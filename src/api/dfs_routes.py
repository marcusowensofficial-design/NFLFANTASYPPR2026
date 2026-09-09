import json
import logging
import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query
import numpy as np
from pydantic import BaseModel, Field

from src.dfs.engine import dfs_engine
from src.dfs.loader import dfs_loader
from src.dfs.optimizer import dfs_optimizer
from src.dfs.analyzer import dfs_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dfs", tags=["DFS Optimizer"])


def _np_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

SLATES_MAP = {
    "main": {
        "id": "main",
        "name": "Week 1 Main Slate (13 Games)",
        "games_count": 13,
        "platform": "FanDuel ($60k Cap)",
        "default_csv": str(DATA_DIR / "FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv"),
    },
    "early": {
        "id": "early",
        "name": "Week 1 Early-Only Slate (8 Games)",
        "games_count": 8,
        "platform": "FanDuel ($60k Cap)",
        "default_csv": str(DATA_DIR / "earlyonlysalariesandrosters.csv"),
    },
}


def _resolve_csv_path(slate_id: str) -> str:
    if slate_id.lower() == "uploaded":
        uploaded_path = DATA_DIR / "uploaded_fanduel.csv"
        if uploaded_path.exists():
            return str(uploaded_path)
        raise HTTPException(status_code=404, detail="No uploaded FanDuel CSV found. Please upload one first.")

    slate_info = SLATES_MAP.get(slate_id.lower())
    if slate_info and os.path.exists(slate_info["default_csv"]):
        return slate_info["default_csv"]

    # Check root for earlyonlysalariesandrosters.csv
    root_early = PROJECT_ROOT / "earlyonlysalariesandrosters.csv"
    if slate_id.lower() == "early" and root_early.exists():
        return str(root_early)

    # Fallback to latest fanduel CSV
    latest = dfs_loader.find_latest_fanduel_csv()
    if latest and os.path.exists(latest):
        return latest

    # Secondary check in src/dfs/
    alt_early = PROJECT_ROOT / "src" / "dfs" / "earlyonlysalariesandrosters.csv"
    if slate_id.lower() == "early" and alt_early.exists():
        return str(alt_early)

    raise HTTPException(status_code=404, detail=f"No CSV data found for slate '{slate_id}'.")


class DFSUploadSlateRequest(BaseModel):
    filename: str = Field(default="fanduel_salaries.csv", description="Name of the uploaded CSV file")
    csv_text: str = Field(description="Raw CSV contents from FanDuel export")


class DFSOptimizeRequest(BaseModel):
    slate_id: str = Field(default="main", description="Slate ID: 'main', 'early', or 'uploaded'")
    mode: str = Field(default="SINGLE_ENTRY_GPP", description="'SINGLE_ENTRY_GPP' or 'CASH'")
    num_lineups: int = Field(default=1, ge=1, le=20, description="Number of unique lineups to generate (1-20)")
    randomness: float = Field(default=0.0, ge=0.0, le=0.5, description="Projection variance factor for portfolio diversification")
    projection_source: str = Field(default="MODEL", description="Projection source: MODEL, CONSENSUS, FANTASYPROS, SLEEPER, ESPN")
    custom_projections: dict[str, float] = Field(default_factory=dict, description="Custom projection overrides (player name or ID to points)")
    stack_qb: str | None = Field(default=None, description="Optional quarterback to stack")
    stack_team: str | None = Field(default=None, description="Team abbreviation for primary stack")
    stack_opp: str | None = Field(default=None, description="Opposing team abbreviation for bring-back")
    lock_players: list[str] = Field(default_factory=list, description="List of player names or IDs to force into roster")
    exclude_players: list[str] = Field(default_factory=list, description="List of player names or IDs to exclude")
    min_salary: int = Field(default=58000, ge=50000, le=60000)
    max_salary: int = Field(default=60000, ge=50000, le=60000)


class DFSExportRequest(BaseModel):
    lineups: list[dict[str, Any]] = Field(description="List of solved lineup dictionaries")


