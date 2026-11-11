"""End-to-End Verification Test Suite for Week 10 (11/10/2026) of the 2026 NFL Season.

Verifies live data stores, Week 10 bye configurations, in-house DvP across Weeks 1-9,
quant projections, expert consensus waivers, SQLite calibration, FastAPI routes, and
the built React SPA bundle.
"""

import asyncio
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.adapters.nfl.schedule_client import NFLGame, nfl_schedule_client
from src.db.models import DefenseVsPositionModel, LeagueModel, PlayerModel
from src.db.session import SessionLocal
from src.main import app
from src.services.waiver.expert_consensus_service import (
    NFL_BYE_WEEKS_2026,
    expert_consensus_service,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIST = PROJECT_ROOT / "web" / "frontend" / "dist"


@pytest.fixture
def api_client():
    """Real TestClient against live SQLite database and updated data caches."""
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client


def test_live_injuries_updated_nov10():
    """Verify data/injuries_live_2026.json contains >= 800 live records with zero invalid IDs."""
    inj_file = DATA_DIR / "injuries_live_2026.json"
    assert inj_file.exists(), f"Missing {inj_file}"

    with open(inj_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("season") == 2026
    injuries = data.get("injuries", [])
    assert len(injuries) >= 800, f"Expected >= 800 injuries, got {len(injuries)}"

    zero_ids = [i for i in injuries if not i.get("athlete_id") or i.get("athlete_id") <= 0]
    assert len(zero_ids) == 0, f"Found {len(zero_ids)} injuries with invalid athlete_id"

    beneficiaries = [i for i in injuries if i.get("backup_athlete_name")]
    assert len(beneficiaries) >= 30, f"Expected >= 30 beneficiaries, got {len(beneficiaries)}"


def test_vegas_movement_week10_14_games():
    """Validate data/vegas_movement_2026.json is updated to Week 10 with 14 matchups."""
    vegas_file = DATA_DIR / "vegas_movement_2026.json"
    assert vegas_file.exists(), f"Missing {vegas_file}"

    with open(vegas_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("season") == 2026
    assert data.get("week") == 10, f"Expected week 10, got {data.get('week')}"
    assert data.get("total_games") == 14, f"Expected 14 games, got {data.get('total_games')}"
    games = data.get("games", [])
    assert len(games) == 14

    matchups = {(g.get("away_team"), g.get("home_team")) for g in games}
    assert ("WSH", "NYG") in matchups or ("WAS", "NYG") in matchups
    assert ("SF", "DAL") in matchups
    for g in games:
        assert g.get("over_under", 0) > 0
        assert "spread" in g


def test_nfl_schedule_client_week10_live_and_fallback():
    """Verify NFLScheduleClient live and offline fallback both return 14 Week 10 games."""
    games = asyncio.run(nfl_schedule_client.fetch_week_schedule(season=2026, week=10))
    assert len(games) == 14
    for g in games:
        assert isinstance(g, NFLGame)
        assert g.over_under > 0

    fallback = nfl_schedule_client._get_fallback_schedule(week=10)
    assert len(fallback) == 14


def test_projections_week10_artifacts():
    """Validate Week 10 JSON and Parquet projection exports."""
    json_path = DATA_DIR / "projections_week_10_2026.json"
    parquet_path = DATA_DIR / "projections_week_10_2026.parquet"
    assert json_path.exists(), f"Missing {json_path}"
    assert parquet_path.exists(), f"Missing {parquet_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        projections = json.load(f)
    assert len(projections) >= 250, f"Expected >= 250 Week 10 projections, got {len(projections)}"

    sample = projections[0]
    for key in ("player", "team", "position", "full_ppr", "half_ppr", "ensemble_half", "floor_10th", "ceiling_95th"):
        assert key in sample, f"Missing key '{key}' in projection"

    df = pd.read_parquet(parquet_path)
    assert len(df) >= 250
    assert "player" in df.columns


def test_waiver_consensus_week10_and_byes():
    """Verify Week 10 expert consensus board and official Week 10 Bye weeks (CHI, DEN, PHI, TB)."""
    assert NFL_BYE_WEEKS_2026[10] == {"CHI", "DEN", "PHI", "TB"}

    consensus_file = DATA_DIR / "waiver_expert_consensus_week_10_2026.json"
    assert consensus_file.exists(), f"Missing {consensus_file}"

    data = expert_consensus_service.load_consensus_data()
    assert data.get("season") == 2026
    assert data.get("week") == 10
    positions = data.get("positions", {})
    for pos in ("RB", "WR", "TE", "QB", "DST", "K"):
        assert pos in positions and len(positions[pos]) >= 5, f"Insufficient Week 10 {pos} targets"

    assert positions["RB"][0]["full_name"] == "Blake Corum"
    assert positions["WR"][0]["full_name"] == "KC Concepcion"


def test_sqlite_database_week10_state():
    """Validate SQLite active league is Week 10, DvP Week 10 has 128 rows, and all players calibrated."""
    db = SessionLocal()
    try:
        league = db.query(LeagueModel).order_by(LeagueModel.last_synced_at.desc()).first()
        assert league is not None
        assert league.current_week == 10, f"Expected current_week == 10, got {league.current_week}"

        dvp_w10 = (
            db.query(DefenseVsPositionModel)
            .filter(DefenseVsPositionModel.season == 2026, DefenseVsPositionModel.week == 10)
            .count()
        )
        assert dvp_w10 == 128, f"Expected 128 Week 10 DvP records, got {dvp_w10}"

        total_players = db.query(PlayerModel).count()
        assert total_players >= 390
        non_none = db.query(PlayerModel).filter(PlayerModel.projected_points.isnot(None)).count()
        assert non_none == total_players
    finally:
        db.close()


def test_api_endpoints_and_spa_dist_week10(api_client):
    """Validate production SPA dist and FastAPI Week 10 endpoints."""
    index_file = FRONTEND_DIST / "index.html"
    assert index_file.exists(), "Built web/frontend/dist/index.html is missing"

    root_res = api_client.get("/")
    assert root_res.status_code == 200
    assert "assets/index-" in root_res.text

    summary_res = api_client.get("/api/league/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary.get("current_week") == 10
    assert summary.get("season") == 2026
    assert len(summary.get("teams", [])) == 8

    dvp_res = api_client.get("/api/analysis/dvp-ratings")
    assert dvp_res.status_code == 200
    dvp_records = dvp_res.json()
    assert len(dvp_records) == 128
    assert dvp_records[0]["week"] == 10

    waiver_res = api_client.get("/api/waiver/consensus-board")
    assert waiver_res.status_code == 200
    waiver = waiver_res.json()
    assert waiver.get("week") == 10
    assert waiver.get("season") == 2026

    vegas_res = api_client.get("/api/analysis/vegas-environments")
    assert vegas_res.status_code == 200
    vegas = vegas_res.json()
    assert vegas.get("week") == 10
    assert vegas.get("total_games") == 14
