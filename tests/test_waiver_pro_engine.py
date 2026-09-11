"""Comprehensive test suite for Human-Pro Waiver Wire Intelligence System."""

import pytest
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, TeamModel
from src.services.recommendation.scoring_engine import scoring_engine
from src.services.waiver.scanner import waiver_scanner


def test_bowers_ironclad_protection_and_ir_triage(db_session):
    """Verify that elite stud Brock Bowers (OUT, TE3) is immune from drops and triggers an IR triage recommendation."""
    league = LeagueModel(id=990, name="Pro Waiver League", season=2026, size=8, user_team_id=1)
    team = TeamModel(id=1, league_id=990, name="User Team", is_user_team=True)
    db_session.add_all([league, team])

    # Starting QB and TE
    qb_hurts = PlayerModel(id=901, full_name="Jalen Hurts", position="QB", pro_team="PHI", projected_points=21.0, consensus_rank=3.0)
    te_starter = PlayerModel(id=902, full_name="Juwan Johnson", position="TE", pro_team="NO", projected_points=8.8, consensus_rank=9.0)
    wr_starter = PlayerModel(id=903, full_name="Malik Nabers", position="WR", pro_team="NYG", projected_points=13.8, injury_status="QUESTIONABLE", consensus_rank=20.0)
    db_session.add_all([qb_hurts, te_starter, wr_starter])

    # Bench: Brock Bowers (OUT, TE3, ECR 35) and Alec Pierce (active WR, ECR 52)
    bowers = PlayerModel(id=910, full_name="Brock Bowers", position="TE", pro_team="LV", projected_points=0.0, injury_status="OUT", fp_rank_ecr=35, fp_pos_rank="TE3", fp_tier=4)
    pierce = PlayerModel(id=911, full_name="Alec Pierce", position="WR", pro_team="IND", projected_points=9.7, injury_status="QUESTIONABLE", fp_rank_ecr=52, fp_pos_rank="WR52")
    db_session.add_all([bowers, pierce])
    db_session.commit()

    entry_qb = RosterEntryModel(id="990_1_901", league_id=990, team_id=1, player_id=901, lineup_slot_id=0, is_starter=True)
    entry_te = RosterEntryModel(id="990_1_902", league_id=990, team_id=1, player_id=902, lineup_slot_id=6, is_starter=True)
    entry_wr = RosterEntryModel(id="990_1_903", league_id=990, team_id=1, player_id=903, lineup_slot_id=4, is_starter=True)
    entry_bowers = RosterEntryModel(id="990_1_910", league_id=990, team_id=1, player_id=910, lineup_slot_id=20, is_starter=False)
    entry_pierce = RosterEntryModel(id="990_1_911", league_id=990, team_id=1, player_id=911, lineup_slot_id=20, is_starter=False)
    db_session.add_all([entry_qb, entry_te, entry_wr, entry_bowers, entry_pierce])
    db_session.commit()

    # Free agent pool: Drake London (alpha WR), Caleb Williams (QB), Jake Bates (Kicker)
    fa_london = PlayerModel(id=920, full_name="Drake London", position="WR", pro_team="ATL", projected_points=15.4, fp_rank_ecr=10, fp_pos_rank="WR10")
    fa_caleb = PlayerModel(id=921, full_name="Caleb Williams", position="QB", pro_team="CHI", projected_points=16.5, fp_rank_ecr=7)
    fa_kicker = PlayerModel(id=922, full_name="Jake Bates", position="K", pro_team="DET", projected_points=11.8)
    db_session.add_all([fa_london, fa_caleb, fa_kicker])
    db_session.commit()

    user_evals = [
        scoring_engine.evaluate_player(qb_hurts, league_size=8),
        scoring_engine.evaluate_player(te_starter, league_size=8),
        scoring_engine.evaluate_player(wr_starter, league_size=8),
        scoring_engine.evaluate_player(bowers, league_size=8),
        scoring_engine.evaluate_player(pierce, league_size=8),
    ]

    scan_res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=990,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        free_agent_pool=[fa_london, fa_caleb, fa_kicker],
        league_size=8,
        current_week=1,
    )

    # 1. Brock Bowers is NEVER dropped
    drop_pids = [u.drop_player.player_id for u in scan_res.top_upgrades if u.drop_player]
    assert 910 not in drop_pids, "Brock Bowers must NEVER be recommended to be dropped!"

    # 2. Alec Pierce is the recommended drop candidate
    assert 911 in drop_pids, "Alec Pierce must be designated as the expendable drop candidate."

    # 3. IR recommendation generated for Bowers
    assert len(scan_res.ir_recommendations) > 0
    assert scan_res.ir_recommendations[0].player_id == 910
    assert "Move Brock Bowers" in scan_res.ir_recommendations[0].action_headline
    assert scan_res.ir_recommendations[0].suggested_wire_add == "Drake London"

    # 4. Kicker and backup QB quarantined from top upgrades
    pickup_names = [u.pickup_player.full_name for u in scan_res.top_upgrades]
    assert "Jake Bates" not in pickup_names, "Kickers must be quarantined from top upgrades."
    assert "Caleb Williams" not in pickup_names, "Backup QBs must be suppressed when user has healthy starter Jalen Hurts."

    # 5. Top upgrade is Drake London with MUST_ADD urgency and FAAB guidance
    assert len(scan_res.top_upgrades) > 0
    top_upg = scan_res.top_upgrades[0]
    assert top_upg.pickup_player.player_id == 920
    assert top_upg.urgency_tier == "MUST_ADD"
    assert top_upg.faab_recommended_pct >= 20
    assert top_upg.faab_recommended_amount >= 20
    assert top_upg.action_type == "MOVE_TO_IR_AND_ADD"
    assert "Drake London" in top_upg.catalyst

    # 6. Bench Security Ledger
    assert len(scan_res.bench_security_ledger) == 2
    ledger_map = {b.player_id: b for b in scan_res.bench_security_ledger}
    assert ledger_map[910].security_tier == "UNTOUCHABLE_CORE"
    assert ledger_map[910].cut_safety_score == 0.0
    assert ledger_map[911].security_tier == "EXPENDABLE_CUT"
    assert ledger_map[911].cut_safety_score > 70.0

    # 7. Deadweight drops does NOT contain Brock Bowers
    dw_pids = [d.player_id for d in scan_res.deadweight_drops]
    assert 910 not in dw_pids, "Brock Bowers must NEVER be flagged as deadweight!"


