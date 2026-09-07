"""Tests for advanced 8-man expert features: Chronological FLEX, Game Theory Spread, 2-for-1 Trades, and Bench Audit."""

import pytest
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.adapters.espn.constants import RosterSlot
from src.services.recommendation.scoring_engine import (
    StartSitEvaluation,
    scoring_engine,
)
from src.services.optimizer.lineup_optimizer import (
    lineup_optimizer,
    get_kickoff_timestamp,
)
from src.services.trade.trade_analyzer import trade_analyzer
from src.services.waiver.scanner import waiver_scanner


def test_chronological_kickoff_flex_allocation():
    """Verify that the player with the latest kickoff holds the FLEX slot, never a Thursday starter."""
    # RB 1: Thursday Night Football (Earliest)
    rb_tnf = StartSitEvaluation(
        player_id=101,
        full_name="Thursday Star RB",
        position="RB",
        pro_team="KC",
        projected_points=17.5,
        start_score=85.0,
        confidence="HIGH",
        recommendation="STRONG START",
        matchup_grade="FAVORABLE",
        opponent="BAL",
        is_home=True,
        implied_team_total=26.5,
        injury_status="ACTIVE",
        game_date="2026-09-10T20:20Z",  # Thursday kickoff
    )

    # RB 2: Sunday 1:00 PM
    rb_sun = StartSitEvaluation(
        player_id=102,
        full_name="Sunday Midday RB",
        position="RB",
        pro_team="DET",
        projected_points=16.0,
        start_score=82.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="GB",
        is_home=True,
        implied_team_total=24.0,
        injury_status="ACTIVE",
        game_date="2026-09-13T13:00Z",  # Sunday early kickoff
    )

    # RB 3: Monday Night Football (Latest)
    rb_mnf = StartSitEvaluation(
        player_id=103,
        full_name="Monday Night RB",
        position="RB",
        pro_team="SF",
        projected_points=15.5,
        start_score=80.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="NYJ",
        is_home=True,
        implied_team_total=25.0,
        injury_status="ACTIVE",
        game_date="2026-09-14T20:15Z",  # Monday late kickoff
    )

    # WR 1 & 2: Sunday kickoffs
    wr_1 = StartSitEvaluation(
        player_id=201,
        full_name="Sunday WR 1",
        position="WR",
        pro_team="MIN",
        projected_points=18.0,
        start_score=86.0,
        confidence="HIGH",
        recommendation="STRONG START",
        matchup_grade="FAVORABLE",
        opponent="NYG",
        is_home=False,
        implied_team_total=23.0,
        injury_status="ACTIVE",
        game_date="2026-09-13T13:00Z",
    )
    wr_2 = StartSitEvaluation(
        player_id=202,
        full_name="Sunday WR 2",
        position="WR",
        pro_team="DAL",
        projected_points=16.5,
        start_score=83.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="CLE",
        is_home=False,
        implied_team_total=21.5,
        injury_status="ACTIVE",
        game_date="2026-09-13T16:25Z",
    )

    # Optimize with 2 RB, 2 WR, 1 FLEX
    roster_config = {"RB": 2, "WR": 2, "FLEX": 1}
    result = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config=roster_config,
        evaluations=[rb_tnf, rb_sun, rb_mnf, wr_1, wr_2],
    )

    starter_slots = {s.slot_name: s for s in result.starters}
    flex_starter = next(s for s in result.starters if s.slot_name == "FLEX")
    rb_starters = [s for s in result.starters if s.slot_name == "RB"]

    # Monday night player MUST hold the FLEX slot
    assert flex_starter.recommended_player.player_id == 103
    assert flex_starter.is_flex_timing_optimal is True
    assert "Optimal FLEX timing" in flex_starter.flex_timing_note

    # Thursday player MUST be in primary RB slot, never FLEX
    rb_pids = {s.recommended_player.player_id for s in rb_starters}
    assert 101 in rb_pids


