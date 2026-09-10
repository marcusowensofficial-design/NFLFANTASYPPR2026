"""FastAPI Application entrypoint for the ESPN Fantasy Football 2026 Assistant."""

import logging
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contextlib import asynccontextmanager
from src.adapters.espn.client import ESPNClient
from src.adapters.espn.schemas import LeagueSummary
from src.api.analysis_routes import router as analysis_router
from src.api.backtest_routes import router as backtest_router
from src.api.dfs_routes import router as dfs_router
from src.api.fantasypros_routes import router as fantasypros_router
from src.api.injury_routes import router as injury_router
from src.api.league_routes import router as league_router
from src.api.lineup_routes import router as lineup_router
from src.api.recommendation_routes import router as recommendation_router
from src.api.sleeper_routes import router as sleeper_router
from src.api.waiver_routes import router as waiver_router

from src.core.config import settings
from src.db.session import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fantasy_assistant")


import asyncio
import time
from pathlib import Path


async def _auto_sync_intelligence_if_stale():
    """Runs master NFL intelligence sync in background if data is older than 12 hours."""
    try:
        depth_file = Path("data/nfl_depth_charts_2026.json")
        now = time.time()
        if not depth_file.exists() or (now - depth_file.stat().st_mtime > 43200):
            logger.info("Local NFL intelligence is stale (>12h) or missing. Auto-syncing in background...")
            from scripts.sync_nfl_intelligence import sync_depth_charts, sync_injuries, sync_vegas_odds
            await asyncio.gather(sync_depth_charts(), sync_injuries(), sync_vegas_odds())
            logger.info("Background NFL intelligence auto-sync completed successfully.")
    except Exception as e:
        logger.warning(f"Background NFL intelligence sync encountered an issue: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables
    logger.info("Initializing SQLite database tables...")
    init_db()
    # Trigger non-blocking intelligence auto-sync
    asyncio.create_task(_auto_sync_intelligence_if_stale())
    yield



app = FastAPI(
    title="ESPN Fantasy Football 2026 Assistant API",
    description="Local-first analytics, start/sit engine, and lineup optimizer for ESPN Fantasy Football.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(league_router)
app.include_router(lineup_router)
app.include_router(recommendation_router)
app.include_router(waiver_router)
app.include_router(backtest_router)
app.include_router(injury_router)
app.include_router(fantasypros_router)
app.include_router(sleeper_router)
app.include_router(analysis_router)
app.include_router(dfs_router)
# Vegas Odds & Props registered


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

# Allow local and deployed frontends (e.g. Render, Railway, localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    configured_league_id: int | None
    season: int
    has_credentials: bool


class ConnectionTestRequest(BaseModel):
    league_id: int | None = None
    season: int | None = None
    swid: str | None = None
    espn_s2: str | None = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    is_private_required: bool
    summary: LeagueSummary | None = None


@app.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Basic service health check."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
        configured_league_id=settings.espn_league_id,
        season=settings.espn_season,
        has_credentials=bool(settings.espn_swid and settings.espn_s2),
    )


@app.get("/api/espn/status", response_model=ConnectionTestResponse)
async def get_espn_status() -> ConnectionTestResponse:
    """Test connection using currently configured .env credentials."""
    if not settings.espn_league_id:
        return ConnectionTestResponse(
            success=False,
            message="No ESPN_LEAGUE_ID configured in .env file.",
            is_private_required=False,
            summary=None,
        )

    client = ESPNClient(
        league_id=settings.espn_league_id,
        season=settings.espn_season,
        swid=settings.espn_swid,
        espn_s2=settings.espn_s2,
    )

    success, message, summary = await client.test_connection()
    is_private_required = "UNAUTHORIZED" in message

    return ConnectionTestResponse(
        success=success,
        message=message,
        is_private_required=is_private_required,
        summary=summary,
    )


@app.post("/api/espn/test", response_model=ConnectionTestResponse)
async def test_espn_connection_endpoint(payload: ConnectionTestRequest) -> ConnectionTestResponse:
    """Test connection with provided or fallback credentials."""
    league_id = payload.league_id or settings.espn_league_id
    if not league_id:
        raise HTTPException(status_code=400, detail="league_id is required.")

    season = payload.season or settings.espn_season
    swid = payload.swid if payload.swid is not None else settings.espn_swid
    espn_s2 = payload.espn_s2 if payload.espn_s2 is not None else settings.espn_s2

    client = ESPNClient(
        league_id=league_id,
        season=season,
        swid=swid,
        espn_s2=espn_s2,
    )

    success, message, summary = await client.test_connection()
    is_private_required = "UNAUTHORIZED" in message

    return ConnectionTestResponse(
        success=success,
        message=message,
        is_private_required=is_private_required,
        summary=summary,
    )


# -----------------------------------------------------------------------------
# Frontend Static Asset & Single-Page Application (SPA) Serving
# -----------------------------------------------------------------------------
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if (frontend_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve built frontend SPA assets or fallback to index.html."""
    if full_path.startswith("api/") or full_path in ("docs", "openapi.json", "redoc"):
        raise HTTPException(status_code=404, detail="Not Found")

    file_path = frontend_dist / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)

    index_html = frontend_dist / "index.html"
    if index_html.is_file():
        return FileResponse(index_html)

    return {"message": "Apex Fantasy Analytics API", "docs": "/docs"}

