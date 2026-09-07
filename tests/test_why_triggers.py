"""Unit tests for 360-degree dynamic pros & cons triggers, funnels, and factor sorting."""

import pytest
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.services.recommendation.scoring_engine import scoring_engine, sort_factor_reasons


def test_sort_factor_reasons():
    """Verify strategic factor ordering puts Volume & Red Zone before Consensus and Weather."""
    raw = [
        "[Consensus] ⭐ FantasyPros ECR #3 Consensus Lock",
        "[Weather] 💨 18 mph wind alert",
        "[Script] 🏈 Trailing pass script",
        "[Volume] 🎯 Workhorse volume: 20 carries",
        "[Red Zone] 🚨 High-value goal line role",
        "[Matchup] 🛡️ Favorable matchup",
    ]
    sorted_reasons = sort_factor_reasons(raw)
    assert sorted_reasons[0].startswith("[Volume]")
    assert sorted_reasons[1].startswith("[Red Zone]")
    assert sorted_reasons[2].startswith("[Script]")
    assert sorted_reasons[3].startswith("[Matchup]")
    assert sorted_reasons[-1].startswith("[Consensus]")


def test_pass_funnel_and_run_funnel_detection():
    """Verify DvPClient detects Detroit as Pass Funnel and Dallas as Run Funnel."""
    det_funnel = dvp_client.detect_defensive_funnel("DET")
    assert det_funnel["is_pass_funnel"] is True
    assert det_funnel["rush_rank"] <= 12
    assert det_funnel["pass_rank"] >= 20

    dal_funnel = dvp_client.detect_defensive_funnel("DAL")
    assert dal_funnel["is_run_funnel"] is True
    assert dal_funnel["pass_rank"] <= 12
    assert dal_funnel["rush_rank"] >= 19


def test_wr_pass_funnel_trigger():
    """Verify WR facing a pass-funnel defense receives Pass Funnel Advantage pro."""
    game = NFLGame(
        id="1",
        name="CHI at DET",
        date="2026-09-14",
        venue_name="Ford Field",
        is_dome=True,
        home_team="DET",
        away_team="CHI",
        over_under=47.5,
        spread=-3.5,
    )
    wr = PlayerModel(
        id=9901,
        full_name="DJ Moore",
        position="WR",
        pro_team="CHI",
        projected_points=14.5,
        projected_stats_json='{"targets": 8.0, "receptions": 5.5, "rec_yds": 75.0, "rec_td": 0.5}',
    )
    eval_res = scoring_engine.evaluate_player(wr, nfl_game=game)
    assert any("Pass Funnel Advantage" in r for r in eval_res.reasons_positive)


def test_rb_run_funnel_trigger():
    """Verify RB facing a run-funnel defense receives Run Funnel Advantage pro."""
    game = NFLGame(
        id="2",
        name="NYG at DAL",
        date="2026-09-14",
        venue_name="AT&T Stadium",
        is_dome=True,
        home_team="DAL",
        away_team="NYG",
        over_under=44.0,
        spread=-6.0,
    )
    rb = PlayerModel(
        id=9902,
        full_name="Devin Singletary",
        position="RB",
        pro_team="NYG",
        projected_points=12.0,
        projected_stats_json='{"rush_att": 14.0, "rush_yds": 60.0, "rush_td": 0.4, "targets": 3.0, "receptions": 2.2, "rec_yds": 18.0}',
    )
    eval_res = scoring_engine.evaluate_player(rb, nfl_game=game)
    assert any("Run Funnel Advantage" in r for r in eval_res.reasons_positive)


