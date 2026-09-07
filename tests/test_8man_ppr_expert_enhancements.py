"""Comprehensive test suite verifying World-Class 8-Man PPR Expert Enhancements:
1. Recommendation Threshold Calibration for 8-man league talent density
2. Positional Stud Invariance (Top-10 RBs, Top-12 WRs, Top-5 QBs, Top-4 TEs)
3. 8-Man PPR Leverage and Trap factor tagging
4. Bye-Week and Consensus Stud Drop Protection in Waiver Scanner
5. Full PPR FLEX Tactical Allocation (Target volume preference)
6. Comparator Head-to-Head PPR Rationale
7. Dynamic Live-Wire VORP calculation
"""

import pytest
from src.adapters.espn.constants import RosterSlot
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.services.optimizer.lineup_optimizer import lineup_optimizer
from src.services.recommendation.comparator import player_comparator
from src.services.recommendation.scoring_engine import (
    LEAGUE_SIZE_BASELINES,
    StartSitEvaluation,
    scoring_engine,
)
from src.services.waiver.scanner import waiver_scanner


def test_8man_recommendation_category_calibration():
    """Verify that in 8-team leagues, low-60s scores are calibrated to BENCH or TOSS-UP, not inflated starts."""
    # A borderline player with ~62 StartScore
    p_bubble = PlayerModel(
        id=701,
        full_name="Bubble Player",
        position="WR",
        pro_team="LV",
        projected_points=12.0,
        injury_status="ACTIVE",
    )
    p_bubble.projected_stats = {"targets": 4.5, "receptions": 3.0, "rec_yds": 40.0}

    eval_8 = scoring_engine.evaluate_player(p_bubble, league_size=8)
    eval_12 = scoring_engine.evaluate_player(p_bubble, league_size=12)

    # In 8-team league, a ~58-63 score must be BENCH or TOSS-UP, never START
    assert eval_8.recommendation in ("BENCH", "TOSS-UP")
    # In 8-team league, baselines ensure stricter start standards
    assert eval_8.start_score < eval_12.start_score


def test_positional_stud_invariance_against_tough_defense():
    """Verify that a player designated as WR8 or RB5 receives MATCHUP_RESILIENT_STUD and positive invariance reason."""
    tough_game = NFLGame(
        id="999",
        name="DAL vs NYJ",
        date="2026-09-13T17:00Z",
        venue_name="MetLife Stadium",
        is_dome=False,
        home_team="NYJ",
        away_team="DAL",
        over_under=41.0,
        spread=3.5,
        home_implied_total=22.0,
        away_implied_total=18.5,
    )

    stud_wr = PlayerModel(
        id=702,
        full_name="Alpha Stud WR",
        position="WR",
        pro_team="DAL",
        projected_points=15.5,
        injury_status="ACTIVE",
    )
    stud_wr.fp_pos_rank = "WR7"
    stud_wr.projected_stats = {"targets": 9.0, "receptions": 6.5, "rec_yds": 85.0, "rec_td": 0.6}

    eval_stud = scoring_engine.evaluate_player(stud_wr, nfl_game=tough_game, league_size=8)

    assert eval_stud.matchup_resilience == "MATCHUP_RESILIENT_STUD"
    assert any("8-Man Locked Stud" in r for r in eval_stud.reasons_positive)
    assert any("Alpha volume insulation" in r for r in eval_stud.reasons_positive)
    assert eval_stud.recommendation in ("STRONG START", "START")


def test_8man_ppr_leverage_and_trap_reasons():
    """Verify that heavy target volume generates [8-Man PPR Leverage] and rush-only roles generate [8-Man PPR Trap]."""
    target_alpha = PlayerModel(
        id=703,
        full_name="Target Alpha WR",
        position="WR",
        pro_team="DET",
        projected_points=17.0,
        injury_status="ACTIVE",
    )
    target_alpha.projected_stats = {"targets": 9.5, "receptions": 7.0, "rec_yds": 90.0, "rec_td": 0.7}

    rush_plodder = PlayerModel(
        id=704,
        full_name="Early Down Plodder",
        position="RB",
        pro_team="WAS",
        projected_points=10.5,
        injury_status="ACTIVE",
    )
    rush_plodder.projected_stats = {"rush_att": 14.0, "rush_yds": 58.0, "rush_td": 0.4, "targets": 0.5}

    eval_alpha = scoring_engine.evaluate_player(target_alpha, league_size=8)
    eval_plodder = scoring_engine.evaluate_player(rush_plodder, league_size=8)

    # Check for 8-Man PPR Leverage
    assert any("[8-Man PPR Leverage]" in r for r in eval_alpha.reasons_positive)
    # Check for 8-Man PPR Trap
    assert any("[8-Man PPR Trap]" in r for r in eval_plodder.reasons_negative)


