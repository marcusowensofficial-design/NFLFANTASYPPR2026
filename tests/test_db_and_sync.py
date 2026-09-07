"""Unit tests for Phase 2: SQLite database models, ESPN hybrid sync service, and league API endpoints."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.main import app
from src.services.espn_sync import ESPNSyncService


@pytest.mark.asyncio
async def test_sync_mock_league_to_db(db_session):
    """Verify that ESPNSyncService accurately stores the 8-team PPR mock data into SQLite."""
    service = ESPNSyncService(db=db_session)

    # Perform initial sync using mock fixture
    success, message, league = await service.sync(league_id=84920174, force=True, use_mock=True)

    assert success is True
    assert "Successfully synchronized" in message
    assert league is not None
    assert league.id == 84920174
    assert league.name == "The Apex 2026 Invitational"
    assert league.size == 8
    assert league.is_ppr is True
    assert league.reception_points == 1.0

    # Verify teams
    teams = db_session.execute(select(TeamModel).where(TeamModel.league_id == 84920174)).scalars().all()
    assert len(teams) == 8

    # Verify user team detection
    user_team = db_session.execute(
        select(TeamModel).where(TeamModel.league_id == 84920174, TeamModel.is_user_team == True)
    ).scalar_one_or_none()
    assert user_team is not None
    assert user_team.id in [1, 6]
    assert league.user_team_id in [1, 6]

    # Verify roster entries for team 1
    entries = db_session.execute(
        select(RosterEntryModel).where(RosterEntryModel.league_id == 84920174, RosterEntryModel.team_id == 1)
    ).scalars().all()
    assert len(entries) == 11
    starters = [e for e in entries if e.is_starter]
    bench = [e for e in entries if not e.is_starter]
    assert len(starters) == 9
    assert len(bench) == 2

    # Verify player details
    jayden = db_session.execute(select(PlayerModel).where(PlayerModel.full_name == "Jayden Daniels")).scalar_one()
    assert jayden.position == "QB"
    assert jayden.pro_team == "WSH"
    assert jayden.projected_points == 21.4

    marvin = db_session.execute(select(PlayerModel).where(PlayerModel.full_name == "Marvin Harrison Jr.")).scalar_one()
    assert marvin.position == "WR"
    assert marvin.injury_status == "QUESTIONABLE"
    assert marvin.injured is True
    assert marvin.projected_points == 16.8


@pytest.mark.asyncio
async def test_cache_freshness_check(db_session):
    """Verify that is_cache_stale correctly recognizes fresh vs expired cache."""
    service = ESPNSyncService(db=db_session)

    # Before sync: cache should be stale
    assert service.is_cache_stale(league_id=84920174, max_age_minutes=15) is True

    # Sync
    await service.sync(league_id=84920174, force=True, use_mock=True)

    # Immediately after sync: cache should NOT be stale
    assert service.is_cache_stale(league_id=84920174, max_age_minutes=15) is False


def test_api_league_endpoints(client):
    """Test FastAPI endpoints for league sync, summary, teams, and team roster."""
    # 1. Trigger sync with use_mock=True
    sync_resp = client.post("/api/league/sync?use_mock=true")
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["success"] is True
    assert sync_data["teams_count"] in [8, 10]

    # 2. Get league summary
    summary_resp = client.get("/api/league/summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()
    assert summary_data["name"] == "The Apex 2026 Invitational"
    assert summary_data["size"] in [8, 10]
    assert summary_data["is_ppr"] is True
    assert summary_data["user_team_id"] in [1, 6]
    assert len(summary_data["teams"]) in [8, 10]

    # 3. Get teams
    teams_resp = client.get("/api/league/teams")
    assert teams_resp.status_code == 200
    teams_data = teams_resp.json()
    assert len(teams_data) in [8, 10]

    # 4. Get team 1 roster
    roster_resp = client.get("/api/league/teams/1/roster")
    assert roster_resp.status_code == 200
    roster_data = roster_resp.json()
    assert roster_data["team_id"] == 1
    assert roster_data["starters_count"] == 9
    assert roster_data["bench_count"] == 2
    assert roster_data["total_projected_points"] > 0
    assert len(roster_data["roster"]) == 11
