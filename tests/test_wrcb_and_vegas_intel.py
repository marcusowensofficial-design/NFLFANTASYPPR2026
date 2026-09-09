"""Tests for WR/CB Matchup Matrix and Vegas Game Script Intelligence."""

import pytest
from fastapi.testclient import TestClient

from src.adapters.nfl.schedule_client import NFLGame
from src.main import app
from src.services.matchup.vegas_gamescript import vegas_gamescript_analyzer
from src.services.matchup.wrcb_matrix import (
    NFL_CB_DEPTH_CHARTS,
    KNOWN_WR_ALIGNMENTS,
    wrcb_analyzer,
)
from src.db.models import PlayerModel
from src.services.recommendation.scoring_engine import scoring_engine


@pytest.fixture
def client():
    return TestClient(app)


def test_cb_depth_charts_and_shadows():
    """Verify CB depth charts exist and shadow coverage flags are properly configured."""
    assert "DEN" in NFL_CB_DEPTH_CHARTS
    assert "NYJ" in NFL_CB_DEPTH_CHARTS
    assert "CHI" in NFL_CB_DEPTH_CHARTS

    den_room = NFL_CB_DEPTH_CHARTS["DEN"]
    assert den_room["outside1"].name == "Patrick Surtain II"
    assert den_room["outside1"].is_shadow is True
    assert den_room["outside1"].coverage_grade > 90.0

    nyj_room = NFL_CB_DEPTH_CHARTS["NYJ"]
    assert nyj_room["outside1"].name == "Sauce Gardner"
    assert nyj_room["outside1"].is_shadow is True


def test_wr_alignments():
    """Verify route alignment tracking for key wide receivers."""
    lamb = wrcb_analyzer.get_wr_alignment("CeeDee Lamb")
    assert lamb.pct_slot >= 0.50

    jefferson = wrcb_analyzer.get_wr_alignment("Justin Jefferson")
    assert jefferson.pct_wide >= 0.70


def test_wrcb_matchup_analysis_shadow_and_mismatch():
    """Verify that elite shadow corners trigger shadow alerts, and slot WRs get slot mismatch ratings."""
    # Justin Jefferson vs Denver (Patrick Surtain II shadow)
    analysis_shadow = wrcb_analyzer.analyze_matchup(
        player_id=1,
        full_name="Justin Jefferson",
        pro_team="MIN",
        opponent="DEN",
        projected_points=18.5,
    )
    assert analysis_shadow.is_shadow_projected is True
    assert analysis_shadow.advantage_rating == "SHADOW_LOCKDOWN"
    assert analysis_shadow.advantage_score < 0
    assert "SHADOW ALERT" in analysis_shadow.tactical_takeaway

    # CeeDee Lamb vs Washington (vulnerable slot corner)
    analysis_slot = wrcb_analyzer.analyze_matchup(
        player_id=2,
        full_name="CeeDee Lamb",
        pro_team="DAL",
        opponent="WSH",
        projected_points=19.2,
    )
    assert analysis_slot.is_shadow_projected is False
    assert analysis_slot.advantage_score > 0
    assert "SLOT" in analysis_slot.advantage_rating or "ADVANTAGE" in analysis_slot.advantage_rating


def test_vegas_game_script_classification():
    """Test game script classification into shootouts, run funnels, pass funnels, and slugfests."""
    # 1. High Shootout (51.5 total, 1.5 spread)
    shootout_game = NFLGame(
        id="401",
        name="KC at BAL",
        date="2026-09-13T20:20Z",
        venue_name="M&T Bank Stadium",
        is_dome=False,
        home_team="BAL",
        away_team="KC",
        over_under=51.5,
        spread=-1.5,
        home_implied_total=26.5,
        away_implied_total=25.0,
    )
    script, label, pace, plays, advice = vegas_gamescript_analyzer.classify_game(shootout_game)
    assert script == "SHOOTOUT"
    assert pace == "FAST"
    assert "SHOOTOUT" in advice

    # 2. Favorite Run Funnel (42.0 total, home favored by 8.5)
    run_game = NFLGame(
        id="402",
        name="CAR at SF",
        date="2026-09-13T16:05Z",
        venue_name="Levi's Stadium",
        is_dome=False,
        home_team="SF",
        away_team="CAR",
        over_under=42.0,
        spread=-8.5,
        home_implied_total=25.25,
        away_implied_total=16.75,
    )
    script, label, pace, plays, advice = vegas_gamescript_analyzer.classify_game(run_game)
    assert script == "FAVORITE_RUN_FUNNEL"
    assert "RUN SCRIPT" in label.upper()

    # 3. Defensive Slugfest (38.0 total)
    slugfest = NFLGame(
        id="403",
        name="PIT at CLE",
        date="2026-09-13T13:00Z",
        venue_name="Cleveland Browns Stadium",
        is_dome=False,
        home_team="CLE",
        away_team="PIT",
        over_under=38.0,
        spread=-2.5,
        home_implied_total=20.25,
        away_implied_total=17.75,
    )
    script, label, pace, plays, advice = vegas_gamescript_analyzer.classify_game(slugfest)
    assert script == "DEFENSIVE_SLUGFEST"
    assert pace == "SLOW"


