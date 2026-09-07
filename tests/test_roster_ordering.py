"""Unit tests validating canonical fantasy slot ordering across optimal lineup and team rosters."""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.optimizer.lineup_optimizer import SLOT_ORDER


@pytest.fixture
def client():
    return TestClient(app)


def test_slot_order_hierarchy_values():
    """Ensure SLOT_ORDER correctly places K before D/ST and FLEX before K."""
    assert SLOT_ORDER["QB"] < SLOT_ORDER["RB"]
    assert SLOT_ORDER["RB"] < SLOT_ORDER["WR"]
    assert SLOT_ORDER["WR"] < SLOT_ORDER["TE"]
    assert SLOT_ORDER["TE"] < SLOT_ORDER["FLEX"]
    assert SLOT_ORDER["FLEX"] < SLOT_ORDER["K"]
    assert SLOT_ORDER["K"] < SLOT_ORDER["D/ST"]
    assert SLOT_ORDER["D/ST"] < SLOT_ORDER["BE"]
    assert SLOT_ORDER["BE"] < SLOT_ORDER["IR"]


def test_optimal_lineup_starter_ordering(client):
    """Verify that /api/lineup/optimal returns starters in exact canonical fantasy order:
    QB, RB, RB, WR, WR, TE, FLEX, K, D/ST.
    """
    resp = client.get("/api/lineup/optimal?team_id=1&mode=BALANCED")
    assert resp.status_code == 200
    data = resp.json()

    starters = data["starters"]
    starter_slot_names = [s["slot_name"] for s in starters]

    # Verify positions sequence
    expected_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "D/ST"]
    assert starter_slot_names == expected_slots, f"Got: {starter_slot_names}"

    # Verify bench count and IR slots
    assert len(data["bench"]) == 7
    assert data["bench_slots_count"] == 7
    assert data["ir_slots_count"] == 1
    assert len(data["ir"]) == 0  # 0 players on IR = 1 FREE SPOT


def test_team_roster_ordering_in_league_api(client):
    """Verify that /api/league/teams/1/roster returns players in canonical fantasy order
    with FLEX positioned between TE and K, not after the bench.
    """
    resp = client.get("/api/league/teams/1/roster")
    assert resp.status_code == 200
    data = resp.json()

    roster = data["roster"]
    slot_names = [p["slot_name"] for p in roster]

    # First 9 slots must be starters in order
    expected_starter_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "D/ST"]
    assert slot_names[:9] == expected_starter_slots, f"Got: {slot_names[:9]}"

    # Next 7 slots must be bench (BE)
    assert all(s == "BE" for s in slot_names[9:]), f"Remaining slots: {slot_names[9:]}"
    assert len(slot_names[9:]) == 7
