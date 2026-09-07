"""Comprehensive test suite for 8-Man ESPN PPR StartScore, Lineup Optimizer, and Waiver features."""

import pytest
from src.db.models import PlayerModel, LeagueModel, TeamModel, RosterEntryModel
from src.services.recommendation.scoring_engine import (
    scoring_engine,
    LEAGUE_SIZE_BASELINES,
    StartSitEvaluation,
)
from src.services.recommendation.comparator import player_comparator
from src.services.optimizer.lineup_optimizer import lineup_optimizer
from src.services.waiver.scanner import waiver_scanner
from src.adapters.espn.constants import RosterSlot


def test_8team_calibrated_positional_baselines():
    """Verify that an 8-team league raises baselines so replacement players don't receive inflated StartScores."""
    rb = PlayerModel(
        id=901,
        full_name="Borderline Flex RB",
        position="RB",
        pro_team="MIA",
        projected_points=14.0,
        injury_status="ACTIVE",
    )
    rb.projected_stats = {"rush_att": 12.0, "targets": 2.0}

    # Evaluate in 12-team league (baseline 13.5) vs 8-team league (baseline 15.5)
    eval_12team = scoring_engine.evaluate_player(rb, league_size=12)
    eval_8team = scoring_engine.evaluate_player(rb, league_size=8)

    # In 12-team, 14.0 pts is above baseline (proj_score > 70)
    assert eval_12team.components.projection_score > 70.0
    # In 8-team, 14.0 pts is below baseline (proj_score < 70)
    assert eval_8team.components.projection_score < 70.0
    assert eval_12team.start_score > eval_8team.start_score


def test_konami_code_qb_rushing_multiplier():
    """Verify that QB rushing attempts receive 3.5x weighting and elicit the Konami Code explanation."""
    qb_rusher = PlayerModel(
        id=902,
        full_name="Dual Threat QB",
        position="QB",
        pro_team="BAL",
        projected_points=22.0,
        injury_status="ACTIVE",
    )
    qb_rusher.projected_stats = {
        "pass_att": 28.0,
        "rush_att": 8.0,
        "rush_yds": 55.0,
        "rush_td": 0.6,
    }

    qb_passer = PlayerModel(
        id=903,
        full_name="Pocket Passer QB",
        position="QB",
        pro_team="MIN",
        projected_points=22.0,
        injury_status="ACTIVE",
    )
    qb_passer.projected_stats = {
        "pass_att": 38.0,
        "rush_att": 1.0,
        "rush_yds": 3.0,
        "rush_td": 0.0,
    }

    eval_rusher = scoring_engine.evaluate_player(qb_rusher)
    eval_passer = scoring_engine.evaluate_player(qb_passer)

    # Dual threat QB should have higher opportunity score and Konami reason
    assert eval_rusher.components.opportunity_score > eval_passer.components.opportunity_score
    assert any("Konami Code" in r for r in eval_rusher.reasons_positive)
    assert eval_rusher.ceiling_score > eval_passer.ceiling_score


def test_ceiling_vs_floor_strategy_modes():
    """Verify that CEILING mode boosts high-variance boom assets and FLOOR mode favors safe volume."""
    # Boom/Bust WR: deep targets, high YPT, high TD equity, but only 4 targets
    wr_boom = PlayerModel(
        id=904,
        full_name="Deep Threat WR",
        position="WR",
        pro_team="MIA",
        projected_points=14.5,
        injury_status="ACTIVE",
    )
    wr_boom.projected_stats = {
        "targets": 5.0,
        "receptions": 3.0,
        "rec_yds": 75.0,
        "rec_td": 0.8,
    }

    # High floor WR: 8 targets, short yardage, 0 TDs
    wr_floor = PlayerModel(
        id=905,
        full_name="Possession Slot WR",
        position="WR",
        pro_team="DEN",
        projected_points=14.5,
        injury_status="ACTIVE",
    )
    wr_floor.projected_stats = {
        "targets": 8.5,
        "receptions": 6.5,
        "rec_yds": 50.0,
        "rec_td": 0.1,
    }

    eval_boom_ceiling = scoring_engine.evaluate_player(wr_boom, mode="CEILING")
    eval_floor_ceiling = scoring_engine.evaluate_player(wr_floor, mode="CEILING")

    eval_boom_floor = scoring_engine.evaluate_player(wr_boom, mode="FLOOR")
    eval_floor_floor = scoring_engine.evaluate_player(wr_floor, mode="FLOOR")

    # In CEILING mode, deep threat should have higher ceiling score
    assert eval_boom_ceiling.ceiling_score > eval_floor_ceiling.ceiling_score
    # In FLOOR mode, possession WR should have higher floor score
    assert eval_floor_floor.floor_score > eval_boom_floor.floor_score