def test_league_ownership_name_shield_blocks_ghost_duplicates(db_session):
    """Verify that if a player (e.g. Drake London) is owned on another team (Team 2),
    he is NEVER recommended on waivers, even if an unowned ghost record with a different ID exists."""
    league = LeagueModel(id=991, name="Multi-Team Shield League", season=2026, size=8, user_team_id=1)
    team1 = TeamModel(id=1, league_id=991, name="Blind Horse Named Dank", is_user_team=True)
    team2 = TeamModel(id=2, league_id=991, name="Mickey's Team", is_user_team=False)
    db_session.add_all([league, team1, team2])

    # Team 1 user starter
    starter = PlayerModel(id=801, full_name="Malik Nabers", position="WR", pro_team="NYG", projected_points=14.0)
    # Team 2 owns Drake London under ID 4426502
    mickey_london = PlayerModel(id=4426502, full_name="Drake London", position="WR", pro_team="ATL", projected_points=15.4)
    # Ghost unrostered record in DB with different ID 4258183
    ghost_london = PlayerModel(id=4258183, full_name="Drake London", position="WR", pro_team="ATL", projected_points=15.4)
    # Legit unowned free agent
    legit_fa = PlayerModel(id=805, full_name="Quentin Johnston", position="WR", pro_team="LAC", projected_points=10.5)

    db_session.add_all([starter, mickey_london, ghost_london, legit_fa])
    db_session.commit()

    entry_user = RosterEntryModel(id="991_1_801", league_id=991, team_id=1, player_id=801, lineup_slot_id=4, is_starter=True)
    entry_mickey = RosterEntryModel(id="991_2_4426502", league_id=991, team_id=2, player_id=4426502, lineup_slot_id=4, is_starter=True)
    db_session.add_all([entry_user, entry_mickey])
    db_session.commit()

    user_evals = [scoring_engine.evaluate_player(starter, league_size=8)]

    # Run waiver scan without passing free_agent_pool, letting it scan DB directly
    scan_res = waiver_scanner.scan_upgrades(
        db=db_session,
        league_id=991,
        user_team_id=1,
        user_roster_evaluations=user_evals,
        league_size=8,
    )

    pickup_names = [u.pickup_player.full_name for u in scan_res.top_upgrades]
    assert "Drake London" not in pickup_names, "Drake London is rostered by Mickey's Team and must NEVER be recommended as a free agent!"
    assert any("Quentin Johnston" in name for name in pickup_names), "Legitimate free agent should be recommended."
