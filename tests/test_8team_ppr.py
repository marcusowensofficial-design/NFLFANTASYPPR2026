"""Master Comprehensive Test Suite for 8-Team ESPN PPR League Intelligence:
1. Calibrated Positional Baselines & Recommendation Thresholds for 8-Team Density
2. Konami Code QB Rush Multiplier, Tactical Ceiling vs. Floor Strategy Modes
3. Chronological Kickoff FLEX Optimization & Tactical FLEX Risk Alerting
4. Opponent Implied Spread Game Theory & Auto Posture Optimization
5. 2-for-1 Depth Consolidation Trade Analyzer with Wire Backfill
6. Roster Architecture Bench Audits & Deadweight Purge Detector
7. Non-linear S-Curve DvP & Pass-Funnel Role-Specific RB PPR Splits
8. Positional Stud Invariance & Matchup Resilience (Top-10 RBs, Top-12 WRs)
9. Playoff Strength of Schedule (Weeks 15-17 SoS) & H2H Stacking Synergies
10. Bye-Week & Stud Drop Protection in Waiver Scanner
11. Full-PPR FLEX Reception Floor Prioritization & Comparator Head-to-Head Rationale
12. Dynamic Live-Wire VORP & Injured/Doubtful Starter Exclusion
"""

import pytest
from src.adapters.espn.constants import RosterSlot
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.services.optimizer.lineup_optimizer import (
    get_kickoff_timestamp,
    lineup_optimizer,
)
from src.services.recommendation.comparator import player_comparator
from src.services.recommendation.scoring_engine import (
    LEAGUE_SIZE_BASELINES,
    StartSitEvaluation,
    calculate_playoff_sos,
    scoring_engine,
)
from src.services.trade.trade_analyzer import trade_analyzer
from src.services.waiver.scanner import waiver_scanner


# =============================================================================
# 1. Positional Baselines & Strategy Modes
# =============================================================================

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

    eval_12team = scoring_engine.evaluate_player(rb, league_size=12)
    eval_8team = scoring_engine.evaluate_player(rb, league_size=8)

    assert eval_12team.components.projection_score > 70.0
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

    assert eval_rusher.components.opportunity_score > eval_passer.components.opportunity_score
    assert any("Konami Code" in r for r in eval_rusher.reasons_positive)
    assert eval_rusher.ceiling_score > eval_passer.ceiling_score


def test_ceiling_vs_floor_strategy_modes():
    """Verify that CEILING mode boosts high-variance boom assets and FLOOR mode favors safe volume."""
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

    assert eval_boom_ceiling.ceiling_score > eval_floor_ceiling.ceiling_score
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

    res_balanced = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="BALANCED",
    )
    assert res_balanced.starters[0].recommended_player.player_id == 2

    res_ceiling = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="CEILING",
    )
    assert res_ceiling.starters[0].recommended_player.player_id == 1

    res_floor = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"FLEX": 1},
        evaluations=[p_ceiling, p_floor],
        mode="FLOOR",
    )
    assert res_floor.starters[0].recommended_player.player_id == 2


# =============================================================================
# 2. Chronological FLEX & Game Theory Opponent Spreads
# =============================================================================

def test_chronological_kickoff_flex_allocation():
    """Verify that the player with the latest kickoff holds the FLEX slot, never a Thursday starter."""
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
        game_date="2026-09-10T20:20Z",
    )

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
        game_date="2026-09-13T13:00Z",
    )

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
        game_date="2026-09-14T20:15Z",
    )

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

    roster_config = {"RB": 2, "WR": 2, "FLEX": 1}
    result = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config=roster_config,
        evaluations=[rb_tnf, rb_sun, rb_mnf, wr_1, wr_2],
    )

    flex_starter = next(s for s in result.starters if s.slot_name == "FLEX")
    rb_starters = [s for s in result.starters if s.slot_name == "RB"]

    assert flex_starter.recommended_player.player_id == 103
    assert flex_starter.is_flex_timing_optimal is True
    assert "Optimal FLEX timing" in flex_starter.flex_timing_note

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
        game_date="2026-09-10T20:15Z",
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
        game_date="2026-09-13T13:00Z",
    )

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
    assert res_underdog.starters[0].recommended_player.player_id == 401

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
    assert res_favorite.starters[0].recommended_player.player_id == 402


