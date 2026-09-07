"""Unit tests for Matchups persistence, Standings ranking, Locked Starter Optimizer retention, and Backtest Grid Search."""

import pytest
from sqlalchemy import select

from src.db.models import MatchupModel
from src.services.backtesting.evaluator import backtest_evaluator
from src.services.optimizer.lineup_optimizer import lineup_optimizer
from src.services.recommendation.scoring_engine import (
    ScoringWeights,
    StartSitEvaluation,
)


def test_matchup_sync_and_api(client, db_session):
    """Verify matchups are persisted during sync and exposed via /api/league/matchups."""
    # 1. Sync mock league
    sync_resp = client.post("/api/league/sync?use_mock=true")
    assert sync_resp.status_code == 200
    synced_league_id = sync_resp.json()["league_id"]

    # 2. Check MatchupModel in SQLite DB
    db_matchups = db_session.execute(
        select(MatchupModel).where(MatchupModel.league_id == synced_league_id)
    ).scalars().all()
    assert len(db_matchups) == 4
    for m in db_matchups:
        assert m.home_team_id is not None
        assert m.away_team_id is not None
        assert m.week == 1

    # 3. Query the matchups API endpoint
    matchups_resp = client.get("/api/league/matchups?week=1")
    assert matchups_resp.status_code == 200
    matchups_data = matchups_resp.json()
    assert len(matchups_data) == 4

    first = matchups_data[0]
    assert first["home_team_name"] != ""
    assert first["away_team_name"] != ""
    assert first["home_projected"] > 0
    assert first["away_projected"] >= 0
    assert "home_score" in first
    assert "away_score" in first


def test_standings_ranking_order(client):
    """Verify teams in summary are strictly sorted by win_pct descending, then points_for descending."""
    client.post("/api/league/sync?use_mock=true")
    resp = client.get("/api/league/summary")
    assert resp.status_code == 200
    teams = resp.json()["teams"]
    assert len(teams) == 8

    # Verify monotonic ranking
    for i in range(len(teams)):
        assert teams[i]["rank"] == i + 1
        if i > 0:
            prev = teams[i - 1]
            curr = teams[i]
            assert (
                prev["win_pct"] > curr["win_pct"]
                or (
                    prev["win_pct"] == curr["win_pct"]
                    and prev["points_for"] >= curr["points_for"]
                )
            )


def test_locked_starter_retention_in_optimizer():
    """Verify that locked starters are never dropped or omitted by the optimizer."""
    locked_qb = StartSitEvaluation(
        player_id=101,
        full_name="Locked QB",
        position="QB",
        pro_team="KC",
        projected_points=18.0,
        start_score=75.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="DEN",
        is_home=True,
        implied_team_total=24.5,
        injury_status="ACTIVE",
    )
    better_bench_qb = StartSitEvaluation(
        player_id=102,
        full_name="Bench Superstar QB",
        position="QB",
        pro_team="BUF",
        projected_points=28.0,
        start_score=95.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="MIA",
        is_home=True,
        implied_team_total=27.0,
        injury_status="ACTIVE",
    )

    roster_evals = [locked_qb, better_bench_qb]
    locked_starter_map = {101: 0}  # Player 101 is locked in the QB starter slot (slot 0)

    result = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"QB": 1},
        evaluations=roster_evals,
        current_starter_ids={101},
        locked_player_ids={101},
        locked_starter_slot_map=locked_starter_map,
    )

    starter_ids = [s.recommended_player.player_id for s in result.starters]
    bench_ids = [b.player_id for b in result.bench]

    # Locked QB MUST remain the starter even though bench QB had higher projection/StartScore
    assert 101 in starter_ids
    assert 102 in bench_ids


def test_backtest_grid_search_tuning(client, db_session):
    """Verify that the systematic simplex grid search runs and produces valid weights summing to 1.0."""
    sync_resp = client.post("/api/league/sync?use_mock=true")
    league_id = sync_resp.json()["league_id"]

    # Test via direct evaluator call
    initial_weights = ScoringWeights(
        projection_weight=0.35,
        opportunity_weight=0.20,
        matchup_weight=0.20,
        environment_weight=0.10,
        health_weight=0.10,
        weather_weight=0.05,
    )
    result = backtest_evaluator.tune_weights(
        db=db_session,
        league_id=league_id,
        team_id=1,
        current_weights=initial_weights,
    )

    assert result is not None
    assert "15 profiles tested" in result.message
    best_w = result.optimized_weights
    total_weight = (
        best_w.projection_weight
        + best_w.opportunity_weight
        + best_w.matchup_weight
        + best_w.environment_weight
        + best_w.health_weight
        + best_w.weather_weight
    )
    # Weights should be normalized simplex summing to 1.0
    assert pytest.approx(total_weight, rel=1e-2) == 1.0

    # Also test via API endpoint
    api_resp = client.post("/api/backtest/tune?team_id=1")
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert "optimized_weights" in api_data


def test_opponent_dvp_and_def_rank_in_optimal_lineup(client):
    """Verify that optimal lineup exposes opponent DvP and overall defensive rank for Week 1."""
    client.post("/api/league/sync?use_mock=true")
    resp = client.get("/api/lineup/optimal?team_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["starters"]) > 0

    for slot in data["starters"]:
        p = slot["recommended_player"]
        if p["opponent"] != "BYE":
            assert p.get("opp_dvp_rank") is not None
            assert 1 <= p["opp_dvp_rank"] <= 32
            assert p.get("opp_def_rank") is not None
            assert 1 <= p["opp_def_rank"] <= 32
            assert p.get("dvp_source") == "FantasyPros Consensus"
            assert p.get("opp_dvp_grade") in ("FAVORABLE", "NEUTRAL", "TOUGH")
            assert p.get("matchup_stars") is not None
            assert 1 <= p["matchup_stars"] <= 5

    for b in data["bench"]:
        if b["opponent"] != "BYE":
            assert b.get("opp_dvp_rank") is not None
            assert 1 <= b["opp_dvp_rank"] <= 32
            assert b.get("opp_def_rank") is not None
            assert 1 <= b["opp_def_rank"] <= 32
            assert b.get("dvp_source") == "FantasyPros Consensus"
            assert b.get("matchup_stars") is not None
            assert 1 <= b["matchup_stars"] <= 5


def test_dvp_client_matchup_stars():
    """Verify FantasyPros 1-5 star calibration against 1-32 defensive ranks."""
    from src.adapters.nfl.dvp_client import dvp_client

    # 1 Star: Toughest (Rank 1-6)
    assert dvp_client.get_matchup_stars(1) == 1
    assert dvp_client.get_matchup_stars(6) == 1

    # 2 Stars: Tough (Rank 7-12)
    assert dvp_client.get_matchup_stars(7) == 2
    assert dvp_client.get_matchup_stars(12) == 2

    # 3 Stars: Neutral (Rank 13-20, e.g. Chase Brown vs TB #13)
    assert dvp_client.get_matchup_stars(13) == 3
    assert dvp_client.get_matchup_stars(20) == 3

    # 4 Stars: Favorable (Rank 21-26)
    assert dvp_client.get_matchup_stars(21) == 4
    assert dvp_client.get_matchup_stars(26) == 4

    # 5 Stars: Smash / Generous (Rank 27-32)
    assert dvp_client.get_matchup_stars(27) == 5
    assert dvp_client.get_matchup_stars(32) == 5

    # Fallback
    assert dvp_client.get_matchup_stars(None) == 3