def test_underdog_script_rb_split():
    """Verify pass-catching RB gets checkdown script pro while early-down grinder gets negative script risk."""
    game = NFLGame(
        id="3",
        name="NE at BUF",
        date="2026-09-14",
        venue_name="Highmark Stadium",
        is_dome=False,
        home_team="BUF",
        away_team="NE",
        over_under=43.0,
        spread=-6.5,  # NE is +6.5 underdog
    )

    # Pass-catching RB
    rb_catcher = PlayerModel(
        id=9903,
        full_name="Antonio Gibson",
        position="RB",
        pro_team="NE",
        projected_points=11.5,
        projected_stats_json='{"rush_att": 6.0, "rush_yds": 25.0, "rush_td": 0.2, "targets": 5.0, "receptions": 4.0, "rec_yds": 32.0, "rec_td": 0.2}',
    )
    eval_catcher = scoring_engine.evaluate_player(rb_catcher, nfl_game=game)
    assert any("Trailing checkdown script" in r for r in eval_catcher.reasons_positive)

    # Early-down grinder RB
    rb_grinder = PlayerModel(
        id=9904,
        full_name="Early Down Grinder",
        position="RB",
        pro_team="NE",
        projected_points=9.5,
        projected_stats_json='{"rush_att": 13.0, "rush_yds": 52.0, "rush_td": 0.3, "targets": 1.0, "receptions": 0.8, "rec_yds": 5.0, "rec_td": 0.0}',
    )
    eval_grinder = scoring_engine.evaluate_player(rb_grinder, nfl_game=game)
    assert any("Negative script risk" in r for r in eval_grinder.reasons_negative)


def test_blowout_script_risk_for_pass_catchers():
    """Verify heavy favorite pass catchers receive blowout script risk con."""
    game = NFLGame(
        id="4",
        name="CAR at KC",
        date="2026-09-14",
        venue_name="Arrowhead Stadium",
        is_dome=False,
        home_team="KC",
        away_team="CAR",
        over_under=46.0,
        spread=-9.5,  # KC favored by 9.5
    )
    wr = PlayerModel(
        id=9905,
        full_name="Rashee Rice",
        position="WR",
        pro_team="KC",
        projected_points=15.0,
        projected_stats_json='{"targets": 7.5, "receptions": 5.5, "rec_yds": 68.0, "rec_td": 0.4}',
    )
    eval_wr = scoring_engine.evaluate_player(wr, nfl_game=game)
    assert any("Blowout script risk" in r for r in eval_wr.reasons_negative)


def test_stud_matchup_resilience():
    """Verify Tier-1 stud facing tough defense gets Stud matchup resilience pro instead of flat con."""
    game = NFLGame(
        id="5",
        name="MIN at SF",
        date="2026-09-14",
        venue_name="Levi's Stadium",
        is_dome=False,
        home_team="SF",
        away_team="MIN",
        over_under=45.0,
        spread=-4.5,
    )
    stud = PlayerModel(
        id=9906,
        full_name="Justin Jefferson",
        position="WR",
        pro_team="MIN",
        projected_points=19.5,
        fp_rank_ecr=2,
        consensus_rank=2.0,
        projected_stats_json='{"targets": 10.5, "receptions": 7.5, "rec_yds": 105.0, "rec_td": 0.7}',
    )
    eval_stud = scoring_engine.evaluate_player(stud, nfl_game=game)
    assert any("Stud matchup resilience" in r or "Alpha volume insulation" in r for r in eval_stud.reasons_positive)


def test_multi_source_convergence_and_divergence_triggers():
    """Verify high multi-source convergence and high divergence triggers."""
    # Player with close projections across all 3 sources
    convergent_player = PlayerModel(
        id=9910,
        full_name="Breece Hall",
        position="RB",
        pro_team="NYJ",
        projected_points=18.0,
        projected_points_model=18.2,
        projected_points_fp=17.8,
        projected_points_espn=18.0,
        projected_stats_json='{"rush_att": 16.0, "rush_yds": 75.0, "rush_td": 0.6, "targets": 5.0, "receptions": 4.0, "rec_yds": 35.0, "rec_td": 0.2}',
    )
    eval_conv = scoring_engine.evaluate_player(convergent_player)
    assert any("Multi-Source Convergence" in r for r in eval_conv.reasons_positive)

    # Player with wide projection divergence across sources
    divergent_player = PlayerModel(
        id=9911,
        full_name="Boom Bust WR",
        position="WR",
        pro_team="MIA",
        projected_points=14.0,
        projected_points_model=19.5,
        projected_points_fp=10.0,
        projected_points_espn=12.5,
        projected_stats_json='{"targets": 7.0, "receptions": 4.0, "rec_yds": 65.0, "rec_td": 0.4}',
    )
    eval_div = scoring_engine.evaluate_player(divergent_player)
    assert any("Multi-Source Model Divergence" in r for r in eval_div.reasons_negative)


