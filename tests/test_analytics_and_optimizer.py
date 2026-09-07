"""Unit tests for Player Identity, Start/Sit Scoring, Lineup Optimizer, Waiver Scanner, and Backtesting."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.identity.resolver import normalize_name, player_resolver
from src.db.models import Base, PlayerModel
from src.main import app
from src.services.backtesting.evaluator import backtest_evaluator
from src.services.espn_sync import ESPNSyncService
from src.services.optimizer.lineup_optimizer import lineup_optimizer
from src.services.recommendation.comparator import player_comparator
from src.services.recommendation.scoring_engine import (
    ScoringWeights,
    StartSitEvaluation,
    scoring_engine,
)
from src.services.waiver.scanner import waiver_scanner


def test_player_name_normalization():
    """Verify that player name normalization handles punctuation and suffixes."""
    assert normalize_name("Marvin Harrison Jr.") == "marvin harrison"
    assert normalize_name("De'Von Achane") == "devon achane"
    assert normalize_name("Patrick Mahomes II") == "patrick mahomes"
    assert normalize_name("Kenneth Walker III") == "kenneth walker"


def test_player_identity_resolver():
    """Verify resolver maps IDs and normalized names accurately."""
    player_resolver.initialize()

    # Match by ESPN ID
    bijan = player_resolver.resolve(espn_id=4430807)
    assert bijan is not None
    assert bijan.full_name == "Bijan Robinson"
    assert bijan.position == "RB"

    # Match Javonte Williams by ESPN ID
    javonte = player_resolver.resolve(espn_id=4361579)
    assert javonte is not None
    assert javonte.full_name == "Javonte Williams"

    # Match by normalized name
    marvin = player_resolver.resolve(name="Marvin Harrison Jr.", position="WR")
    assert marvin is not None
    assert marvin.espn_id == 4432708


def test_start_sit_scoring_engine():
    """Test Start/Sit scoring engine on active and questionable players."""
    p_healthy = PlayerModel(
        id=4426348,
        full_name="Jayden Daniels",
        position="QB",
        pro_team="WSH",
        projected_points=21.4,
        injury_status="ACTIVE",
    )
    p_healthy.projected_stats = {
        "pass_att": 35.0,
        "pass_cmp": 23.0,
        "pass_yds": 255.0,
        "pass_td": 1.8,
        "pass_int": 0.6,
        "rush_att": 7.0,
        "rush_yds": 42.0,
        "rush_td": 0.4,
    }
    eval_healthy = scoring_engine.evaluate_player(p_healthy)
    assert eval_healthy.start_score >= 75.0
    assert eval_healthy.confidence == "HIGH"
    assert len(eval_healthy.reasons_positive) > 0

    p_injured = PlayerModel(
        id=4430878,
        full_name="Marvin Harrison Jr.",
        position="WR",
        pro_team="ARI",
        projected_points=16.8,
        injury_status="QUESTIONABLE",
    )
    eval_injured = scoring_engine.evaluate_player(p_injured)
    assert eval_injured.components.health_score < 100.0
    assert any("Questionable" in r for r in eval_injured.reasons_negative)


def test_player_comparator_close_calls():
    """Test 2-player comparator and close-call threshold detection."""
    ev1 = StartSitEvaluation(
        player_id=1,
        full_name="Player A",
        position="WR",
        pro_team="KC",
        projected_points=16.8,
        start_score=78.5,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="FAVORABLE",
        opponent="CAR",
        is_home=True,
        implied_team_total=26.5,
        injury_status="ACTIVE",
    )
    ev2 = StartSitEvaluation(
        player_id=2,
        full_name="Player B",
        position="WR",
        pro_team="NYJ",
        projected_points=17.0,
        start_score=77.0,
        confidence="HIGH",
        recommendation="START",
        matchup_grade="NEUTRAL",
        opponent="NE",
        is_home=False,
        implied_team_total=22.0,
        injury_status="ACTIVE",
    )

    comp = player_comparator.compare([ev1, ev2])
    assert comp.recommended_player_id == 1
    assert comp.is_close_call is True  # delta is 1.5 (<= 2.5)
    assert "TOSS-UP" in comp.headline


@pytest.mark.asyncio
async def test_full_lineup_optimization_and_waivers(client, db_session):
    """Test end-to-end integration: Sync mock league, optimize lineup, and scan waivers."""
    service = ESPNSyncService(db=db_session)
    success, _, league = await service.sync(league_id=84920174, force=True, use_mock=True)
    assert success is True

    # 1. Optimize lineup for Team 1
    # Sync via endpoint to populate in-memory DB
    client.post("/api/league/sync?use_mock=true")

    opt_resp = client.get("/api/lineup/optimal?team_id=1")
    assert opt_resp.status_code == 200
    opt_data = opt_resp.json()

    assert opt_data["team_id"] == 1
    assert len(opt_data["starters"]) == 9  # 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 DST, 1 K
    assert len(opt_data["bench"]) == 2
    assert opt_data["total_start_score"] > 0
    assert opt_data["total_projected_points"] > 0

    # 2. Test Waiver Wire endpoint
    waiver_resp = client.get("/api/waiver/upgrades?team_id=1")
    assert waiver_resp.status_code == 200
    waiver_data = waiver_resp.json()
    assert "user_team_id" in waiver_data

    # 3. Test Backtesting endpoint
    backtest_resp = client.get("/api/backtest/report?team_id=1")
    assert backtest_resp.status_code == 200
    backtest_data = backtest_resp.json()
    assert backtest_data["overall_accuracy_pct"] >= 0.0

    # 4. Test Compare endpoint
    compare_resp = client.post(
        "/api/recommendation/compare",
        json={"player_ids": [4426348, 4361579]},
    )
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()
    assert compare_data["recommended_player_id"] in (4426348, 4361579)


def test_calibrated_ppr_volume_and_stratified_tiers():
    """Verify RB 2.85x target weighting and TE vs WR target tier stratification."""
    # 1. RB: Dual-threat vs early-down grinder
    rb_dual_threat = PlayerModel(id=101, full_name="Dual Threat RB", position="RB", pro_team="ATL", projected_points=18.0)
    rb_dual_threat.projected_stats = {"rush_att": 10.0, "targets": 7.0, "receptions": 5.5, "rush_yds": 45.0, "rec_yds": 45.0}

    rb_grinder = PlayerModel(id=102, full_name="Early Down Grinder", position="RB", pro_team="WSH", projected_points=14.0)
    rb_grinder.projected_stats = {"rush_att": 18.0, "targets": 0.0, "receptions": 0.0, "rush_yds": 75.0, "rec_yds": 0.0}

    eval_dual = scoring_engine.evaluate_player(rb_dual_threat)
    eval_grind = scoring_engine.evaluate_player(rb_grinder)
    assert eval_dual.components.opportunity_score > eval_grind.components.opportunity_score
    assert any("receiving role" in r for r in eval_dual.reasons_positive)

    # 2. TE vs WR with 6.5 targets
    te = PlayerModel(id=103, full_name="Brock Bowers", position="TE", pro_team="LV", projected_points=15.0)
    te.projected_stats = {"targets": 6.5, "receptions": 5.0, "rec_yds": 60.0}

    wr = PlayerModel(id=104, full_name="Slot Receiver", position="WR", pro_team="MIA", projected_points=13.0)
    wr.projected_stats = {"targets": 6.5, "receptions": 5.0, "rec_yds": 60.0}

    eval_te = scoring_engine.evaluate_player(te)
    eval_wr = scoring_engine.evaluate_player(wr)

    assert any("Elite TE" in r for r in eval_te.reasons_positive)
    assert any("Solid WR" in r for r in eval_wr.reasons_positive)


def test_game_script_and_asymmetric_weather():
    """Verify spread-induced game script and position-specific weather sensitivity."""
    from src.adapters.nfl.schedule_client import NFLGame
    from src.adapters.weather.client import WeatherReport
    from src.adapters.nfl.injuries_client import PlayerInjuryReport

    # 1. Game Script: Heavy favorite RB (KC -6.5)
    game_kc = NFLGame(id="1", name="DEN at KC", date="2026-09-14", venue_name="Arrowhead", is_dome=False, home_team="KC", away_team="DEN", over_under=48.5, spread=-6.5)
    rb_fav = PlayerModel(id=110, full_name="Pacheco", position="RB", pro_team="KC", projected_points=15.0)
    rb_fav.projected_stats = {"rush_att": 16.0, "targets": 2.0}
    eval_fav = scoring_engine.evaluate_player(rb_fav, nfl_game=game_kc)
    assert any("clock-killing run script" in r for r in eval_fav.reasons_positive)

    # 2. Asymmetric weather: Kicker vs RB in 18 mph wind
    windy_weather = WeatherReport(team="BUF", is_dome=False, temperature_f=45.0, wind_speed_mph=18.0)
    kicker = PlayerModel(id=120, full_name="Kicker A", position="K", pro_team="BUF", projected_points=8.5)
    rb_weather = PlayerModel(id=121, full_name="Cook", position="RB", pro_team="BUF", projected_points=15.0)
    rb_weather.projected_stats = {"rush_att": 14.0, "targets": 4.0}

    eval_k = scoring_engine.evaluate_player(kicker, weather=windy_weather)
    eval_rb = scoring_engine.evaluate_player(rb_weather, weather=windy_weather)

    assert eval_k.components.weather_score < 85.0
    assert eval_rb.components.weather_score >= 100.0

    # 3. Practice status progression (FP vs DNP)
    inj_fp = PlayerInjuryReport(athlete_id=130, name="Player FP", position="WR", team="LAR", status="QUESTIONABLE", headline="Practiced in full Friday")
    inj_dnp = PlayerInjuryReport(athlete_id=131, name="Player DNP", position="WR", team="LAR", status="QUESTIONABLE", headline="Held out, did not practice Friday")

    p_test = PlayerModel(id=130, full_name="P", position="WR", pro_team="LAR", projected_points=14.0)
    eval_fp = scoring_engine.evaluate_player(p_test, injury_report=inj_fp)
    eval_dnp = scoring_engine.evaluate_player(p_test, injury_report=inj_dnp)

    assert eval_fp.components.health_score == 90.0
    assert eval_dnp.components.health_score == 50.0


def test_waiver_scanner_slot_legality_and_kicker_isolation(db_session):
    """Ensure Kickers NEVER replace starting RBs or FLEX, and are not recommended as BENCH_STASH."""
    from src.db.models import LeagueModel, TeamModel, RosterEntryModel
    from src.adapters.espn.constants import RosterSlot

    # Create dummy league and team
    league = LeagueModel(id=999, name="Test League", season=2026, current_week=1, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=999, name="My Team", is_user_team=True)
    db_session.add_all([league, team])

    # Starter RB with low score
    rb_starter = PlayerModel(id=201, full_name="Low Starter RB", position="RB", pro_team="CAR", projected_points=8.0)
    # Bench RB
    rb_bench = PlayerModel(id=202, full_name="Bench RB", position="RB", pro_team="DEN", projected_points=6.0)
    # Starter Kicker
    k_starter = PlayerModel(id=203, full_name="Current Kicker", position="K", pro_team="NYG", projected_points=7.0)

    db_session.add_all([rb_starter, rb_bench, k_starter])
    db_session.commit()

    # Roster entries: RB is starter, Bench RB is bench, K is starter
    entry_rb = RosterEntryModel(id="999_1_201", league_id=999, team_id=1, player_id=201, lineup_slot_id=RosterSlot.RB, is_starter=True)
    entry_bench = RosterEntryModel(id="999_1_202", league_id=999, team_id=1, player_id=202, lineup_slot_id=RosterSlot.BENCH, is_starter=False)
    entry_k = RosterEntryModel(id="999_1_203", league_id=999, team_id=1, player_id=203, lineup_slot_id=RosterSlot.K, is_starter=True)
    db_session.add_all([entry_rb, entry_bench, entry_k])
    db_session.commit()

    # Free agents: Elite Kicker with high projection/StartScore
    fa_kicker = PlayerModel(id=301, full_name="Aubrey", position="K", pro_team="DAL", projected_points=11.5)
    db_session.add(fa_kicker)
    db_session.commit()

    user_evals = [
        scoring_engine.evaluate_player(rb_starter),
        scoring_engine.evaluate_player(rb_bench),
        scoring_engine.evaluate_player(k_starter),
    ]

    result = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=999,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        free_agent_pool=[fa_kicker],
    )

    for upg in result.top_upgrades:
        # If the upgrade picks up the kicker, it must NEVER replace RB or FLEX, and must NEVER be a BENCH_STASH
        if upg.pickup_player.position in ("K", "PK"):
            assert upg.replaces_slot == "K"
            assert upg.upgrade_type == "STARTING_LINEUP_UPGRADE"
            # And it must drop the current Kicker, NOT the bench RB!
            assert upg.drop_player.position in ("K", "PK")
            assert upg.drop_player.player_id == 203


