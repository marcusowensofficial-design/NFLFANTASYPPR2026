"""Tests for live and resolved game actual scoring transitions across scoring engine, optimizer, and league routes."""

import pytest
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.services.recommendation.scoring_engine import (
    ComponentScores,
    ScoringWeights,
    StartSitEvaluation,
    StartSitScoringEngine,
)
from src.services.optimizer.lineup_optimizer import LineupOptimizer


def test_scoring_engine_upcoming_game():
    """When a game has not started, effective_points equals projected_points and status is UPCOMING."""
    engine = StartSitScoringEngine()
    player = PlayerModel(
        id=101,
        full_name="CeeDee Lamb",
        position="WR",
        pro_team="DAL",
        projected_points=18.5,
        injury_status="ACTIVE",
    )
    game = NFLGame(
        id="401671001",
        name="Dallas Cowboys at Philadelphia Eagles",
        venue_name="Lincoln Financial Field",
        home_team="PHI",
        away_team="DAL",
        date="2026-09-13T17:00Z",
        is_started=False,
        is_final=False,
    )
    eval_res = engine.evaluate_player(
        player=player,
        nfl_game=game,
        actual_points=0.0,
        lineup_locked=False,
    )
    assert eval_res.game_status == "UPCOMING"
    assert eval_res.is_started is False
    assert eval_res.is_final is False
    assert eval_res.effective_points == eval_res.projected_points
    assert eval_res.actual_points == 0.0


def test_scoring_engine_live_game():
    """When a game is in-progress, game_status is LIVE and effective_points reflects live actual_points."""
    engine = StartSitScoringEngine()
    player = PlayerModel(
        id=102,
        full_name="Amon-Ra St. Brown",
        position="WR",
        pro_team="DET",
        projected_points=16.8,
        injury_status="ACTIVE",
    )
    game = NFLGame(
        id="401671002",
        name="Chicago Bears at Detroit Lions",
        venue_name="Ford Field",
        home_team="DET",
        away_team="CHI",
        date="2026-09-13T17:00Z",
        is_started=True,
        is_final=False,
    )
    eval_res = engine.evaluate_player(
        player=player,
        nfl_game=game,
        actual_points=12.4,
        lineup_locked=True,
    )
    assert eval_res.game_status == "LIVE"
    assert eval_res.is_started is True
    assert eval_res.is_final is False
    assert eval_res.effective_points == 12.4
    assert eval_res.actual_points == 12.4


def test_scoring_engine_final_game():
    """When a game has concluded, game_status is FINAL and effective_points is the official actual_points."""
    engine = StartSitScoringEngine()
    player = PlayerModel(
        id=103,
        full_name="Derrick Henry",
        position="RB",
        pro_team="BAL",
        projected_points=17.2,
        injury_status="ACTIVE",
    )
    game = NFLGame(
        id="401671003",
        name="Baltimore Ravens at Kansas City Chiefs",
        venue_name="GEHA Field at Arrowhead Stadium",
        home_team="KC",
        away_team="BAL",
        date="2026-09-10T20:20Z",
        is_started=True,
        is_final=True,
    )
    eval_res = engine.evaluate_player(
        player=player,
        nfl_game=game,
        actual_points=26.4,
        lineup_locked=True,
    )
    assert eval_res.game_status == "FINAL"
    assert eval_res.is_started is True
    assert eval_res.is_final is True
    assert eval_res.effective_points == 26.4
    assert eval_res.actual_points == 26.4


def test_scoring_engine_locked_fallback():
    """If nfl_game object is missing, locked with points transitions to LIVE/effective actuals."""
    engine = StartSitScoringEngine()
    player = PlayerModel(
        id=104,
        full_name="Rashee Rice",
        position="WR",
        pro_team="KC",
        projected_points=14.0,
        injury_status="ACTIVE",
    )
    eval_res = engine.evaluate_player(
        player=player,
        nfl_game=None,
        actual_points=19.3,
        lineup_locked=True,
    )
    assert eval_res.game_status == "LIVE"
    assert eval_res.effective_points == 19.3
    assert eval_res.actual_points == 19.3