def test_five_star_smash_and_one_star_lockdown_triggers():
    """Verify 5-Star smash matchup and 1-Star lockdown alert triggers."""
    game_smash = NFLGame(
        id="10",
        name="ATL at CAR",
        date="2026-09-14",
        venue_name="Bank of America Stadium",
        is_dome=False,
        home_team="CAR",
        away_team="ATL",
        over_under=45.0,
        spread=3.5,  # CAR is home underdog
    )
    rb_smash = PlayerModel(
        id=9912,
        full_name="Bijan Robinson",
        position="RB",
        pro_team="ATL",
        projected_points=19.0,
        projected_stats_json='{"rush_att": 18.0, "rush_yds": 95.0, "rush_td": 0.8, "targets": 5.0, "receptions": 4.0, "rec_yds": 35.0}',
    )
    eval_smash = scoring_engine.evaluate_player(rb_smash, nfl_game=game_smash)
    assert any("5-Star Smash Matchup" in r for r in eval_smash.reasons_positive)
    assert any("Porous Scoring Defense" in r for r in eval_smash.reasons_positive)

    # Streamer facing Cleveland (rank #2 vs WR)
    game_lockdown = NFLGame(
        id="11",
        name="CIN at CLE",
        date="2026-09-14",
        venue_name="Cleveland Browns Stadium",
        is_dome=False,
        home_team="CLE",
        away_team="CIN",
        over_under=42.0,
        spread=-3.5,
    )
    wr_streamer = PlayerModel(
        id=9913,
        full_name="Fringe Streamer WR",
        position="WR",
        pro_team="CIN",
        projected_points=7.5,
        fp_rank_ecr=45,
        consensus_rank=45.0,
        projected_stats_json='{"targets": 4.0, "receptions": 2.5, "rec_yds": 28.0, "rec_td": 0.1}',
    )
    eval_lock = scoring_engine.evaluate_player(wr_streamer, nfl_game=game_lockdown)
    assert any("1-Star Lockdown Alert" in r for r in eval_lock.reasons_negative)
    assert any("Elite Scoring Defense" in r for r in eval_lock.reasons_negative)


def test_efficiency_and_workhorse_triggers():
    """Verify 20+ touch monster, high YPC burst, and high catch rate conversion triggers."""
    rb_workhorse = PlayerModel(
        id=9914,
        full_name="Christian McCaffrey",
        position="RB",
        pro_team="SF",
        projected_points=22.0,
        projected_stats_json='{"rush_att": 18.0, "rush_yds": 92.0, "rush_td": 0.9, "targets": 6.0, "receptions": 5.0, "rec_yds": 42.0, "rec_td": 0.3}',
    )
    eval_rb = scoring_engine.evaluate_player(rb_workhorse)
    assert any("Elite 20+ Touch Workhorse" in r for r in eval_rb.reasons_positive)
    assert any("Explosive Ground Efficiency" in r for r in eval_rb.reasons_positive)
    assert any("High-Value Touch Hub" in r for r in eval_rb.reasons_positive)

    # WR with elite 85% catch rate
    wr_possession = PlayerModel(
        id=9915,
        full_name="Amon-Ra St. Brown",
        position="WR",
        pro_team="DET",
        projected_points=18.5,
        projected_stats_json='{"targets": 8.0, "receptions": 6.5, "rec_yds": 78.0, "rec_td": 0.6}',
    )
    eval_wr = scoring_engine.evaluate_player(wr_possession)
    assert any("High-Percentage Target Conversion" in r for r in eval_wr.reasons_positive)


def test_dual_threat_qb_and_competitive_shootout_triggers():
    """Verify dual-threat QB designed rush equity and competitive shootout script triggers."""
    game_shootout = NFLGame(
        id="12",
        name="KC at BAL",
        date="2026-09-14",
        venue_name="M&T Bank Stadium",
        is_dome=False,
        home_team="BAL",
        away_team="KC",
        over_under=49.5,
        spread=-1.5,  # BAL favored by 1.5 (tight spread, high O/U)
    )
    qb = PlayerModel(
        id=9916,
        full_name="Lamar Jackson",
        position="QB",
        pro_team="BAL",
        projected_points=23.0,
        projected_stats_json='{"pass_att": 29.0, "pass_yds": 225.0, "pass_td": 1.9, "pass_int": 0.5, "rush_att": 8.0, "rush_yds": 58.0, "rush_td": 0.45}',
    )
    eval_qb = scoring_engine.evaluate_player(qb, nfl_game=game_shootout)
    assert any("Designed Rushing & Sneak Equity" in r for r in eval_qb.reasons_positive)
    assert any("Competitive Shootout Script" in r for r in eval_qb.reasons_positive)
    assert any("High Passing TD Ceiling" in r for r in eval_qb.reasons_positive)
    assert any("Home Favorite Advantage" in r for r in eval_qb.reasons_positive)


