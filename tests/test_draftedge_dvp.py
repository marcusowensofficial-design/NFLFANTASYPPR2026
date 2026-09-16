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
    assert dal_qb["dk_fpa"] >= 20.0
    assert dal_qb["tier"] == "SMASH"
    assert "is_baseline" in dal_qb


def test_dvp_api_endpoints():
    """Verify FastAPI endpoints for DvP ratings and status."""
    client = TestClient(app)

    # 1. Status endpoint
    status_res = client.get("/api/analysis/dvp-status?season=2026&week=1")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["total_records"] >= 128
    assert status_data["is_seeded"] is True
    assert "is_baseline" in status_data
    assert "baseline_context" in status_data

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
    assert ev.dvp_fpa["dk_fpa"] >= 20.0

    # Ensure high-signal DvP reason exists
    dvp_reasons = [r for r in ev.reasons_positive if "DK pts/G" in r or "Soft QB Matchup" in r]
    assert len(dvp_reasons) > 0, f"Expected DvP reason in reasons_positive, found: {ev.reasons_positive}"


def test_was_pit_sf_filled_in_and_calculated_fpa():
    """Verify Washington Commanders, Steelers TE, and 49ers rushing are filled in with valid yards allowed
    and that FPA is calculated using our exact Half-PPR and Full-PPR formulas.
    """
    from src.services.matchup.dvp_calculator import calculate_fpa_from_supporting_stats

    # 1. Washington Commanders in QB, RB, WR, TE
    qb_ratings = {r["pro_team"]: r for r in dvp_service.get_dvp_ratings(season=2026, week=2, position="QB")}
    assert "WAS" in qb_ratings
    was_qb = qb_ratings["WAS"]
    assert was_qb["supporting_stats"]["pass_yds"] > 200.0, f"Expected WAS pass_yds > 200, got {was_qb['supporting_stats']}"
    assert was_qb["supporting_stats"]["pass_td"] > 1.5
    h_qb, f_qb = calculate_fpa_from_supporting_stats("QB", was_qb["supporting_stats"])
    assert was_qb["dk_fpa"] == h_qb
    assert was_qb["fd_fpa"] == f_qb

    rb_ratings = {r["pro_team"]: r for r in dvp_service.get_dvp_ratings(season=2026, week=2, position="RB")}
    assert "WAS" in rb_ratings
    was_rb = rb_ratings["WAS"]
    assert was_rb["supporting_stats"]["rush_yds"] > 90.0, f"Expected WAS rush_yds > 90, got {was_rb['supporting_stats']}"
    assert was_rb["supporting_stats"]["rush_td"] > 0.5
    h_rb, f_rb = calculate_fpa_from_supporting_stats("RB", was_rb["supporting_stats"])
    assert was_rb["dk_fpa"] == h_rb
    assert was_rb["fd_fpa"] == f_rb

    wr_ratings = {r["pro_team"]: r for r in dvp_service.get_dvp_ratings(season=2026, week=2, position="WR")}
    assert "WAS" in wr_ratings
    was_wr = wr_ratings["WAS"]
    assert was_wr["supporting_stats"]["rec_yds"] > 120.0
    assert was_wr["supporting_stats"]["rec"] > 8.0

    te_ratings = {r["pro_team"]: r for r in dvp_service.get_dvp_ratings(season=2026, week=2, position="TE")}
    assert "WAS" in te_ratings
    was_te = te_ratings["WAS"]
    assert was_te["supporting_stats"]["rec_yds"] > 50.0
    assert was_te["supporting_stats"]["rec_td"] > 0.5

    # 2. San Francisco 49ers for rushing
    assert "SF" in rb_ratings
    sf_rb = rb_ratings["SF"]
    assert sf_rb["supporting_stats"]["rush_yds"] > 80.0, f"Expected SF rush_yds > 80, got {sf_rb['supporting_stats']}"
    assert sf_rb["supporting_stats"]["rush_td"] > 0.5
    h_sf, f_sf = calculate_fpa_from_supporting_stats("RB", sf_rb["supporting_stats"])
    assert sf_rb["dk_fpa"] == h_sf
    assert sf_rb["fd_fpa"] == f_sf

    # 3. Pittsburgh Steelers for TE matchups
    assert "PIT" in te_ratings
    pit_te = te_ratings["PIT"]
    assert pit_te["supporting_stats"]["rec_yds"] > 40.0, f"Expected PIT TE rec_yds > 40, got {pit_te['supporting_stats']}"
    assert pit_te["supporting_stats"]["targets"] > 5.0
    assert pit_te["supporting_stats"]["rec"] > 3.0
    h_pit, f_pit = calculate_fpa_from_supporting_stats("TE", pit_te["supporting_stats"])
    assert pit_te["dk_fpa"] == h_pit
    assert pit_te["fd_fpa"] == f_pit