def test_optimizer_effective_and_actual_totals():
    """LineupOptimizer must compute total_actual_points and total_effective_points across starters."""
    optimizer = LineupOptimizer()
    dummy_components = ComponentScores(
        projection_score=80.0,
        opportunity_score=80.0,
        matchup_score=80.0,
        environment_score=80.0,
        health_score=80.0,
        weather_score=80.0,
    )

    def make_eval(pid, name, pos, proj, actual=0.0, status="UPCOMING", is_final=False):
        eff = actual if (status in ("FINAL", "LIVE") or is_final) else proj
        return StartSitEvaluation(
            player_id=pid,
            full_name=name,
            position=pos,
            pro_team="KC",
            projected_points=proj,
            actual_points=actual,
            lineup_locked=(status in ("FINAL", "LIVE")),
            is_started=(status in ("FINAL", "LIVE")),
            is_final=is_final,
            game_status=status,
            effective_points=eff,
            start_score=85.0,
            confidence="HIGH",
            recommendation="START",
            matchup_grade="FAVORABLE",
            opponent="BAL",
            is_home=True,
            implied_team_total=27.5,
            injury_status="ACTIVE",
            weather_summary=None,
            reasons_positive=[],
            reasons_negative=[],
            components=dummy_components,
        )

    # 1 QB (Final, scored 25.0 actual vs 20.0 proj)
    qb = make_eval(1, "Patrick Mahomes", "QB", 20.0, actual=25.0, status="FINAL", is_final=True)
    # 2 RBs (1 Final scored 18.0 actual, 1 Upcoming proj 15.0)
    rb1 = make_eval(2, "Isiah Pacheco", "RB", 14.0, actual=18.0, status="FINAL", is_final=True)
    rb2 = make_eval(3, "Breece Hall", "RB", 15.0, actual=0.0, status="UPCOMING", is_final=False)
    # 2 WRs (1 Live scored 10.0 actual, 1 Upcoming proj 16.0)
    wr1 = make_eval(4, "Xavier Worthy", "WR", 12.0, actual=10.0, status="LIVE", is_final=False)
    wr2 = make_eval(5, "Garrett Wilson", "WR", 16.0, actual=0.0, status="UPCOMING", is_final=False)
    # 1 TE (Upcoming proj 11.0)
    te = make_eval(6, "Travis Kelce", "TE", 11.0, actual=0.0, status="UPCOMING", is_final=False)
    # 1 FLEX (Upcoming proj 10.0)
    flex = make_eval(7, "Devon Achane", "RB", 10.0, actual=0.0, status="UPCOMING", is_final=False)
    # 1 K (Final scored 9.0)
    k = make_eval(8, "Harrison Butker", "K", 8.0, actual=9.0, status="FINAL", is_final=True)
    # 1 D/ST (Upcoming proj 7.0)
    dst = make_eval(9, "Chiefs D/ST", "D/ST", 7.0, actual=0.0, status="UPCOMING", is_final=False)

    bench = [make_eval(10, "Backup RB", "RB", 5.0)]

    roster = [qb, rb1, rb2, wr1, wr2, te, flex, k, dst] + bench
    res = optimizer.optimize_lineup(
        team_id=1,
        evaluations=roster,
        roster_slots_config={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "D/ST": 1, "BE": 7, "IR": 1},
        opponent_projected_points=110.0,
    )

    # Expected Actuals: 25.0 (QB) + 18.0 (RB1) + 10.0 (WR1) + 9.0 (K) = 62.0
    assert res.total_actual_points == 62.0
    # Expected Effective: 25.0 + 18.0 + 15.0 + 10.0 + 16.0 + 11.0 + 10.0 + 9.0 + 7.0 = 121.0
    assert res.total_effective_points == 121.0
    # Implied spread against opponent (110.0): 121.0 - 110.0 = +11.0
    assert res.implied_matchup_spread == 11.0