def test_current_lineup_flex_timing_risk_alert():
    """Verify that current starting lineups with Thursday players in FLEX trigger tactical alerts."""
    p_tnf = StartSitEvaluation(
        player_id=301,
        full_name="Thursday Flex Hazard",
        position="WR",
        pro_team="MIA",
        projected_points=14.0,
        start_score=78.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="BUF",
        is_home=True,
        implied_team_total=24.0,
        injury_status="ACTIVE",
        game_date="2026-09-10T20:15Z",  # Thursday
    )
    p_sunday = StartSitEvaluation(
        player_id=302,
        full_name="Sunday Primary WR",
        position="WR",
        pro_team="PHI",
        projected_points=16.0,
        start_score=82.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="GB",
        is_home=False,
        implied_team_total=25.0,
        injury_status="ACTIVE",
        game_date="2026-09-13T13:00Z",  # Sunday
    )

    # Current ESPN lineup erroneously has p_tnf in FLEX (slot 23) and p_sunday in WR (slot 4)
    locked_map = {301: RosterSlot.FLEX, 302: RosterSlot.WR}

    result = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"WR": 1, "FLEX": 1},
        evaluations=[p_tnf, p_sunday],
        current_starter_ids={301, 302},
        locked_starter_slot_map=locked_map,
    )

    assert result.flex_timing_risk is True
    assert "Tactical FLEX Lock Alert" in result.flex_timing_warning


def test_game_theory_opponent_spread_auto_mode():
    """Verify that AUTO mode detects underdogs and triggers CEILING, and detects favorites for FLOOR."""
    p1 = StartSitEvaluation(
        player_id=401,
        full_name="Boom Ceiling Asset",
        position="WR",
        pro_team="KC",
        projected_points=15.0,
        start_score=75.0,
        ceiling_score=94.0,
        floor_score=50.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="LAC",
        is_home=True,
        implied_team_total=26.0,
        injury_status="ACTIVE",
    )
    p2 = StartSitEvaluation(
        player_id=402,
        full_name="Safe Floor Asset",
        position="WR",
        pro_team="HOU",
        projected_points=15.0,
        start_score=76.0,
        ceiling_score=79.0,
        floor_score=80.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="IND",
        is_home=True,
        implied_team_total=24.0,
        injury_status="ACTIVE",
    )

    # Underdog scenario: opponent projected at 30.0 pts while our starter projects 15.0 pts (spread -15.0)
    res_underdog = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"WR": 1, "FLEX": 0},
        evaluations=[p1, p2],
        current_starter_ids={402},
        mode="AUTO",
        opponent_projected_points=30.0,
    )
    assert res_underdog.mode == "CEILING"
    assert res_underdog.game_theory_posture == "HEAVY_UNDERDOG_CEILING"
    assert res_underdog.starters[0].recommended_player.player_id == 401  # Boom asset started

    # Heavy Favorite scenario: opponent projected at only 5.0 pts while our starter projects 15.0 pts (spread +10.0)
    res_favorite = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"WR": 1, "FLEX": 0},
        evaluations=[p1, p2],
        current_starter_ids={402},
        mode="AUTO",
        opponent_projected_points=5.0,
    )
    assert res_favorite.mode == "FLOOR"
    assert res_favorite.game_theory_posture == "SUBSTANTIAL_FAVORITE_FLOOR"
    assert res_favorite.starters[0].recommended_player.player_id == 402  # Floor asset started