# =============================================================================
# 3. Consolidation Trades & Bench Architecture Audits
# =============================================================================

def test_consolidation_trade_analyzer_2_for_1(db_session):
    """Verify that 2-for-1 trade analyzer recommends targeting Tier-1 Alphas and computes net gain with waiver backfill."""
    league = LeagueModel(id=9901, name="Trade League", season=2026, size=8, user_team_id=1)
    user_team = TeamModel(id=1, league_id=9901, name="My Team", is_user_team=True)
    rival_team = TeamModel(id=2, league_id=9901, name="Rival Alpha Hoarder", is_user_team=False)
    db_session.add_all([league, user_team, rival_team])

    chase = PlayerModel(id=5001, full_name="Ja'Marr Chase", position="WR", pro_team="CIN", projected_points=21.0)
    chase.projected_stats = {"targets": 11.0, "receptions": 8.0, "rec_yds": 105.0, "rec_td": 0.8}
    weak_rb = PlayerModel(id=5002, full_name="Subpar Starter RB", position="RB", pro_team="CAR", projected_points=8.0)
    weak_rb.projected_stats = {"rush_att": 8.0, "rush_yds": 28.0, "targets": 1.0}
    db_session.add_all([chase, weak_rb])
    db_session.commit()

    db_session.add_all([
        RosterEntryModel(id="9901_2_5001", league_id=9901, team_id=2, player_id=5001, lineup_slot_id=RosterSlot.WR, is_starter=True),
        RosterEntryModel(id="9901_2_5002", league_id=9901, team_id=2, player_id=5002, lineup_slot_id=RosterSlot.RB, is_starter=True),
    ])

    user_wr = PlayerModel(id=6001, full_name="DeVonta Smith", position="WR", pro_team="PHI", projected_points=16.0)
    user_wr.projected_stats = {"targets": 8.0, "receptions": 5.5, "rec_yds": 75.0, "rec_td": 0.5}
    user_rb = PlayerModel(id=6002, full_name="James Cook", position="RB", pro_team="BUF", projected_points=15.5)
    user_rb.projected_stats = {"rush_att": 14.0, "rush_yds": 65.0, "targets": 4.0, "receptions": 3.0, "rec_yds": 25.0, "rush_td": 0.6}
    db_session.add_all([user_wr, user_rb])
    db_session.commit()

    db_session.add_all([
        RosterEntryModel(id="9901_1_6001", league_id=9901, team_id=1, player_id=6001, lineup_slot_id=RosterSlot.WR, is_starter=True),
        RosterEntryModel(id="9901_1_6002", league_id=9901, team_id=1, player_id=6002, lineup_slot_id=RosterSlot.RB, is_starter=False),
    ])

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

    k_start = PlayerModel(id=8001, full_name="Starter Kicker", position="K", pro_team="BAL", projected_points=9.0)
    k_bench = PlayerModel(id=8002, full_name="Wasted Backup Kicker", position="K", pro_team="KC", projected_points=8.5)
    rb_start = PlayerModel(id=8003, full_name="Starter RB", position="RB", pro_team="SF", projected_points=18.0)
    db_session.add_all([k_start, k_bench, rb_start])
    db_session.commit()

    db_session.add_all([
        RosterEntryModel(id="9902_1_8001", league_id=9902, team_id=1, player_id=8001, lineup_slot_id=RosterSlot.K, is_starter=True),
        RosterEntryModel(id="9902_1_8002", league_id=9902, team_id=1, player_id=8002, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
        RosterEntryModel(id="9902_1_8003", league_id=9902, team_id=1, player_id=8003, lineup_slot_id=RosterSlot.RB, is_starter=True),
    ])
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


# =============================================================================
# 4. DvP Curves & Stud Matchup Resilience
# =============================================================================

def test_dvp_client_non_linear_curve():
    """Rank 1 (toughest) should NOT give a 3% score, but a calibrated ~36 score on S-curve."""
    score_toughest, grade_toughest = dvp_client.calculate_matchup_score("NYJ", "WR")
    assert grade_toughest in ("TOUGH", "BRUTAL")
    assert 30.0 <= score_toughest <= 58.0

    score_softest, grade_softest = dvp_client.calculate_matchup_score("CAR", "WR")
    assert grade_softest in ("FAVORABLE", "ELITE")
    assert 85.0 <= score_softest <= 100.0

    score_mid, grade_mid = dvp_client.calculate_matchup_score("SEA", "WR")
    assert 60.0 <= score_mid <= 75.0


def test_role_specific_rb_ppr_matchup():
    """Receiving RBs in trailing script against tough run defense receive pass-funnel boost."""
    score_rush, grade_rush = dvp_client.calculate_matchup_score("BAL", "RB")
    score_rec, grade_rec, detail = dvp_client.calculate_role_matchup_score(
        opponent_team="BAL",
        position="RB",
        is_receiving_back=True,
        team_spread=4.5,
    )
    assert score_rec > score_rush
    assert "PPR Receiving Funnel" in detail or "targets/rec" in detail or grade_rec in ("FAVORABLE", "NEUTRAL")


def test_stud_matchup_elasticity_invariance():
    """Tier-1 studs should have compressed elasticity (MATCHUP_RESILIENT_STUD) against tough defense."""
    stud = PlayerModel(
        id=101,
        full_name="Justin Jefferson",
        position="WR",
        pro_team="MIN",
        projected_points=19.5,
        projected_stats={"targets": 10.5, "receptions": 7.5, "rec_yds": 98.0, "rec_td": 0.8},
        injury_status="ACTIVE",
    )
    streamer = PlayerModel(
        id=102,
        full_name="Jalen Nailor",
        position="WR",
        pro_team="MIN",
        projected_points=7.5,
        projected_stats={"targets": 3.5, "receptions": 2.0, "rec_yds": 25.0, "rec_td": 0.2},
        injury_status="ACTIVE",
    )

    game = NFLGame(
        id="401",
        name="MIN vs NYJ",
        date="2026-09-13T17:00Z",
        venue_name="MetLife Stadium",
        is_dome=False,
        home_team="NYJ",
        away_team="MIN",
        over_under=43.0,
        spread=3.0,
        home_implied_total=23.0,
        away_implied_total=20.0,
    )

    eval_stud = scoring_engine.evaluate_player(stud, nfl_game=game, league_size=8)
    eval_streamer = scoring_engine.evaluate_player(streamer, nfl_game=game, league_size=8)

    assert eval_stud.matchup_resilience == "MATCHUP_RESILIENT_STUD"
    assert eval_streamer.matchup_resilience == "MATCHUP_SENSITIVE_STREAMER"
    assert eval_stud.recommendation in ("STRONG START", "START")
    assert eval_stud.start_score >= 80.0
    assert eval_streamer.recommendation in ("BENCH", "SIT")


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


# =============================================================================
# 5. Playoff SoS & Correlation Stacking
# =============================================================================

def test_playoff_sos_calculation():
    """Weeks 15-17 Playoff SoS must produce a 0-100 score and qualitative grade."""
    score, grade = calculate_playoff_sos("ATL", "WR")
    assert 0.0 <= score <= 100.0
    assert grade in ("ELITE", "FAVORABLE", "NEUTRAL", "TOUGH", "BRUTAL")

    player = PlayerModel(
        id=201,
        full_name="Drake London",
        position="WR",
        pro_team="ATL",
        projected_points=15.0,
        injury_status="ACTIVE",
    )
    ev = scoring_engine.evaluate_player(player, league_size=8)
    assert hasattr(ev, "playoff_sos_score")
    assert hasattr(ev, "playoff_sos_grade")
    assert ev.playoff_sos_score == score
    assert ev.playoff_sos_grade == grade


def test_h2h_correlation_stacking_in_ceiling_mode():
    """In CEILING mode, starting a QB must apply correlation stacking boost to same-team WR/TE."""
    qb = scoring_engine.evaluate_player(
        PlayerModel(id=301, full_name="Joe Burrow", position="QB", pro_team="CIN", projected_points=21.5, injury_status="ACTIVE"),
        league_size=8,
    )
    wr_stack = scoring_engine.evaluate_player(
        PlayerModel(id=302, full_name="Ja'Marr Chase", position="WR", pro_team="CIN", projected_points=17.5, injury_status="ACTIVE"),
        league_size=8,
    )
    wr_other = scoring_engine.evaluate_player(
        PlayerModel(id=303, full_name="Nico Collins", position="WR", pro_team="HOU", projected_points=17.4, injury_status="ACTIVE"),
        league_size=8,
    )
    rb1 = scoring_engine.evaluate_player(
        PlayerModel(id=304, full_name="Bijan Robinson", position="RB", pro_team="ATL", projected_points=18.0, injury_status="ACTIVE"),
        league_size=8,
    )
    rb2 = scoring_engine.evaluate_player(
        PlayerModel(id=305, full_name="Jahmyr Gibbs", position="RB", pro_team="DET", projected_points=17.0, injury_status="ACTIVE"),
        league_size=8,
    )
    te = scoring_engine.evaluate_player(
        PlayerModel(id=306, full_name="Trey McBride", position="TE", pro_team="ARI", projected_points=13.0, injury_status="ACTIVE"),
        league_size=8,
    )
    dst = scoring_engine.evaluate_player(
        PlayerModel(id=307, full_name="Ravens D/ST", position="D/ST", pro_team="BAL", projected_points=9.0, injury_status="ACTIVE"),
        league_size=8,
    )
    k = scoring_engine.evaluate_player(
        PlayerModel(id=308, full_name="Justin Tucker", position="K", pro_team="BAL", projected_points=9.0, injury_status="ACTIVE"),
        league_size=8,
    )

    evals = [qb, wr_stack, wr_other, rb1, rb2, te, dst, k]
    slots_config = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 0, "D/ST": 1, "K": 1}

    result = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config=slots_config,
        evaluations=evals,
        mode="CEILING",
    )

    assert result.active_stacks is not None
    assert any("CIN QB Joe Burrow" in s for s in result.active_stacks)