def test_dst_turnover_pro_and_clean_bill_of_health():
    """Verify D/ST turnover funnel pro and clean bill of health pro."""
    game_car = NFLGame(
        id="13",
        name="CAR at TB",
        date="2026-09-14",
        venue_name="Raymond James Stadium",
        is_dome=False,
        home_team="TB",
        away_team="CAR",
        over_under=41.5,
        spread=-4.5,
    )
    dst = PlayerModel(
        id=9917,
        full_name="Buccaneers D/ST",
        position="D/ST",
        pro_team="TB",
        projected_points=9.0,
        injury_status="ACTIVE",
    )
    eval_dst = scoring_engine.evaluate_player(dst, nfl_game=game_car)
    assert any("Generous Turnover Opponent" in r for r in eval_dst.reasons_positive)
    assert any("Clean Bill of Health" in r for r in eval_dst.reasons_positive)


def test_rb_target_to_touch_ratio_triggers():
    """Verify elite target-to-touch ratio pro and low ratio trap con."""
    game = NFLGame(
        id="14",
        name="KC at LAC",
        date="2026-09-13",
        venue_name="SoFi Stadium",
        home_team="LAC",
        away_team="KC",
    )
    # High ratio pass-catcher (e.g. 5 tgts on 15 touches = 33%)
    rb_high = PlayerModel(
        id=9918,
        full_name="Jahmyr Gibbs",
        position="RB",
        pro_team="KC",
        projected_points=17.5,
        projected_stats_json='{"rush_att": 10.0, "rush_yds": 48.0, "targets": 5.0, "receptions": 4.2, "rec_yds": 38.0, "rush_td": 0.4, "rec_td": 0.3}',
    )
    eval_high = scoring_engine.evaluate_player(rb_high, nfl_game=game)
    assert any("Elite Target-to-Touch Ratio" in r for r in eval_high.reasons_positive)

    # Low ratio early-down grinder (e.g. 1 tgt on 15 touches = 6.7%)
    rb_low = PlayerModel(
        id=9919,
        full_name="Early Down Plodder",
        position="RB",
        pro_team="LAC",
        projected_points=9.5,
        projected_stats_json='{"rush_att": 14.0, "rush_yds": 52.0, "targets": 1.0, "receptions": 0.8, "rec_yds": 5.0, "rush_td": 0.3, "rec_td": 0.0}',
    )
    eval_low = scoring_engine.evaluate_player(rb_low, nfl_game=game)
    assert any("Low Target-to-Touch Ratio" in r for r in eval_low.reasons_negative)


def test_receptions_grounded_floor_and_td_dependency_triggers():
    """Verify receptions-grounded floor pro and touchdown-dependent trap con."""
    game = NFLGame(
        id="15",
        name="MIN at DET",
        date="2026-09-13",
        venue_name="Ford Field",
        home_team="DET",
        away_team="MIN",
    )
    # High reception share WR (e.g. Amon-Ra style: 7 rec on 9 tgts, 75 yds, 0.2 TD)
    wr_floor = PlayerModel(
        id=9920,
        full_name="Slot Machine WR",
        position="WR",
        pro_team="DET",
        projected_points=15.7,
        projected_stats_json='{"targets": 9.0, "receptions": 7.0, "rec_yds": 75.0, "rec_td": 0.2}',
    )
    eval_floor = scoring_engine.evaluate_player(wr_floor, nfl_game=game)
    assert any("Receptions-Grounded Floor" in r for r in eval_floor.reasons_positive)

    # TD dependent player (e.g. 2 catches, 15 yds, 0.75 TD)
    te_td = PlayerModel(
        id=9921,
        full_name="TD Dependent Specialist",
        position="TE",
        pro_team="MIN",
        projected_points=8.5,
        projected_stats_json='{"targets": 2.5, "receptions": 2.0, "rec_yds": 18.0, "rec_td": 0.70}',
    )
    eval_td = scoring_engine.evaluate_player(te_td, nfl_game=game)
    assert any("Touchdown-Dependent Trap" in r for r in eval_td.reasons_negative)


