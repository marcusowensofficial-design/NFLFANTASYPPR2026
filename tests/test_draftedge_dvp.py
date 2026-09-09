"""Tests for DraftEdge Defense vs Position (DvP) integration, scraper, service, and API endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.adapters.nfl.draftedge_client import draftedge_client, get_softness_tier
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.main import app
from src.services.matchup.dvp_service import dvp_service
from src.services.recommendation.scoring_engine import scoring_engine


import asyncio

def test_draftedge_client_positions():
    """Verify DraftEdge client parses exactly 32 teams for each core position."""
    for pos in ["QB", "RB", "WR", "TE"]:
        records = asyncio.run(draftedge_client.fetch_position_dvp(pos))
        assert len(records) == 32, f"Expected 32 teams for {pos}, got {len(records)}"

        for r in records:
            assert "pro_team" in r and r["pro_team"] != "UNK"
            assert "team_name" in r and len(r["team_name"]) > 0
            assert "dk_fpa" in r and r["dk_fpa"] >= 0.0
            assert "vs_avg" in r
            assert "prior_season_fpa" in r and r["prior_season_fpa"] >= 0.0
            assert "tier" in r and r["tier"] in ("SMASH", "FAVORABLE", "NEUTRAL", "TOUGH", "LOCKDOWN")
            assert "rank_softness" in r and 1 <= r["rank_softness"] <= 32
            assert "rank_defense" in r and 1 <= r["rank_defense"] <= 32
            assert r["rank_softness"] + r["rank_defense"] == 33
            assert "supporting_stats" in r and isinstance(r["supporting_stats"], dict)


def test_softness_tier_boundaries():
    """Verify tier assignment matches softness rank specification."""
    assert get_softness_tier(1) == ("SMASH", "Elite Smash Matchup")
    assert get_softness_tier(6) == ("SMASH", "Elite Smash Matchup")
    assert get_softness_tier(7) == ("FAVORABLE", "Favorable Matchup")
    assert get_softness_tier(12) == ("FAVORABLE", "Favorable Matchup")
    assert get_softness_tier(13) == ("NEUTRAL", "Neutral Matchup")
    assert get_softness_tier(20) == ("NEUTRAL", "Neutral Matchup")
    assert get_softness_tier(21) == ("TOUGH", "Tough Defense")
    assert get_softness_tier(26) == ("TOUGH", "Tough Defense")
    assert get_softness_tier(27) == ("LOCKDOWN", "Brutal Lockdown")
    assert get_softness_tier(32) == ("LOCKDOWN", "Brutal Lockdown")


def test_dvp_service_ratings_and_matchup():
    """Verify DvP service retrieves ratings and single player matchups."""
    qb_ratings = dvp_service.get_dvp_ratings(season=2026, week=1, position="QB")
    assert len(qb_ratings) == 32
    assert qb_ratings[0]["rank_softness"] == 1
    assert qb_ratings[-1]["rank_softness"] == 32

    # Player matchup lookup
    dal_qb = dvp_service.get_matchup_for_player(opponent_team="DAL", position="QB", season=2026, week=1)
    assert dal_qb is not None
    assert dal_qb["defensive_team"] == "DAL"
    assert dal_qb["dk_fpa"] == 24.0
    assert dal_qb["tier"] == "SMASH"
    assert dal_qb["is_baseline"] is True


def test_dvp_api_endpoints():
    """Verify FastAPI endpoints for DvP ratings and status."""
    client = TestClient(app)

    # 1. Status endpoint
    status_res = client.get("/api/analysis/dvp-status?season=2026&week=1")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["total_records"] >= 128
    assert status_data["is_seeded"] is True
    assert status_data["is_baseline"] is True
    assert "2025-26 regular season" in status_data["baseline_context"]

    # 2. Ratings endpoint
    ratings_res = client.get("/api/analysis/dvp-ratings?season=2026&week=1&position=RB")
    assert ratings_res.status_code == 200
    rb_list = ratings_res.json()
    assert len(rb_list) == 32
    assert rb_list[0]["position"] == "RB"
    assert "rush_yds" in rb_list[0]["supporting_stats"]


def test_scoring_engine_dvp_reasons():
    """Verify player evaluation populates dvp_fpa and generates structured matchup reasons."""
    qb = PlayerModel(id=999, full_name="Streaming QB", position="QB", pro_team="WAS", projected_points=16.0)
    game = NFLGame(
        id="G_TEST",
        name="WAS @ DAL",
        date="2026-09-13T17:00:00Z",
        venue_name="AT&T Stadium",
        season=2026,
        week=1,
        home_team="DAL",
        away_team="WAS",
        home_implied_total=24.0,
        away_implied_total=21.0,
    )

    ev = scoring_engine.evaluate_player(qb, nfl_game=game)
    assert ev.dvp_fpa is not None
    assert ev.dvp_fpa["defensive_team"] == "DAL"
    assert ev.dvp_fpa["dk_fpa"] == 24.0

    # Ensure high-signal DvP reason exists
    dvp_reasons = [r for r in ev.reasons_positive if "DK pts/G" in r or "Soft QB Matchup" in r]
    assert len(dvp_reasons) > 0, f"Expected DvP reason in reasons_positive, found: {ev.reasons_positive}"
    assert "24.0 DK pts/G" in dvp_reasons[0]
