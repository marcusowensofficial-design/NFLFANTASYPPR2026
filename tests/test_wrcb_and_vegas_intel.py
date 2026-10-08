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
    """Verify CB depth charts exist and shadow coverage flags are properly configured for 2026."""
    assert "DEN" in NFL_CB_DEPTH_CHARTS
    assert "NYJ" in NFL_CB_DEPTH_CHARTS
    assert "CHI" in NFL_CB_DEPTH_CHARTS
    assert "IND" in NFL_CB_DEPTH_CHARTS
    assert "KC" in NFL_CB_DEPTH_CHARTS
    assert "LAR" in NFL_CB_DEPTH_CHARTS
    assert "TEN" in NFL_CB_DEPTH_CHARTS

    den_room = NFL_CB_DEPTH_CHARTS["DEN"]
    assert den_room["outside1"].name in ("Patrick Surtain II", "Pat Surtain II")
    assert den_room["outside1"].is_shadow is True
    assert den_room["outside1"].coverage_grade >= 88.0

    # NYJ starter is Azareye'h Thomas or Nahshon Wright
    nyj_room = NFL_CB_DEPTH_CHARTS["NYJ"]
    assert nyj_room["outside1"].name in ("Azareye'h Thomas", "Nahshon Wright")

    # Sauce Gardner and Charvarius Ward on IND
    ind_room = NFL_CB_DEPTH_CHARTS["IND"]
    assert ind_room["outside1"].name == "Sauce Gardner"
    assert ind_room["outside1"].is_shadow is True
    assert ind_room["outside2"].name == "Charvarius Ward"

    # Trent McDuffie traded to LAR (Shadow All-Pro)
    lar_room = NFL_CB_DEPTH_CHARTS["LAR"]
    assert lar_room["outside2"].name == "Trent McDuffie"
    assert lar_room["outside2"].is_shadow is True

    # L'Jarius Sneed reunited with KC
    kc_room = NFL_CB_DEPTH_CHARTS["KC"]
    assert kc_room["slot"].name == "L'Jarius Sneed"

    # TEN cornerbacks (Cor'Dale Flott, Alontae Taylor)
    ten_room = NFL_CB_DEPTH_CHARTS["TEN"]
    assert ten_room["outside1"].name == "Cor'Dale Flott"
    assert ten_room["outside2"].name == "Alontae Taylor"


def test_all_32_teams_cb_depth_charts_have_no_discrepancies():
    """Regression test: verifies that all 32 teams' cornerbacks match their verified 2026 depth chart team."""
    import json
    from pathlib import Path

    dc_path = Path("data/nfl_depth_charts_2026.json")
    assert dc_path.exists(), "Official depth chart file must exist"
    with open(dc_path, "r", encoding="utf-8") as f:
        dc_teams = json.load(f).get("teams", {})

    pff_path = Path("data/pff_scouting_2026.json")
    assert pff_path.exists(), "PFF scouting file must exist"
    with open(pff_path, "r", encoding="utf-8") as f:
        pff_teams = json.load(f).get("teams", {})

    discrepancies = []
    for team, cb_room in NFL_CB_DEPTH_CHARTS.items():
        assert team in dc_teams, f"Team {team} missing from official depth charts"
        assert team in pff_teams, f"Team {team} missing from PFF scouting"
        
        team_dc = dc_teams[team].get("defense", {})
        dc_players = set()
        for pos in ["lcb", "rcb", "nb", "cb", "fs", "ss", "db"]:
            for p in team_dc.get(pos, []):
                dc_players.add(p.get("name"))

        for role, prof in cb_room.items():
            if prof.name not in dc_players:
                discrepancies.append(f"wrcb_matrix [{team}] {role}: {prof.name} not in depth chart")

        pff_cbs = pff_teams[team].get("cornerbacks", {})
        for role in ["outside1", "outside2", "slot"]:
            pff_cb_name = pff_cbs.get(role, {}).get("name")
            if pff_cb_name and pff_cb_name not in dc_players:
                discrepancies.append(f"pff_scouting [{team}] {role}: {pff_cb_name} not in depth chart")

    assert not discrepancies, f"Found cornerback team discrepancies:\n" + "\n".join(discrepancies)




def test_wr_alignments():
    """Verify route alignment tracking for key wide receivers."""
    lamb = wrcb_analyzer.get_wr_alignment("CeeDee Lamb")
    assert lamb.pct_slot >= 0.50

    jefferson = wrcb_analyzer.get_wr_alignment("Justin Jefferson")
    assert jefferson.pct_wide >= 0.70