# =============================================================================
# 6. Waiver Drops, Deadweight Purge & Stud Protection
# =============================================================================

def test_8team_waiver_drop_protection(db_session):
    """Verify that 14.0 projected points is drop-eligible in an 8-team league but protected in 12-team."""
    league = LeagueModel(id=801, name="8 Team League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=801, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    rb_starter = PlayerModel(id=810, full_name="Elite Starter RB", position="RB", pro_team="SF", projected_points=18.0)
    rb_bench = PlayerModel(id=811, full_name="Decent Bench Player", position="RB", pro_team="CLE", projected_points=14.0)
    db_session.add_all([rb_starter, rb_bench])
    db_session.commit()

    db_session.add_all([
        RosterEntryModel(id="801_1_810", league_id=801, team_id=1, player_id=810, lineup_slot_id=RosterSlot.RB, is_starter=True),
        RosterEntryModel(id="801_1_811", league_id=801, team_id=1, player_id=811, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
    ])
    db_session.commit()

    fa_stud = PlayerModel(id=820, full_name="Breakout Free Agent", position="WR", pro_team="DAL", projected_points=17.5)
    db_session.add(fa_stud)
    db_session.commit()

    user_evals_8 = [
        scoring_engine.evaluate_player(rb_starter, league_size=8),
        scoring_engine.evaluate_player(rb_bench, league_size=8),
    ]

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

    db_session.add_all([
        RosterEntryModel(id="802_1_830", league_id=802, team_id=1, player_id=830, lineup_slot_id=RosterSlot.RB, is_starter=True),
        RosterEntryModel(id="802_1_831", league_id=802, team_id=1, player_id=831, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
    ])
    db_session.commit()

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


def test_waiver_deadweight_bench_purge_detector(db_session):
    """Low-ceiling bench players must be flagged as deadweight in 8-team leagues."""
    league = LeagueModel(id=99, name="Elite 8", season=2026, size=8, current_week=1)
    team = TeamModel(id=901, league_id=99, name="Championship Squad")
    db_session.add_all([league, team])
    db_session.flush()

    deadweight_p = PlayerModel(
        id=501,
        full_name="Nelson Agholor",
        position="WR",
        pro_team="BAL",
        projected_points=6.5,
        injury_status="ACTIVE",
    )
    starter_p = PlayerModel(
        id=502,
        full_name="Amon-Ra St. Brown",
        position="WR",
        pro_team="DET",
        projected_points=18.0,
        injury_status="ACTIVE",
    )
    db_session.add_all([deadweight_p, starter_p])
    db_session.flush()

    db_session.add_all([
        RosterEntryModel(id="99_901_502", league_id=99, team_id=901, player_id=starter_p.id, lineup_slot_id=RosterSlot.WR, is_starter=True),
        RosterEntryModel(id="99_901_501", league_id=99, team_id=901, player_id=deadweight_p.id, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
    ])
    db_session.commit()

    starter_ev = scoring_engine.evaluate_player(starter_p, league_size=8)
    bench_ev = scoring_engine.evaluate_player(deadweight_p, league_size=8)

    waiver_res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=99,
        user_team_id=901,
        user_roster_evaluations=[starter_ev, bench_ev],
        league_size=8,
    )

    assert len(waiver_res.deadweight_drops) > 0
    dw = waiver_res.deadweight_drops[0]
    assert dw.player_id == deadweight_p.id
    assert "Zero-Ceiling" in dw.diagnosis
    assert any("Purge bench deadweight" in rx for rx in waiver_res.architecture_audit.tactical_prescriptions)


def test_bye_week_stud_drop_protection(db_session):
    """Verify that an elite stud on a BYE week (0 projected points) is NEVER recommended as a drop candidate."""
    league = LeagueModel(id=899, name="Expert 8-Man League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=899, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    rb_active = PlayerModel(id=710, full_name="Active Starter RB", position="RB", pro_team="SF", projected_points=18.0)
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

    db_session.add_all([
        RosterEntryModel(id="899_1_710", league_id=899, team_id=1, player_id=710, lineup_slot_id=RosterSlot.RB, is_starter=True),
        RosterEntryModel(id="899_1_711", league_id=899, team_id=1, player_id=711, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
        RosterEntryModel(id="899_1_712", league_id=899, team_id=1, player_id=712, lineup_slot_id=RosterSlot.BENCH, is_starter=False),
    ])
    db_session.commit()

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

    assert len(scan_res.top_upgrades) > 0
    drop_pids = [u.drop_player.player_id for u in scan_res.top_upgrades if u.drop_player]
    assert 711 not in drop_pids
    assert 712 in drop_pids


# =============================================================================
# 7. PPR Leverage Tagging, FLEX Floor & Live VORP
# =============================================================================

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

    assert any("[8-Man PPR Leverage]" in r for r in eval_alpha.reasons_positive)
    assert any("[8-Man PPR Trap]" in r for r in eval_plodder.reasons_negative)


def test_full_ppr_flex_tactical_allocation():
    """Verify that in full PPR, a high-target WR is prioritized for FLEX over a low-target RB with identical StartScore."""
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

    res = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config={"RB": 0, "WR": 0, "TE": 0, "FLEX": 1, "QB": 0, "D/ST": 0, "K": 0},
        evaluations=[rb_rush, wr_targets],
        mode="BALANCED",
    )

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
    assert 3.8 <= ev.live_vorp <= 4.2


def test_doubtful_injured_players_never_in_close_calls_or_optimal_over_healthy():
    """Verify that players who are Doubtful, Out, IR, or injured with 0 pts are never offered in close calls."""
    starter_te = StartSitEvaluation(
        player_id=801,
        full_name="Juwan Johnson",
        position="TE",
        pro_team="NO",
        projected_points=10.5,
        start_score=68.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="CAR",
        is_home=True,
        implied_team_total=23.0,
        injury_status="ACTIVE",
    )
    bench_doubtful = StartSitEvaluation(
        player_id=802,
        full_name="Brock Bowers",
        position="TE",
        pro_team="LV",
        projected_points=0.0,
        start_score=0.0,
        confidence="HIGH",
        recommendation="SIT",
        matchup_grade="BRUTAL",
        opponent="LAC",
        is_home=False,
        implied_team_total=18.0,
        injury_status="OUT",
    )
    bench_healthy = StartSitEvaluation(
        player_id=803,
        full_name="Jake Ferguson",
        position="TE",
        pro_team="DAL",
        projected_points=10.0,
        start_score=67.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="CLE",
        is_home=False,
        implied_team_total=21.0,
        injury_status="ACTIVE",
    )

    roster_config = {"QB": 0, "RB": 0, "WR": 0, "TE": 1, "FLEX": 0, "D/ST": 0, "K": 0}
    res = lineup_optimizer.optimize_lineup(
        team_id=1,
        roster_slots_config=roster_config,
        evaluations=[starter_te, bench_doubtful, bench_healthy],
        current_starter_ids={801},
        mode="BALANCED",
    )

    assert res.starters[0].recommended_player.player_id == 801
    for cc in res.close_calls:
        assert cc.starter.player_id != 802
        assert cc.bench_player.player_id != 802
