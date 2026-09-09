"""Automated test suite for Elite 8-Team PPR enhancements:
1. Non-linear Matchup Elasticity & Stud Invariance
2. Role-specific DvP splits (Receiving Back PPR funnel & Slot WR)
3. Playoff Strength of Schedule (Weeks 15-17 SoS)
4. Playoff Championship Leverage in Consolidation Trades
5. Week N+1 Lookahead Streaming Radar (D/ST & Kickers)
6. 8-Man Deadweight Bench Purge Detector
7. H2H Stacking & Correlation Game Theory in Lineup Optimizer
"""

import pytest
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import PlayerModel
from src.services.optimizer.lineup_optimizer import lineup_optimizer
from src.services.recommendation.scoring_engine import (
    calculate_playoff_sos,
    scoring_engine,
)
from src.services.waiver.scanner import waiver_scanner


def test_dvp_client_non_linear_curve():
    """Rank 1 (toughest) should NOT give a 3% score, but a calibrated ~36 score on S-curve."""
    score_toughest, grade_toughest = dvp_client.calculate_matchup_score("NYJ", "WR")
    assert grade_toughest in ("TOUGH", "BRUTAL")
    assert 30.0 <= score_toughest <= 58.0

    score_softest, grade_softest = dvp_client.calculate_matchup_score("CAR", "WR")
    assert grade_softest in ("FAVORABLE", "ELITE")
    assert 85.0 <= score_softest <= 100.0

    # Neutral middle rank
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
    # Receiving score should be substantially higher than pure between-the-tackles rush rank
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
    # Stud maintains elite recommendation despite tough NYJ secondary
    assert eval_stud.recommendation in ("STRONG START", "START")
    assert eval_stud.start_score >= 80.0
    # Streamer is penalized significantly
    assert eval_streamer.recommendation in ("BENCH", "SIT")


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
    # Stacking synergy should identify CIN QB + WR stack
    assert any("CIN QB Joe Burrow" in s for s in result.active_stacks)


def test_waiver_deadweight_bench_purge_detector(db_session):
    """Low-ceiling bench players must be flagged as deadweight in 8-team leagues."""
    from src.db.models import LeagueModel, RosterEntryModel, TeamModel

    league = LeagueModel(id=99, name="Elite 8", season=2026, size=8, current_week=1)
    team = TeamModel(id=901, league_id=99, name="Championship Squad")
    db_session.add_all([league, team])
    db_session.flush()

    # Create deadweight bench player (low projection, zero ceiling)
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

    from src.adapters.espn.constants import RosterSlot
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