def test_bye_week_stud_drop_protection(db_session):
    """Verify that an elite stud on a BYE week (0 projected points) is NEVER recommended as a drop candidate."""
    league = LeagueModel(id=899, name="Expert 8-Man League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=899, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    # Starter active
    rb_active = PlayerModel(id=710, full_name="Active Starter RB", position="RB", pro_team="SF", projected_points=18.0)
    # Stud on BYE on bench (e.g. CeeDee Lamb or Breece Hall on Week 7 bye)
    stud_on_bye = PlayerModel(
        id=711,
        full_name="Superstar On Bye",
        position="WR",
        pro_team="DAL",
        projected_points=0.0,
    )
    stud_on_bye.fp_ecr = 12
    stud_on_bye.fp_pos_rank = "WR4"
    stud_on_bye.fp_tier = 1

    # End-of-bench expendable player
    expendable_bench = PlayerModel(
        id=712,
        full_name="Expendable Bench Player",
        position="WR",
        pro_team="CAR",
        projected_points=8.0,
    )
    expendable_bench.fp_ecr = 145
    expendable_bench.fp_pos_rank = "WR65"

    db_session.add_all([rb_active, stud_on_bye, expendable_bench])
    db_session.commit()

    entry_start = RosterEntryModel(id="899_1_710", league_id=899, team_id=1, player_id=710, lineup_slot_id=RosterSlot.RB, is_starter=True)
    entry_bye = RosterEntryModel(id="899_1_711", league_id=899, team_id=1, player_id=711, lineup_slot_id=RosterSlot.BENCH, is_starter=False)
    entry_exp = RosterEntryModel(id="899_1_712", league_id=899, team_id=1, player_id=712, lineup_slot_id=RosterSlot.BENCH, is_starter=False)
    db_session.add_all([entry_start, entry_bye, entry_exp])
    db_session.commit()

    # Free agent streamer
    fa_pickup = PlayerModel(id=720, full_name="Streaming Pickup", position="WR", pro_team="MIA", projected_points=14.5)
    db_session.add(fa_pickup)
    db_session.commit()

    user_evals = [
        scoring_engine.evaluate_player(rb_active, league_size=8),
        scoring_engine.evaluate_player(stud_on_bye, league_size=8),
        scoring_engine.evaluate_player(expendable_bench, league_size=8),
    ]

    scan_res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=899,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        free_agent_pool=[fa_pickup],
        league_size=8,
    )

    # Must find an upgrade
    assert len(scan_res.top_upgrades) > 0
    # The drop player MUST be the expendable player (id 712), NEVER the superstar on bye (id 711)!
    drop_pids = [u.drop_player.player_id for u in scan_res.top_upgrades if u.drop_player]
    assert 711 not in drop_pids
    assert 712 in drop_pids


def test_full_ppr_flex_tactical_allocation():
    """Verify that in full PPR, a high-target WR is prioritized for FLEX over a low-target RB with identical StartScore."""
    # RB with 14.5 pts, low targets (2 down back)
    rb_rush = StartSitEvaluation(
        player_id=730,
        full_name="Between Tackles RB",
        position="RB",
        pro_team="WAS",
        projected_points=14.5,
        start_score=75.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="NYG",
        is_home=True,
        implied_team_total=22.0,
        injury_status="ACTIVE",
        itemized_stats={"rush_att": 16.0, "targets": 1.5, "receptions": 1.0},
    )

    # WR with 14.5 pts, 8.5 targets (high reception floor)
    wr_targets = StartSitEvaluation(
        player_id=731,
        full_name="High Target WR",
        position="WR",
        pro_team="GB",
        projected_points=14.5,
        start_score=75.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="CHI",
        is_home=True,
        implied_team_total=23.0,
        injury_status="ACTIVE",
        itemized_stats={"targets": 8.5, "receptions": 6.0, "rec_yds": 65.0},
    )

    # 1 FLEX slot only (explicitly zero out primary RB and WR slots so players compete directly for FLEX)
    res = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"RB": 0, "WR": 0, "TE": 0, "FLEX": 1, "QB": 0, "D/ST": 0, "K": 0},
        evaluations=[rb_rush, wr_targets],
        mode="BALANCED",
    )

    # High target WR should win the flex allocation due to PPR reception floor bonus
    assert res.starters[0].recommended_player.player_id == 731
    assert res.starters[0].slot_name == "FLEX"


def test_comparator_head_to_head_ppr_rationale():
    """Verify that player comparator breaks down head-to-head target volume and tier deltas."""
    p_winner = StartSitEvaluation(
        player_id=740,
        full_name="Winner WR",
        position="WR",
        pro_team="MIN",
        projected_points=16.5,
        start_score=80.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="DET",
        is_home=True,
        implied_team_total=26.0,
        injury_status="ACTIVE",
        fp_tier=2,
        volume_share=28.0,
        itemized_stats={"targets": 9.5, "receptions": 7.0, "rec_yds": 95.0, "rec_td": 0.7},
    )

    p_runner_up = StartSitEvaluation(
        player_id=741,
        full_name="Runner Up WR",
        position="WR",
        pro_team="HOU",
        projected_points=15.8,
        start_score=78.5,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="IND",
        is_home=True,
        implied_team_total=24.0,
        injury_status="ACTIVE",
        fp_tier=3,
        volume_share=21.0,
        itemized_stats={"targets": 6.5, "receptions": 4.5, "rec_yds": 70.0, "rec_td": 0.4},
    )

    comp = player_comparator.compare([p_winner, p_runner_up])

    assert comp.is_close_call is True
    assert comp.recommended_player_id == 740
    # Must contain target volume or volume share or tier in detailed rationale
    assert any(
        term in comp.detailed_rationale.lower()
        for term in ("target volume", "workload share", "tier", "red-zone")
    )


def test_dynamic_live_vorp_computation():
    """Verify that StartSitEvaluation populates live_vorp against the 8-man positional baseline."""
    p = PlayerModel(
        id=750,
        full_name="Elite QB",
        position="QB",
        pro_team="BUF",
        projected_points=24.5,
        injury_status="ACTIVE",
    )
    ev = scoring_engine.evaluate_player(p, league_size=8)
    assert ev.live_vorp is not None
    # Projected ~24.4 - 20.5 (QB baseline in 8-team) = +3.9
    assert 3.8 <= ev.live_vorp <= 4.2
