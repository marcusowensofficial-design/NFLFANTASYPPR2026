"""Unit tests for the 2026 NFL Week 2 Expert Consensus Waiver Engine."""

import pytest
from sqlalchemy import select
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.services.recommendation.scoring_engine import scoring_engine
from src.services.waiver.expert_consensus_service import expert_consensus_service
from src.services.waiver.scanner import waiver_scanner


def test_consensus_data_integrity_and_sources():
    """Verify that the 2026 Week 2 consensus database contains 40+ players across all 6 positions
    and is backed by verified national fantasy outlets."""
    data = expert_consensus_service.load_consensus_data()
    assert data["season"] == 2026
    assert 2 <= data["week"] <= 18
    assert "FantasyPros" in data["expert_sources"]
    assert "CBS Sports" in data["expert_sources"]
    assert "NFL.com" in data["expert_sources"]

    positions = data["positions"]
    for expected_pos in ["RB", "WR", "TE", "QB", "DST", "K"]:
        assert expected_pos in positions, f"Missing position {expected_pos} in consensus data"
        assert len(positions[expected_pos]) >= 5, f"Position {expected_pos} must have at least 5 consensus players"

    total_consensus = sum(len(p_list) for p_list in positions.values())
    assert total_consensus >= 45, f"Expected 45+ consensus players, found {total_consensus}"

    # Verify attributes of top consensus players
    top_te = positions["TE"][0]
    assert top_te["rank"] == 1
    assert "full_name" in top_te
    assert "faab_recommended_pct" in top_te
    assert "week_1_metric" in top_te
    assert "expert_rationale" in top_te
    assert len(top_te["expert_sources"]) >= 3


def test_analyze_team_positional_needs_diagnoses_injuries_and_deficits():
    """Verify that team positional needs accurately diagnose Brock Bowers' injury
    and recommend consensus targets for high-need positions."""
    allen = PlayerModel(id=101, full_name="Josh Allen", position="QB", pro_team="BUF", projected_points=23.1, injury_status="ACTIVE")
    bijan = PlayerModel(id=102, full_name="Bijan Robinson", position="RB", pro_team="ATL", projected_points=18.5, injury_status="ACTIVE")
    bowers = PlayerModel(id=103, full_name="Brock Bowers", position="TE", pro_team="LV", projected_points=12.5, injury_status="QUESTIONABLE")
    pierce = PlayerModel(id=104, full_name="Alec Pierce", position="WR", pro_team="IND", projected_points=6.2, injury_status="ACTIVE")

    eval_allen = scoring_engine.evaluate_player(allen, league_size=8)
    eval_bijan = scoring_engine.evaluate_player(bijan, league_size=8)
    eval_bowers = scoring_engine.evaluate_player(bowers, league_size=8)
    eval_pierce = scoring_engine.evaluate_player(pierce, league_size=8)

    needs = expert_consensus_service.analyze_team_positional_needs(
        [eval_allen, eval_bijan, eval_bowers, eval_pierce],
        league_size=8,
    )

    needs_by_pos = {n.position: n for n in needs}

    # 1. TE should be diagnosed with high/critical need due to Questionable starter and no backup
    assert "TE" in needs_by_pos
    assert needs_by_pos["TE"].need_level in ("CRITICAL_NEED", "HIGH_NEED")
    assert any(
        t in needs_by_pos["TE"].recommended_consensus_targets
        for t in (
            "Dalton Kincaid", "Kyle Pitts Sr.", "Darren Waller", "Brenton Strange",
            "T.J. Hockenson", "Tyler Higbee", "Kenyon Sadiq", "Mike Gesicki", "Hunter Henry",
        )
    )

    # 2. QB should be stable with healthy active non-bye Josh Allen
    assert "QB" in needs_by_pos
    assert needs_by_pos["QB"].need_level == "STABLE"


def test_get_consensus_board_with_availability(db_session):
    """Verify that the consensus board correctly tags league wire availability and identifies need matches."""
    league = LeagueModel(id=777, name="Consensus Test League", season=2026, size=8, user_team_id=1)
    team1 = TeamModel(id=1, league_id=777, name="User Team", is_user_team=True)
    team2 = TeamModel(id=2, league_id=777, name="Opponent Team", is_user_team=False)
    db_session.add_all([league, team1, team2])

    raw_consensus = expert_consensus_service.load_consensus_data()
    te_user_info = raw_consensus["positions"]["TE"][0]
    wr_opp_info = raw_consensus["positions"]["WR"][0]
    wr_wire_info = raw_consensus["positions"]["WR"][1]

    te_user_id = te_user_info.get("player_id") or 3116164
    wr_opp_id = wr_opp_info.get("player_id") or 4695883
    wr_wire_id = wr_wire_info.get("player_id") or 4569559

    p_user = PlayerModel(id=te_user_id, full_name=te_user_info["full_name"], position="TE", pro_team=te_user_info["pro_team"], projected_points=10.5)
    p_opp = PlayerModel(id=wr_opp_id, full_name=wr_opp_info["full_name"], position="WR", pro_team=wr_opp_info["pro_team"], projected_points=11.2)
    p_wire = PlayerModel(id=wr_wire_id, full_name=wr_wire_info["full_name"], position="WR", pro_team=wr_wire_info["pro_team"], projected_points=9.8)

    db_session.add_all([p_user, p_opp, p_wire])
    db_session.commit()

    entry_user = RosterEntryModel(id=f"777_1_{te_user_id}", league_id=777, team_id=1, player_id=te_user_id, lineup_slot_id=6, is_starter=True)
    entry_opp = RosterEntryModel(id=f"777_2_{wr_opp_id}", league_id=777, team_id=2, player_id=wr_opp_id, lineup_slot_id=4, is_starter=True)
    db_session.add_all([entry_user, entry_opp])
    db_session.commit()

    needs = [
        expert_consensus_service.analyze_team_positional_needs([], league_size=8)[0]
    ]

    board = expert_consensus_service.get_consensus_board_with_availability(
        db=db_session,
        league_id=777,
        user_team_id=1,
        positional_needs=needs,
    )

    # Check TE board
    te_list = board.get("TE", [])
    user_item = next((p for p in te_list if p.full_name == te_user_info["full_name"]), None)
    assert user_item is not None
    assert user_item.availability_status == "ROSTERED_USER"
    assert not user_item.is_available

    # Check WR board
    wr_list = board.get("WR", [])
    opp_item = next((p for p in wr_list if p.full_name == wr_opp_info["full_name"]), None)
    assert opp_item is not None
    assert opp_item.availability_status == "ROSTERED_OPPONENT"
    assert not opp_item.is_available

    wire_item = next((p for p in wr_list if p.full_name == wr_wire_info["full_name"]), None)
    assert wire_item is not None
    assert wire_item.availability_status == "AVAILABLE"
    assert wire_item.is_available