@router.post("/upload-slate")
async def upload_slate(payload: DFSUploadSlateRequest) -> dict[str, Any]:
    """Ingests, parses, and enriches a user-uploaded FanDuel CSV file."""
    if not payload.csv_text or not payload.csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV file content is empty.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DATA_DIR / "uploaded_fanduel.csv"

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(payload.csv_text)
    except Exception as e:
        logger.error(f"Failed to save uploaded CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded CSV: {e}")

    # Verify and enrich via loader
    try:
        enriched_df = await dfs_loader.load_slate(csv_path=str(target_path))
        # Clear engine cached slate so fresh data is loaded
        dfs_engine.clear_cache()
    except Exception as e:
        logger.error(f"Failed to parse and enrich uploaded CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid FanDuel CSV format: {e}")

    teams = sorted(enriched_df["team"].unique().tolist()) if "team" in enriched_df.columns else []
    games = sorted(enriched_df["game"].unique().tolist()) if "game" in enriched_df.columns else []
    salary_min = int(enriched_df["salary"].min()) if "salary" in enriched_df.columns and not enriched_df.empty else 0
    salary_max = int(enriched_df["salary"].max()) if "salary" in enriched_df.columns and not enriched_df.empty else 0

    top_stars = []
    if not enriched_df.empty:
        top_df = enriched_df.sort_values(by="salary", ascending=False).head(5)
        for _, r in top_df.iterrows():
            top_stars.append({
                "name": r.get("name"),
                "position": r.get("position"),
                "team": r.get("team"),
                "salary": int(r.get("salary", 0)),
                "proj": float(r.get("proj", 0.0)),
            })

    SLATES_MAP["uploaded"] = {
        "id": "uploaded",
        "name": f"Uploaded: {payload.filename}",
        "games_count": len(games),
        "platform": "FanDuel ($60k Cap)",
        "default_csv": str(target_path),
    }

    return {
        "success": True,
        "slate_id": "uploaded",
        "filename": payload.filename,
        "total_players": len(enriched_df),
        "teams": teams,
        "games_count": len(games),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "top_stars": top_stars,
    }


@router.post("/export-lineups")
async def export_lineups(payload: DFSExportRequest) -> dict[str, Any]:
    """Generates FanDuel CSV upload formatted file content from solved lineups."""
    if not payload.lineups:
        raise HTTPException(status_code=400, detail="No lineups provided for export.")

    csv_text = dfs_optimizer.format_fanduel_csv_export(payload.lineups)
    return {
        "filename": "fanduel_lineup_import.csv",
        "csv_content": csv_text,
        "lineup_count": len(payload.lineups),
    }


@router.get("/slates")
async def get_available_slates() -> list[dict[str, Any]]:
    """Returns available DFS slates with file status and game counts."""
    available = []
    for sid, info in SLATES_MAP.items():
        exists = os.path.exists(info["default_csv"])
        available.append({
            "id": info["id"],
            "name": info["name"],
            "games_count": info["games_count"],
            "platform": info["platform"],
            "is_available": exists,
        })
    return available


@router.get("/slate-data")
async def get_slate_data(
    slate_id: str = Query(default="main"),
    projection_source: str = Query(default="MODEL", description="Projection source: MODEL, CONSENSUS, FANTASYPROS, SLEEPER, ESPN"),
) -> dict[str, Any]:
    """Returns enriched player pool, top game stacks, chalk radar, and tournament leverage targets."""
    csv_path = _resolve_csv_path(slate_id)
    try:
        slate_df = await dfs_engine.get_slate(csv_path=csv_path, projection_source=projection_source)
    except Exception as e:
        logger.error(f"Failed to load slate data for {slate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load slate: {e}")

    import json

    def _to_clean_records(df: Any) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []
        return json.loads(df.to_json(orient="records"))

    # Top Game Stacks
    top_stacks = dfs_analyzer.get_top_game_stacks(slate_df, top_n=5)

    # Top Leverage Plays
    top_leverage_df = dfs_analyzer.get_top_leverage_plays(slate_df, top_n=12)
    leverage_plays = _to_clean_records(top_leverage_df[[
        "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "proj_ownership", "leverage_score", "ownership_tier"
    ]]) if not top_leverage_df.empty else []

    # Top Chalk Plays
    top_chalk_df = dfs_analyzer.get_top_ownership_plays(slate_df, top_n=12)
    chalk_plays = _to_clean_records(top_chalk_df[[
        "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "proj_ownership", "ownership_tier"
    ]]) if not top_chalk_df.empty else []

    # Player pool catalog (sorted by salary desc)
    clean_pool = slate_df[
        ~slate_df["injury"].isin(["IR", "O", "OUT"])
        & (slate_df["proj"] >= 3.0)
    ].sort_values(by="salary", ascending=False)

    player_items = _to_clean_records(clean_pool[[
        "player_id", "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "floor_proj",
        "team_implied", "opp_soft_rank", "opp_tier", "opp_tier_label", "opp_fd_fpa", "value_ratio", "proj_ownership", "ownership_tier", "leverage_score"
    ]])

    raw_resp = {
        "slate_id": slate_id,
        "projection_source": (projection_source or "MODEL").upper(),
        "total_players": len(player_items),
        "top_stacks": top_stacks,
        "leverage_plays": leverage_plays,
        "chalk_plays": chalk_plays,
        "players": player_items,
    }

    return json.loads(json.dumps(raw_resp, default=_np_default))


