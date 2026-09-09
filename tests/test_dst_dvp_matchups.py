"""Unit tests verifying that D/ST DvP and matchup ratings are calibrated against opponent offense."""

import pytest
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.services.recommendation.scoring_engine import scoring_engine, ScoringWeights


def test_dst_dvp_rankings_calibrated_against_offenses():
    """Verify that targeting generous offenses (CAR, NYG, TEN) yields top DvP ranks (27-32)
    and avoiding potent offenses (DET, BAL, KC) yields low DvP ranks (1-6)."""
    # Carolina: Bryce Young, sack-heavy, turnover-prone -> Rank 32
    car_rank = dvp_client.get_position_rank("CAR", "D/ST")
    assert car_rank == 32
    assert dvp_client.get_matchup_stars(car_rank) == 5

    # NY Giants: high sack rate -> Rank 31
    nyg_rank = dvp_client.get_position_rank("NYG", "D/ST")
    assert nyg_rank == 31
    assert dvp_client.get_matchup_stars(nyg_rank) == 5

    # Detroit Lions: top offense, elite O-line -> Rank 1
    det_rank = dvp_client.get_position_rank("DET", "D/ST")
    assert det_rank == 1
    assert dvp_client.get_matchup_stars(det_rank) == 1

    # Kansas City: Mahomes, low turnovers -> Rank 3
    kc_rank = dvp_client.get_position_rank("KC", "D/ST")
    assert kc_rank <= 5
    assert dvp_client.get_matchup_stars(kc_rank) == 1


def test_dst_matchup_score_and_grades():
    """Verify that DvP matchup score awards FAVORABLE/ELITE for streaming vs weak offenses
    and TOUGH/BRUTAL for facing elite offenses."""
    car_score, car_grade = dvp_client.calculate_matchup_score("CAR", "D/ST")
    assert car_score >= 76.0
    assert car_grade in ("ELITE", "FAVORABLE")

    det_score, det_grade = dvp_client.calculate_matchup_score("DET", "D/ST")
    assert det_score <= 58.0
    assert det_grade in ("TOUGH", "BRUTAL")


def test_dst_overall_off_rank_accessor():
    """Verify get_overall_off_rank accurately reflects offensive power."""
    assert dvp_client.get_overall_off_rank("DET") == 1
    assert dvp_client.get_overall_off_rank("BAL") == 2
    assert dvp_client.get_overall_off_rank("CAR") == 32
    assert dvp_client.get_overall_off_rank("UNKNOWN") == 16


def test_dst_scoring_engine_evaluation_reasons_and_off_rank():
    """Verify scoring engine populates opp_off_rank and appropriate streaming reasons for D/ST."""
    dst_player = PlayerModel(
        id=901,
        full_name="Broncos D/ST",
        position="D/ST",
        pro_team="DEN",
        projected_points=8.5,
        injury_status="ACTIVE",
    )
    favorable_game = NFLGame(
        id="9001",
        name="CAR at DEN",
        date="2026-09-10T20:00:00Z",
        venue_name="Empower Field",
        home_team="DEN",
        away_team="CAR",
        spread=-7.0,
        over_under=39.5,
        home_implied_total=23.25,
        away_implied_total=16.25,
    )

    eval_result = scoring_engine.evaluate_player(
        player=dst_player,
        nfl_game=favorable_game,
    )

    assert eval_result.opp_dvp_rank == 32
    assert eval_result.opp_off_rank == 32
    assert eval_result.matchup_stars == 5
    assert eval_result.matchup_grade in ("ELITE", "FAVORABLE")

    # Check reason string explicitly mentions Opp Offense and D/ST
    all_reasons = " ".join(eval_result.reasons_positive)
    assert "streaming matchup vs CAR" in all_reasons
    assert "Opp Offense #32" in all_reasons
    assert "Def rank #" not in all_reasons


def test_dst_tough_matchup_evaluation_reasons():
    """Verify D/ST facing elite offense gets tough matchup warning and opp_off_rank."""
    dst_player = PlayerModel(
        id=902,
        full_name="Cardinals D/ST",
        position="D/ST",
        pro_team="ARI",
        projected_points=4.5,
        injury_status="ACTIVE",
    )
    tough_game = NFLGame(
        id="9002",
        name="DET at ARI",
        date="2026-09-10T20:00:00Z",
        venue_name="State Farm Stadium",
        home_team="ARI",
        away_team="DET",
        spread=6.5,
        over_under=52.5,
        home_implied_total=23.0,
        away_implied_total=29.5,
    )

    eval_result = scoring_engine.evaluate_player(
        player=dst_player,
        nfl_game=tough_game,
    )

    assert eval_result.opp_dvp_rank == 1
    assert eval_result.opp_off_rank == 1
    assert eval_result.matchup_stars == 1
    assert eval_result.matchup_grade in ("TOUGH", "BRUTAL")

    all_neg_reasons = " ".join(eval_result.reasons_negative)
    assert "Opp Offense #1" in all_neg_reasons
