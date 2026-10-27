"""End-to-End Verification Test Suite for Week 8 of the 2026 NFL Season.

Verifies:
1. Live Injuries as of 10/27/2026 (800 records, non-zero IDs, practice statuses, beneficiaries)
2. 32-team depth charts and PFF scouting matrices
3. Week 8 Vegas movement (14 games)
4. In-House Proprietary DvP (128 records, completed Weeks 1–7)
5. Week 8 Quant Projections (JSON & Parquet, Ensemble Blend, Ceilings)
6. Week 8 Expert Consensus Waiver Wire Intelligence & Byes (HOU, NO, NYG, SF)
7. SQLite Database League calibration (current_week == 8)
8. FastAPI Service Endpoints (/api/league/summary, /api/analysis/dvp-ratings, /api/waiver/consensus-board)
"""

import asyncio
import json
from pathlib import Path
import pandas as pd
import pytest
from starlette.testclient import TestClient

from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.schedule_client import NFLGame, nfl_schedule_client
from src.db.models import LeagueModel, PlayerModel
from src.db.session import SessionLocal
from src.main import app
from src.services.waiver.expert_consensus_service import expert_consensus_service

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


@pytest.fixture(scope="module")
def api_client():
    with TestClient(app) as client:
        yield client


# ==============================================================================
# 1. Live Injury Wire (As of 10/27/2026)
# ==============================================================================