def test_vegas_implied_td_bonanza_and_desert_triggers():
    """Verify Implied Touchdown Bonanza for high totals and Touchdown Desert for low totals."""
    # KC high implied total (30.0)
    game_kc = NFLGame(
        id="16",
        name="DEN at KC",
        date="2026-09-13",
        venue_name="Arrowhead",
        home_team="KC",
        away_team="DEN",
        over_under=53.0,
        spread=-7.0,
        home_implied_total=30.0,
        away_implied_total=23.0,
    )
    kc_wr = PlayerModel(
        id=9922,
        full_name="Rashee Rice",
        position="WR",
        pro_team="KC",
        projected_points=14.0,
        projected_stats_json='{"targets": 7.0, "receptions": 5.5, "rec_yds": 65.0, "rec_td": 0.4}',
    )
    eval_kc = scoring_engine.evaluate_player(kc_wr, nfl_game=game_kc)
    assert any("Implied Touchdown Bonanza" in r for r in eval_kc.reasons_positive)

    # Low implied total (15.5)
    game_low = NFLGame(
        id="17",
        name="CAR at TB",
        date="2026-09-13",
        venue_name="Raymond James Stadium",
        home_team="TB",
        away_team="CAR",
        over_under=36.0,
        spread=-5.0,
        home_implied_total=20.5,
        away_implied_total=15.5,
    )
    car_rb = PlayerModel(
        id=9923,
        full_name="Chuba Hubbard",
        position="RB",
        pro_team="CAR",
        projected_points=10.0,
        projected_stats_json='{"rush_att": 12.0, "rush_yds": 46.0, "targets": 2.0, "receptions": 1.5, "rec_yds": 10.0, "rush_td": 0.3, "rec_td": 0.0}',
    )
    eval_car = scoring_engine.evaluate_player(car_rb, nfl_game=game_low)
    assert any("Touchdown Desert" in r for r in eval_car.reasons_negative)


def test_qb_ballhawk_pressure_risk_trigger():
    """Verify streamer QB receives Ballhawk Pressure Risk against top-6 pass defense."""
    # NYJ is a top-ranked defense (DvP rank <= 6 vs QB)
    game_nyj = NFLGame(
        id="18",
        name="TEN at NYJ",
        date="2026-09-13",
        venue_name="MetLife Stadium",
        home_team="NYJ",
        away_team="TEN",
        over_under=40.0,
        spread=-4.0,
    )
    qb_streamer = PlayerModel(
        id=9924,
        full_name="Will Levis",
        position="QB",
        pro_team="TEN",
        projected_points=13.5,
        projected_stats_json='{"pass_att": 30.0, "pass_yds": 210.0, "pass_td": 1.1, "pass_int": 1.1, "rush_att": 2.5, "rush_yds": 12.0, "rush_td": 0.1}',
    )
    eval_qb = scoring_engine.evaluate_player(qb_streamer, nfl_game=game_nyj)
    assert any("Ballhawk Pressure Risk" in r for r in eval_qb.reasons_negative)


def test_thursday_kickoff_flex_rule_trigger():
    """Verify Thursday kickoff triggers tactical FLEX placement recommendation."""
    game_thu = NFLGame(
        id="19",
        name="BAL at KC",
        date="2026-09-10T20:20:00Z",  # 2026-09-10 is Thursday (weekday index 3)
        venue_name="Arrowhead Stadium",
        home_team="KC",
        away_team="BAL",
    )
    wr_thu = PlayerModel(
        id=9925,
        full_name="Xavier Worthy",
        position="WR",
        pro_team="KC",
        projected_points=12.8,
        projected_stats_json='{"targets": 6.0, "receptions": 4.0, "rec_yds": 58.0, "rec_td": 0.4}',
    )
    eval_thu = scoring_engine.evaluate_player(wr_thu, nfl_game=game_thu)
    assert any("Thursday Kickoff FLEX Rule" in r for r in eval_thu.reasons_positive)
    assert any(r.startswith("[Tactical]") for r in eval_thu.reasons_positive)


