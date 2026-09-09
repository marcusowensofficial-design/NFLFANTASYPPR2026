"""Tests for the Institutional Quant Projection Engine and Bulk Calibration."""

import pytest
from src.adapters.espn.schemas import ItemizedStatLine
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.services.recommendation.projection_engine import (
    ecr_to_projected_ppr,
    get_dst_points_allowed_score,
    quant_projection_engine,
)


def test_ecr_to_projected_ppr_curves():
    """Verify non-linear exponential and power decay curves by position."""
    # QB curve
    qb1 = ecr_to_projected_ppr(1, "QB")
    qb12 = ecr_to_projected_ppr(12, "QB")
    qb24 = ecr_to_projected_ppr(24, "QB")
    assert 22.0 <= qb1 <= 24.5
    assert 16.0 <= qb12 <= 18.0
    assert 12.5 <= qb24 <= 14.5
    assert qb1 > qb12 > qb24

    # RB curve
    rb1 = ecr_to_projected_ppr(1, "RB")
    rb12 = ecr_to_projected_ppr(12, "RB")
    rb24 = ecr_to_projected_ppr(24, "RB")
    assert 20.0 <= rb1 <= 23.0
    assert 13.0 <= rb12 <= 15.5
    assert 9.5 <= rb24 <= 11.5
    assert rb1 > rb12 > rb24

    # WR curve
    wr1 = ecr_to_projected_ppr(1, "WR")
    wr12 = ecr_to_projected_ppr(12, "WR")
    wr24 = ecr_to_projected_ppr(24, "WR")
    assert 20.0 <= wr1 <= 22.5
    assert 13.5 <= wr12 <= 15.5
    assert 10.5 <= wr24 <= 12.5
    assert wr1 > wr12 > wr24

    # TE cliff
    te1 = ecr_to_projected_ppr(1, "TE")
    te12 = ecr_to_projected_ppr(12, "TE")
    assert 14.5 <= te1 <= 17.0
    assert 7.0 <= te12 <= 9.0
    assert te1 > te12

    # DST curve
    dst1 = ecr_to_projected_ppr(1, "DST")
    dst12 = ecr_to_projected_ppr(12, "DST")
    assert 9.5 <= dst1 <= 11.5
    assert 6.0 <= dst12 <= 7.5
    assert dst1 > dst12


def test_dst_points_allowed_brackets():
    """Verify standard NFL fantasy D/ST points-allowed brackets."""
    assert get_dst_points_allowed_score(0.0) == 5.0
    assert get_dst_points_allowed_score(3.0) == 4.0
    assert get_dst_points_allowed_score(10.0) == 3.0
    assert get_dst_points_allowed_score(15.0) == 1.0
    assert get_dst_points_allowed_score(21.0) == 0.0
    assert get_dst_points_allowed_score(30.0) == -1.0
    assert get_dst_points_allowed_score(38.0) == -4.0


def test_exact_mathematical_statline_invariance():
    """Verify that itemized statline calculation strictly matches target projection."""
    # Offensive player
    base_stats = ItemizedStatLine(
        pass_att=35.0,
        pass_cmp=23.0,
        pass_yds=260.0,
        pass_td=1.8,
        pass_int=0.7,
        rush_att=4.0,
        rush_yds=20.0,
        rush_td=0.2,
    )
    target_pts = 19.45
    reconciled = quant_projection_engine._reconcile_itemized_to_points(base_stats, target_pts, "QB")
    calc_ppr = quant_projection_engine._calculate_ppr(reconciled, "QB")
    assert abs(calc_ppr - target_pts) < 0.001

    # D/ST unit
    dst_stats = ItemizedStatLine(
        sacks=3.2,
        turnovers=1.4,
        def_td=0.15,
        pts_allowed=16.5,
    )
    dst_target = 8.75
    reconciled_dst = quant_projection_engine._reconcile_itemized_to_points(dst_stats, dst_target, "D/ST")
    calc_dst = quant_projection_engine._calculate_ppr(reconciled_dst, "D/ST")
    assert abs(calc_dst - dst_target) < 0.001


def test_inactive_player_zero_projection():
    """Verify that players marked OUT or IR receive 0.0 points and zeroed stats."""
    player_out = PlayerModel(
        id=999991,
        full_name="Injured Star",
        position="RB",
        pro_team="KC",
        injury_status="OUT",
        injured=True,
        projected_points=16.5,
    )
    res = quant_projection_engine.calculate_player_projection(player_out)
    assert res.projected_points == 0.0
    assert res.model_points == 0.0
    assert res.consensus_points == 0.0
    assert res.itemized_stats.calculated_ppr == 0.0
    assert res.itemized_stats.rush_att == 0.0


def test_active_player_full_projection():
    """Verify active player generates complete projection with Vegas and DvP factors."""
    game = NFLGame(
        id="test_game_1",
        name="NE at SEA",
        date="2026-09-10T00:20Z",
        venue_name="Lumen Field",
        is_dome=False,
        home_team="SEA",
        away_team="NE",
        over_under=44.0,
        spread=-4.5,
        home_implied_total=24.25,
        away_implied_total=19.75,
    )
    player = PlayerModel(
        id=999992,
        full_name="Jaxon Smith-Njigba",
        position="WR",
        pro_team="SEA",
        injury_status="ACTIVE",
        injured=False,
        projected_points=18.5,
        fp_rank_ecr=4,
        fp_pos_rank="WR4",
    )
    res = quant_projection_engine.calculate_player_projection(player, nfl_game=game)
    assert res.projected_points > 15.0
    assert res.model_points > 15.0
    assert res.consensus_points > 15.0
    assert res.itemized_stats.targets > 5.0
    assert res.itemized_stats.rec_yds > 50.0
    # Mathematical invariance
    calc_ppr = quant_projection_engine._calculate_ppr(res.itemized_stats, "WR")
    assert abs(calc_ppr - res.projected_points) < 0.001