@router.post("/optimize")
async def optimize_dfs_lineup(payload: DFSOptimizeRequest) -> dict[str, Any]:
    """Solves globally optimal FanDuel lineup(s) under linear constraints and performs live forensic audit."""
    csv_path = _resolve_csv_path(payload.slate_id)
    try:
        if payload.custom_projections:
            slate_df = await dfs_loader.load_slate(
                csv_path=csv_path,
                custom_projections=payload.custom_projections,
                projection_source=payload.projection_source,
            )
        else:
            slate_df = await dfs_engine.get_slate(
                csv_path=csv_path,
                projection_source=payload.projection_source,
            )
    except Exception as e:
        logger.error(f"Failed to load slate for optimizer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load slate: {e}")

    # If single-entry tournament without explicit stack, identify natural top game stack
    stack_qb = payload.stack_qb
    stack_team = payload.stack_team
    stack_opp = payload.stack_opp

    if payload.mode == "SINGLE_ENTRY_GPP" and not stack_qb:
        stacks = dfs_analyzer.get_top_game_stacks(slate_df, top_n=1)
        if stacks:
            top_s = stacks[0]
            stack_qb = top_s["qb"].split(" (")[0]
            qb_row = slate_df[slate_df["name"] == stack_qb]
            if not qb_row.empty:
                stack_team = qb_row.iloc[0]["team"]
                stack_opp = qb_row.iloc[0]["opponent"]

    if payload.num_lineups > 1:
        lineups = dfs_optimizer.optimize_multi(
            df_slate=slate_df,
            num_lineups=payload.num_lineups,
            randomness=payload.randomness,
            mode=payload.mode,
            stack_qb=stack_qb,
            stack_team=stack_team,
            stack_opp=stack_opp,
            lock_players=payload.lock_players if payload.lock_players else None,
            exclude_players=payload.exclude_players if payload.exclude_players else None,
            min_salary=payload.min_salary,
            max_salary=payload.max_salary,
        )
        if not lineups:
            raise HTTPException(
                status_code=400,
                detail="Unable to find feasible DFS lineup under current constraints. Try removing locks or relaxing salary bounds.",
            )
        primary_lineup = lineups[0]
        audit = await dfs_engine.audit_roster(primary_lineup["roster"])
        for l in lineups:
            l["slate_id"] = payload.slate_id
            l["audit"] = audit
            l["active_stack"] = {
                "qb": stack_qb,
                "team": stack_team,
                "opponent": stack_opp,
            } if stack_qb else None

        exposure = dfs_optimizer.calculate_portfolio_exposure(lineups)
        resp = dict(primary_lineup)
        resp["lineups"] = lineups
        resp["exposure"] = exposure
        resp["projection_source"] = (payload.projection_source or "MODEL").upper()
        return json.loads(json.dumps(resp, default=_np_default))

    lineup = dfs_optimizer.optimize(
        df_slate=slate_df,
        mode=payload.mode,
        stack_qb=stack_qb,
        stack_team=stack_team,
        stack_opp=stack_opp,
        lock_players=payload.lock_players if payload.lock_players else None,
        exclude_players=payload.exclude_players if payload.exclude_players else None,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
    )

    if not lineup:
        raise HTTPException(
            status_code=400,
            detail="Unable to find feasible DFS lineup under current constraints. Try removing locks or relaxing salary bounds.",
        )

    # Perform forensic live audit (weather + injuries)
    audit = await dfs_engine.audit_roster(lineup["roster"])
    lineup["audit"] = audit
    lineup["slate_id"] = payload.slate_id
    lineup["projection_source"] = (payload.projection_source or "MODEL").upper()
    lineup["active_stack"] = {
        "qb": stack_qb,
        "team": stack_team,
        "opponent": stack_opp,
    } if stack_qb else None
    lineup_copy = dict(lineup)
    lineup["lineups"] = [lineup_copy]
    lineup["exposure"] = dfs_optimizer.calculate_portfolio_exposure([lineup_copy])

    return json.loads(json.dumps(lineup, default=_np_default))