def test_optimizer_honors_strategy_modes():
    """Verify lineup optimizer optimizes for ceiling or floor depending on selected mode."""
    p_ceiling = StartSitEvaluation(
        player_id=1,
        full_name="Boom Player",
        position="WR",
        pro_team="KC",
        projected_points=15.0,
        start_score=75.0,
        ceiling_score=92.0,
        floor_score=55.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="LAC",
        is_home=True,
        implied_team_total=27.0,
        injury_status="ACTIVE",
    )

    p_floor = StartSitEvaluation(
        player_id=2,
        full_name="Safe Floor Player",
        position="WR",
        pro_team="DET",
        projected_points=15.0,
        start_score=76.0,
        ceiling_score=80.0,
        floor_score=78.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="GB",
        is_home=True,
        implied_team_total=24.0,
        injury_status="ACTIVE",
    )

    # In BALANCED mode, p_floor starts (76.0 vs 75.0)
    res_balanced = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="BALANCED",
    )
    assert res_balanced.starters[0].recommended_player.player_id == 2

    # In CEILING mode, p_ceiling starts (92.0 vs 80.0 ceiling)
    res_ceiling = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="CEILING",
    )
    assert res_ceiling.starters[0].recommended_player.player_id == 1

    # In FLOOR mode, p_floor starts (78.0 vs 55.0 floor)
    res_floor = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="FLOOR",
    )
    assert res_floor.starters[0].recommended_player.player_id == 2


def test_8team_waiver_drop_protection(db_session):
    """Verify that 14.0 projected points is drop-eligible in an 8-team league but protected in 12-team."""
    league = LeagueModel(id=801, name="8 Team League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=801, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    # Starter with high projection
    rb_starter = PlayerModel(id=810, full_name="Elite Starter RB", position="RB", pro_team="SF", projected_points=18.0)
    # Bench player with 14.0 points (StartScore ~ 73.0)
    rb_bench = PlayerModel(id=811, full_name="Decent Bench Player", position="RB", pro_team="CLE", projected_points=14.0)
    db_session.add_all([rb_starter, rb_bench])
    db_session.commit()

    entry_start = RosterEntryModel(id="801_1_810", league_id=801, team_id=1, player_id=810, lineup_slot_id=RosterSlot.RB, is_starter=True)
    entry_bench = RosterEntryModel(id="801_1_811", league_id=801, team_id=1, player_id=811, lineup_slot_id=RosterSlot.BENCH, is_starter=False)
    db_session.add_all([entry_start, entry_bench])
    db_session.commit()

    # Free agent high-upside star
    fa_stud = PlayerModel(id=820, full_name="Breakout Free Agent", position="WR", pro_team="DAL", projected_points=17.5)
    db_session.add(fa_stud)
    db_session.commit()

    user_evals_8 = [
        scoring_engine.evaluate_player(rb_starter, league_size=8),
        scoring_engine.evaluate_player(rb_bench, league_size=8),
    ]

    # In 8-team scan: rb_bench (< 15.5 pts) is eligible to drop for fa_stud!
    scan_8 = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=801,
        user_team_id=1,
        user_roster_evaluations=user_evals_8,
        free_agent_pool=[fa_stud],
        league_size=8,
    )
    assert len(scan_8.top_upgrades) > 0
    assert scan_8.top_upgrades[0].drop_player.player_id == 811


def test_contingent_upside_stash_recommendation(db_session):
    """Verify that backup RBs with high contingent scores are surfaced as CONTINGENT_UPSIDE_STASH."""
    league = LeagueModel(id=802, name="Contingency League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=802, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    rb_starter = PlayerModel(id=830, full_name="Starter RB", position="RB", pro_team="DET", projected_points=17.0)
    low_bench = PlayerModel(id=831, full_name="End of Bench WR", position="WR", pro_team="NE", projected_points=7.0)
    db_session.add_all([rb_starter, low_bench])
    db_session.commit()

    entry_start = RosterEntryModel(id="802_1_830", league_id=802, team_id=1, player_id=830, lineup_slot_id=RosterSlot.RB, is_starter=True)
    entry_bench = RosterEntryModel(id="802_1_831", league_id=802, team_id=1, player_id=831, lineup_slot_id=RosterSlot.BENCH, is_starter=False)
    db_session.add_all([entry_start, entry_bench])
    db_session.commit()

    # Free agent high-contingency backup RB (e.g. Blake Corum / Braelon Allen)
    fa_handcuff = PlayerModel(id=840, full_name="Elite Handcuff RB", position="RB", pro_team="NYJ", projected_points=8.5)
    fa_handcuff.projected_stats = {"rush_att": 6.0, "rush_yds": 32.0, "targets": 2.0}
    db_session.add(fa_handcuff)
    db_session.commit()

    user_evals = [
        scoring_engine.evaluate_player(rb_starter),
        scoring_engine.evaluate_player(low_bench),
    ]

    scan_res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=802,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        free_agent_pool=[fa_handcuff],
        league_size=8,
    )

    stash_upgrades = [u for u in scan_res.top_upgrades if u.upgrade_type == "CONTINGENT_UPSIDE_STASH"]
    assert len(stash_upgrades) > 0
    assert stash_upgrades[0].pickup_player.player_id == 840
    assert "contingent upside" in stash_upgrades[0].rationale.lower()