def test_wrcb_matchup_analysis_shadow_and_mismatch():
    """Verify that elite shadow corners trigger shadow alerts, and live injured corners trigger backup replacements."""
    # Healthy shadow baseline: Justin Jefferson vs IND (Sauce Gardner shadow)
    analysis_shadow = wrcb_analyzer.analyze_matchup(
        player_id=1,
        full_name="Justin Jefferson",
        pro_team="MIN",
        opponent="IND",
        projected_points=18.5,
        inactive_player_names=set(),
    )
    assert analysis_shadow.is_shadow_projected is True
    assert analysis_shadow.advantage_rating == "SHADOW_LOCKDOWN"
    assert analysis_shadow.advantage_score < 0
    assert "SHADOW ALERT" in analysis_shadow.tactical_takeaway

    # Live Inactive Test: Justin Jefferson vs DEN (Pat Surtain II is DOUBTFUL -> Jahdae Barron promoted)
    analysis_den_injured = wrcb_analyzer.analyze_matchup(
        player_id=1,
        full_name="Justin Jefferson",
        pro_team="MIN",
        opponent="DEN",
        projected_points=18.5,
    )
    assert analysis_den_injured.primary_cb.is_backup_replacement is True
    assert analysis_den_injured.primary_cb.name == "Jahdae Barron"
    assert "BACKUP CB TARGET" in analysis_den_injured.tactical_takeaway or "MAJOR_ADVANTAGE" in analysis_den_injured.advantage_rating

    # CeeDee Lamb vs Washington (vulnerable slot corner)
    analysis_slot = wrcb_analyzer.analyze_matchup(
        player_id=2,
        full_name="CeeDee Lamb",
        pro_team="DAL",
        opponent="WSH",
        projected_points=19.2,
    )
    assert analysis_slot.is_shadow_projected is False
    assert analysis_slot.advantage_score >= 0
    assert "SLOT" in analysis_slot.advantage_rating or "ADVANTAGE" in analysis_slot.advantage_rating or analysis_slot.advantage_rating == "NEUTRAL"


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
    """Test that evaluate_player in scoring_engine produces WR/CB and Game Script metadata, accurately detecting shadow vs backup."""
    player = PlayerModel(
        id=999,
        full_name="Justin Jefferson",
        position="WR",
        pro_team="MIN",
        projected_points=18.0,
        injured=False,
    )
    # 1. Healthy Shadow Test: MIN at IND (Sauce Gardner shadows WR1)
    game_ind = NFLGame(
        id="501",
        name="MIN at IND",
        date="2026-09-13T16:25Z",
        venue_name="Lucas Oil Stadium",
        home_team="IND",
        away_team="MIN",
        over_under=48.5,
        spread=-1.5,
        home_implied_total=25.0,
        away_implied_total=23.5,
    )
    eval_ind = scoring_engine.evaluate_player(player, nfl_game=game_ind)
    assert eval_ind.wrcb_primary_cb == "Sauce Gardner"
    assert eval_ind.wrcb_is_shadow is True
    assert eval_ind.game_script == "SHOOTOUT"
    assert eval_ind.game_script_label == "High-Ceiling Shootout"
    assert any("SHADOW ALERT" in r for r in eval_ind.reasons_negative)
    assert any("Shootout" in r for r in eval_ind.reasons_positive)

    # 2. Live Inactive Test: MIN at DEN (Surtain is DOUBTFUL -> Jahdae Barron promoted)
    game_den = NFLGame(
        id="502",
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
    eval_den = scoring_engine.evaluate_player(player, nfl_game=game_den)
    assert eval_den.wrcb_primary_cb == "Jahdae Barron"
    assert eval_den.wrcb_is_shadow is False


def test_injured_reserve_is_out_fix():
    """Verify that players with status INJURED RESERVE evaluate to is_out=True and is_playable=False."""
    import json
    from src.adapters.nfl.injuries_client import PlayerInjuryReport

    with open("data/injuries_live_2026.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    ir_players = [
        PlayerInjuryReport(**{k: inj[k] for k in PlayerInjuryReport.model_fields.keys() if k in inj})
        for inj in d.get("injuries", [])
        if "RESERVE" in str(inj.get("status", "")).upper()
    ]
    assert len(ir_players) > 0, "Expected at least 1 player on IR in live wire"
    for p in ir_players:
        assert p.is_out is True, f"IR player {p.name} should have is_out=True"
        assert p.is_playable is False, f"IR player {p.name} should have is_playable=False"


def test_expanded_active_wr_alignments_no_defaults():
    """Verify that active starting depth chart receivers exist in KNOWN_WR_ALIGNMENTS with calibrated values."""
    assert len(KNOWN_WR_ALIGNMENTS) >= 200, f"Expected at least 200 calibrated WRs, found {len(KNOWN_WR_ALIGNMENTS)}"

    # Check key players that were previously missing
    assert "joshua palmer" in KNOWN_WR_ALIGNMENTS
    assert "marvin mims jr." in KNOWN_WR_ALIGNMENTS
    assert "brandin cooks" in KNOWN_WR_ALIGNMENTS
    assert "andrei iosivas" in KNOWN_WR_ALIGNMENTS
    assert "troy franklin" in KNOWN_WR_ALIGNMENTS
    assert "darnell mooney" in KNOWN_WR_ALIGNMENTS

    palmer = KNOWN_WR_ALIGNMENTS["joshua palmer"]
    assert palmer.target_share > 0.05
    assert palmer.pct_wide > 0.50


def test_2026_definitive_stats_and_parquet():
    """Verify that player_stats_2026.parquet contains multi-week records and strictly demarcated seasons."""
    import json
    import pandas as pd
    from pathlib import Path

    p26 = Path("data/parquets/player_stats_2026.parquet")
    assert p26.exists(), "2026 parquet must exist"
    df26 = pd.read_parquet(p26)
    assert len(df26) >= 500, f"Expected multi-week expanded 2026 dataset, found {len(df26)} records"
    assert (df26["season"] == 2026).all(), "All records in 2026 parquet must have season=2026"

    # Verify Super Brain metadata
    with open("data/encyclopedia/nfl_super_brain_master.json", "r", encoding="utf-8") as f:
        meta = json.load(f)["metadata"]
    assert meta["as_of_date"] == "2026-10-08"
    assert meta["sample_weeks"] == 4
