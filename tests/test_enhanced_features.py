"""Tests for projection source parity, factor score alignment, settings persistence, and inactives alert."""

import pytest
from fastapi.testclient import TestClient


def test_compare_with_projection_source(client: TestClient):
    """Test that compare endpoint accepts projection_source and recalculates calibrated start_score."""
    # First ensure mock league is synced
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    # Get players from team 1 via optimal lineup
    lineup_res = client.get("/api/lineup/optimal?team_id=1")
    assert lineup_res.status_code == 200
    starters = lineup_res.json()["starters"]
    assert len(starters) >= 2
    pid1 = starters[0]["recommended_player"]["player_id"]
    pid2 = starters[1]["recommended_player"]["player_id"]

    # Compare with MODEL
    res_model = client.post(
        "/api/recommendation/compare",
        json={"player_ids": [pid1, pid2], "mode": "BALANCED", "projection_source": "MODEL"},
    )
    assert res_model.status_code == 200
    data_model = res_model.json()
    assert "recommended_player_id" in data_model
    assert len(data_model["players"]) == 2

    # Verify that start_score is a valid number in [0, 100]
    p0 = data_model["players"][0]
    assert 0.0 <= p0["start_score"] <= 100.0
    assert p0["comparator_factors"] is not None

    # Compare with FANTASYPROS
    res_fp = client.post(
        "/api/recommendation/compare",
        json={"player_ids": [pid1, pid2], "mode": "BALANCED", "projection_source": "FANTASYPROS"},
    )
    assert res_fp.status_code == 200
    data_fp = res_fp.json()
    assert "recommended_player_id" in data_fp


def test_settings_persistence_sqlite(client: TestClient):
    """Test that updating scoring settings and weights persists to the database."""
    # Update settings
    new_settings = {
        "league_size": 10,
        "weights": {
            "projection_weight": 0.40,
            "opportunity_weight": 0.20,
            "matchup_weight": 0.20,
            "environment_weight": 0.10,
            "health_weight": 0.05,
            "weather_weight": 0.05,
        },
    }
    update_res = client.post("/api/recommendation/settings", json=new_settings)
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["league_size"] == 10
    assert data["weights"]["projection_weight"] == 0.40

    # Retrieve settings in new request
    get_res = client.get("/api/recommendation/settings")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["league_size"] == 10
    assert retrieved["weights"]["projection_weight"] == 0.40

    # Reset back to default 8-team standard weights for subsequent tests
    reset_settings = {
        "league_size": 8,
        "weights": {
            "projection_weight": 0.35,
            "opportunity_weight": 0.20,
            "matchup_weight": 0.20,
            "environment_weight": 0.10,
            "health_weight": 0.10,
            "weather_weight": 0.05,
        },
    }
    client.post("/api/recommendation/settings", json=reset_settings)


def test_inactives_alert_endpoint(client: TestClient):
    """Test that the inactives alert sweeper endpoint returns a valid response structure."""
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    alert_res = client.get("/api/lineup/inactives-alert?team_id=1")
    assert alert_res.status_code == 200
    data = alert_res.json()
    assert "team_id" in data
    assert "has_critical_inactives" in data
    assert "alerts_count" in data
    assert "alerts" in data
    assert isinstance(data["alerts"], list)