def test_vegas_week_analysis_and_roster_exposure():
    """Test full week analysis, team implied rankings, and roster exposure mapping."""
    games = [
        NFLGame(
            id="1",
            name="DAL at NYG",
            date="2026-09-13T13:00Z",
            venue_name="MetLife Stadium",
            home_team="NYG",
            away_team="DAL",
            over_under=45.5,
            spread=3.5,  # NYG underdog by 3.5
            home_implied_total=21.0,
            away_implied_total=24.5,
        ),
        NFLGame(
            id="2",
            name="DET at GB",
            date="2026-09-13T16:25Z",
            venue_name="Lambeau Field",
            home_team="GB",
            away_team="DET",
            over_under=49.5,
            spread=-2.5,
            home_implied_total=26.0,
            away_implied_total=23.5,
        ),
    ]
    user_roster = [
        {"player_id": 101, "full_name": "CeeDee Lamb", "position": "WR", "pro_team": "DAL", "is_starter": True, "projected_points": 18.0},
        {"player_id": 102, "full_name": "Amon-Ra St. Brown", "position": "WR", "pro_team": "DET", "is_starter": True, "projected_points": 17.5},
    ]

    res = vegas_gamescript_analyzer.analyze_week(games, season=2026, week=1, user_roster_players=user_roster)
    assert res.total_games == 2
    assert len(res.team_rankings) == 4
    # GB (26.0) should be ranked #1
    assert res.team_rankings[0].pro_team == "GB"
    assert res.team_rankings[0].rank == 1

    # Check that CeeDee Lamb is mapped to the DAL game
    dal_game = next(g for g in res.games if g.away_team == "DAL")
    assert len(dal_game.user_roster_exposure) == 1
    assert dal_game.user_roster_exposure[0].full_name == "CeeDee Lamb"


def test_api_wrcb_and_vegas_endpoints(client):
    """Test the REST endpoints /api/analysis/wrcb-matrix and /api/analysis/vegas-environments."""
    # 1. WR/CB Matrix endpoint
    wrcb_res = client.get("/api/analysis/wrcb-matrix?week=1")
    assert wrcb_res.status_code == 200
    data = wrcb_res.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "player_id" in first
        assert "advantage_score" in first
        assert "advantage_rating" in first
        assert "primary_cb" in first

    # 2. Vegas Environments endpoint
    vegas_res = client.get("/api/analysis/vegas-environments?week=1")
    assert vegas_res.status_code == 200
    vdata = vegas_res.json()
    assert "games" in vdata
    assert "team_rankings" in vdata
    assert "shootout_count" in vdata


def test_scoring_engine_enrichment_with_wrcb_and_vegas():
    """Test that evaluate_player in scoring_engine now produces WR/CB and Game Script metadata."""
    player = PlayerModel(
        id=999,
        full_name="Justin Jefferson",
        position="WR",
        pro_team="MIN",
        projected_points=18.0,
        injured=False,
    )
    game = NFLGame(
        id="501",
        name="MIN at DEN",
        date="2026-09-13T16:25Z",
        venue_name="Empower Field at Mile High",
        home_team="DEN",
        away_team="MIN",
        over_under=48.5,
        spread=-1.5,
        home_implied_total=25.0,
        away_implied_total=23.5,
    )
    evaluation = scoring_engine.evaluate_player(player, nfl_game=game)
    assert evaluation.wrcb_primary_cb == "Patrick Surtain II"
    assert evaluation.wrcb_is_shadow is True
    assert evaluation.game_script == "SHOOTOUT"
    assert evaluation.game_script_label == "High-Ceiling Shootout"
    assert any("SHADOW ALERT" in r for r in evaluation.reasons_negative)
    assert any("Shootout" in r for r in evaluation.reasons_positive)