def test_consolidation_trade_analyzer_2_for_1(db_session):
    """Verify that 2-for-1 trade analyzer recommends targeting Tier-1 Alphas and computes net gain with waiver backfill."""
    league = LeagueModel(id=9901, name="Trade League", season=2026, size=8, user_team_id=1)
    user_team = TeamModel(id=1, league_id=9901, name="My Team", is_user_team=True)
    rival_team = TeamModel(id=2, league_id=9901, name="Rival Alpha Hoarder", is_user_team=False)
    db_session.add_all([league, user_team, rival_team])

    # Rival has Tier-1 Alpha: Ja'Marr Chase (WR, 21.0 pts) and a terrible RB2 (8.0 pts)
    chase = PlayerModel(id=5001, full_name="Ja'Marr Chase", position="WR", pro_team="CIN", projected_points=21.0)
    chase.projected_stats = {"targets": 11.0, "receptions": 8.0, "rec_yds": 105.0, "rec_td": 0.8}
    weak_rb = PlayerModel(id=5002, full_name="Subpar Starter RB", position="RB", pro_team="CAR", projected_points=8.0)
    weak_rb.projected_stats = {"rush_att": 8.0, "rush_yds": 28.0, "targets": 1.0}
    db_session.add_all([chase, weak_rb])
    db_session.commit()

    entry_chase = RosterEntryModel(id="9901_2_5001", league_id=9901, team_id=2, player_id=5001, lineup_slot_id=RosterSlot.WR, is_starter=True)
    entry_weak = RosterEntryModel(id="9901_2_5002", league_id=9901, team_id=2, player_id=5002, lineup_slot_id=RosterSlot.RB, is_starter=True)
    db_session.add_all([entry_chase, entry_weak])

    # User has solid WR2 (16.0 pts) and solid RB2 (15.5 pts)
    user_wr = PlayerModel(id=6001, full_name="DeVonta Smith", position="WR", pro_team="PHI", projected_points=16.0)
    user_wr.projected_stats = {"targets": 8.0, "receptions": 5.5, "rec_yds": 75.0, "rec_td": 0.5}
    user_rb = PlayerModel(id=6002, full_name="James Cook", position="RB", pro_team="BUF", projected_points=15.5)
    user_rb.projected_stats = {"rush_att": 14.0, "rush_yds": 65.0, "targets": 4.0, "receptions": 3.0, "rec_yds": 25.0, "rush_td": 0.6}
    db_session.add_all([user_wr, user_rb])
    db_session.commit()

    entry_uwr = RosterEntryModel(id="9901_1_6001", league_id=9901, team_id=1, player_id=6001, lineup_slot_id=RosterSlot.WR, is_starter=True)
    entry_urb = RosterEntryModel(id="9901_1_6002", league_id=9901, team_id=1, player_id=6002, lineup_slot_id=RosterSlot.RB, is_starter=False)  # on bench
    db_session.add_all([entry_uwr, entry_urb])

    # Free agent wire backfill (13.0 pts available on waivers)
    fa_wire = PlayerModel(id=7001, full_name="Top Free Agent WR", position="WR", pro_team="LAC", projected_points=13.0)
    fa_wire.projected_stats = {"targets": 6.5, "receptions": 4.5, "rec_yds": 55.0, "rec_td": 0.4}
    db_session.add(fa_wire)
    db_session.commit()

    user_evals = [
        scoring_engine.evaluate_player(user_wr, league_size=8),
        scoring_engine.evaluate_player(user_rb, league_size=8),
    ]

    trade_res = trade_analyzer.analyze_consolidation_trades(
        db=db_session,
        league_id=9901,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        free_agent_pool=[fa_wire],
        league_size=8,
    )

    assert trade_res.total_trades_analyzed > 0
    assert len(trade_res.recommendations) > 0
    top_rec = trade_res.recommendations[0]
    assert top_rec.target_alpha.full_name == "Ja'Marr Chase"
    assert top_rec.user_net_projected_delta > 0
    assert "Consolidates depth into Tier-1 Alpha" in top_rec.rationale


def test_8man_roster_architecture_bench_audit(db_session):
    """Verify that carrying a backup Kicker or D/ST flags a leak, while 3 handcuffs earns an A+."""
    league = LeagueModel(id=9902, name="Audit League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=9902, name="Audit Team", is_user_team=True)
    db_session.add_all([league, team])

    # Flawed team: Starter K and Backup K on bench, 0 handcuffs
    k_start = PlayerModel(id=8001, full_name="Starter Kicker", position="K", pro_team="BAL", projected_points=9.0)
    k_bench = PlayerModel(id=8002, full_name="Wasted Backup Kicker", position="K", pro_team="KC", projected_points=8.5)
    rb_start = PlayerModel(id=8003, full_name="Starter RB", position="RB", pro_team="SF", projected_points=18.0)
    db_session.add_all([k_start, k_bench, rb_start])
    db_session.commit()

    db_session.add(RosterEntryModel(id="9902_1_8001", league_id=9902, team_id=1, player_id=8001, lineup_slot_id=RosterSlot.K, is_starter=True))
    db_session.add(RosterEntryModel(id="9902_1_8002", league_id=9902, team_id=1, player_id=8002, lineup_slot_id=RosterSlot.BENCH, is_starter=False))
    db_session.add(RosterEntryModel(id="9902_1_8003", league_id=9902, team_id=1, player_id=8003, lineup_slot_id=RosterSlot.RB, is_starter=True))
    db_session.commit()

    evals = [
        scoring_engine.evaluate_player(k_start),
        scoring_engine.evaluate_player(k_bench),
        scoring_engine.evaluate_player(rb_start),
    ]

    res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=9902,
        user_team_id=1,
        user_roster_evaluations=evals,
        free_agent_pool=[],
        league_size=8,
    )

    assert res.architecture_audit is not None
    audit = res.architecture_audit
    assert any("Backup Kicker" in w for w in audit.wasted_bench_slots)
    assert any("Drop backup kicker" in p for p in audit.tactical_prescriptions)
    assert audit.score < 80.0