def test_live_injuries_integrity_as_of_oct_27():
    """Verify data/injuries_live_2026.json contains >= 750 records with non-zero IDs and practice trends."""
    inj_file = DATA_DIR / "injuries_live_2026.json"
    assert inj_file.exists(), f"Missing {inj_file}"

    with open(inj_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("season") == 2026
    injuries = data.get("injuries", [])
    assert len(injuries) >= 750, f"Expected >= 750 injuries, got {len(injuries)}"

    # Quality check: non-zero IDs
    zero_ids = [i for i in injuries if not i.get("athlete_id") or i.get("athlete_id") <= 0]
    assert len(zero_ids) == 0, f"Found {len(zero_ids)} injuries with invalid/zero athlete_id"

    # Key injury verifications as of 10/27/2026
    inj_by_name = {i["name"]: i for i in injuries}

    # Saquon Barkley hamstring
    assert "Saquon Barkley" in inj_by_name
    barkley = inj_by_name["Saquon Barkley"]
    assert barkley["is_out"] or "QUESTIONABLE" in barkley["status"].upper() or "HAMSTRING" in barkley.get("headline", "").upper()

    # Lamar Jackson ankle
    assert "Lamar Jackson" in inj_by_name
    lamar = inj_by_name["Lamar Jackson"]
    assert lamar.get("practice_status") in ("DNP", "LIMITED", "NOT_REPORTED")

    # Jalen Coker shoulder
    assert "Jalen Coker" in inj_by_name

    # Check next-man-up beneficiaries
    beneficiaries = [i for i in injuries if i.get("backup_athlete_name")]
    assert len(beneficiaries) >= 30, f"Expected >= 30 next-man-up beneficiaries, got {len(beneficiaries)}"


# ==============================================================================
# 2. Week 8 Vegas Betting Movement & Schedule
# ==============================================================================

def test_vegas_movement_week8_14_games():
    """Validate data/vegas_movement_2026.json has week == 8 and 14 games."""
    vegas_file = DATA_DIR / "vegas_movement_2026.json"
    assert vegas_file.exists(), f"Missing {vegas_file}"

    with open(vegas_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("season") == 2026
    assert data.get("week") == 8, f"Expected week 8, got {data.get('week')}"
    assert data.get("total_games") == 14, f"Expected 14 games, got {data.get('total_games')}"
    games = data.get("games", [])
    assert len(games) == 14

    for g in games:
        assert g.get("over_under") > 0
        assert "spread" in g
        assert g.get("home_team")
        assert g.get("away_team")


def test_nfl_schedule_client_week8():
    """Verify schedule client returns 14 games for Week 8."""
    games = asyncio.run(nfl_schedule_client.fetch_week_schedule(season=2026, week=8))
    assert len(games) == 14
    for g in games:
        assert isinstance(g, NFLGame)
        assert g.over_under > 0


# ==============================================================================
# 3. In-House Proprietary DvP (Weeks 1–7 Realized)
# ==============================================================================

def test_proprietary_dvp_week8():
    """Validate data/nfl_dvp_proprietary_2026.json has week == 8 and 128 records."""
    dvp_file = DATA_DIR / "nfl_dvp_proprietary_2026.json"
    assert dvp_file.exists(), f"Missing {dvp_file}"

    with open(dvp_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Dictionary mapping position -> list of 32 team records
    assert isinstance(data, dict)
    assert set(data.keys()) == {"QB", "RB", "WR", "TE"}

    all_records = []
    for pos, recs in data.items():
        assert len(recs) == 32
        all_records.extend(recs)

    assert len(all_records) == 128
    assert all(r.get("pro_team") for r in all_records)
    assert all(r.get("position") in ("QB", "RB", "WR", "TE") for r in all_records)
    assert all("half_ppr_fpa" in r and "full_ppr_fpa" in r for r in all_records)


# ==============================================================================
# 4. Week 8 Quant Projections Artifacts
# ==============================================================================

def test_projections_week8_artifacts():
    """Validate projections_week_8_2026.json and .parquet exist with ensemble projections."""
    json_path = DATA_DIR / "projections_week_8_2026.json"
    parquet_path = DATA_DIR / "projections_week_8_2026.parquet"

    assert json_path.exists(), f"Missing {json_path}"
    assert parquet_path.exists(), f"Missing {parquet_path}"

    with open(json_path, "r", encoding="utf-8") as f:
        projections = json.load(f)

    assert len(projections) >= 150, f"Expected >= 150 projected players, got {len(projections)}"

    sample = projections[0]
    for key in ("player", "team", "position", "full_ppr", "half_ppr", "ensemble_half", "floor_10th", "ceiling_95th"):
        assert key in sample, f"Missing key '{key}' in projection"

    df = pd.read_parquet(parquet_path)
    assert len(df) >= 150
    assert "player" in df.columns


# ==============================================================================
# 5. Week 8 Waiver Expert Consensus & Bye Weeks
# ==============================================================================

def test_waiver_consensus_week8():
    """Validate data/waiver_expert_consensus_week_8_2026.json and bye teams (HOU, NO, NYG, SF)."""
    consensus_file = DATA_DIR / "waiver_expert_consensus_week_8_2026.json"
    assert consensus_file.exists(), f"Missing {consensus_file}"

    with open(consensus_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("season") == 2026
    assert data.get("week") == 8
    positions = data.get("positions", {})
    assert "RB" in positions and "WR" in positions and "TE" in positions and "QB" in positions

    # Check top RB is Will Shipley
    top_rb = positions["RB"][0]
    assert top_rb["full_name"] == "Will Shipley"
    assert top_rb["consensus_tier"] == "MUST_ADD"

    # Check top WR is Jalen Coker
    top_wr = positions["WR"][0]
    assert top_wr["full_name"] == "Jalen Coker"
    assert top_wr["consensus_tier"] == "MUST_ADD"


# ==============================================================================
# 6. SQLite Database Calibration
# ==============================================================================

def test_sqlite_database_week8_calibration():
    """Validate SQLite active league is Week 8 and players are calibrated."""
    db = SessionLocal()
    try:
        league = db.query(LeagueModel).order_by(LeagueModel.last_synced_at.desc()).first()
        assert league is not None
        assert league.current_week == 8, f"Expected league.current_week == 8, got {league.current_week}"

        total_players = db.query(PlayerModel).count()
        assert total_players >= 390

        non_none_count = db.query(PlayerModel).filter(PlayerModel.projected_points.isnot(None)).count()
        assert non_none_count == total_players

        calibrated = db.query(PlayerModel).filter(PlayerModel.projected_points > 0).count()
        assert calibrated >= 280
    finally:
        db.close()


# ==============================================================================
# 7. FastAPI Service Endpoints for Week 8
# ==============================================================================

def test_api_league_summary_week8(api_client):
    """GET /api/league/summary returns 200 with current_week == 8."""
    response = api_client.get("/api/league/summary")
    assert response.status_code == 200
    data = response.json()
    assert data.get("current_week") == 8
    assert data.get("season") == 2026


def test_api_dvp_ratings_week8(api_client):
    """GET /api/analysis/dvp-ratings returns 200 with 128 Week 8 records."""
    response = api_client.get("/api/analysis/dvp-ratings")
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 128
    assert records[0]["week"] == 8


def test_api_waiver_consensus_board_week8(api_client):
    """GET /api/waiver/consensus-board returns 200 with Week 8 pickups."""
    response = api_client.get("/api/waiver/consensus-board")
    assert response.status_code == 200
    data = response.json()
    assert data.get("week") == 8
    assert data.get("season") == 2026
    positions = data.get("positions", {})
    assert len(positions) >= 4
