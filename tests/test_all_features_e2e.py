"""Comprehensive integration and end-to-end tests for all phases and API endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.main import app


def test_full_application_lifecycle_e2e(client):
    """Test the complete workflow across all 8 phases."""
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. Sync mock league data
    res = client.post("/api/league/sync?use_mock=true&force=true")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. League summary & teams
    res = client.get("/api/league/summary")
    assert res.status_code == 200
    summary = res.json()
    assert len(summary["teams"]) in [8, 10]

    res = client.get("/api/league/teams")
    assert res.status_code == 200
    teams = res.json()
    assert len(teams) in [8, 10]

    # 4. Team roster details
    res = client.get("/api/league/teams/1/roster")
    assert res.status_code == 200
    roster_data = res.json()
    assert roster_data["team_id"] == 1
    assert len(roster_data["roster"]) > 0

    # 5. Lineup optimizer (Phase 5)
    res = client.get("/api/lineup/optimal?team_id=1")
    assert res.status_code == 200
    lineup = res.json()
    assert len(lineup["starters"]) == 9  # 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K
    assert lineup["total_projected_points"] > 0
    assert lineup["total_start_score"] > 0

    # 6. Recommendation comparator (Phase 4)
    starter_ids = [lineup["starters"][0]["recommended_player"]["player_id"], lineup["starters"][1]["recommended_player"]["player_id"]]
    res = client.post("/api/recommendation/compare", json={"player_ids": starter_ids})
    assert res.status_code == 200
    comp = res.json()
    assert len(comp["players"]) == 2
    assert comp["recommended_player_id"] in starter_ids

    # 7. Weights management (Phase 4)
    res = client.get("/api/recommendation/weights")
    assert res.status_code == 200
    cur_weights = res.json()
    assert "projection_weight" in cur_weights

    new_weights = {**cur_weights, "projection_weight": 0.40, "opportunity_weight": 0.15}
    res = client.post("/api/recommendation/weights", json=new_weights)
    assert res.status_code == 200
    assert res.json()["projection_weight"] == 0.40
    # Restore original weights so other tests remain isolated
    client.post("/api/recommendation/weights", json=cur_weights)


    # 8. Waiver upgrades scanner (Phase 6)
    res = client.get("/api/waiver/upgrades?team_id=1")
    assert res.status_code == 200
    waivers = res.json()
    assert "top_upgrades" in waivers
    assert "streaming_dst" in waivers
    assert "streaming_te" in waivers

    # 9. Backtest report & automated tuning (Phase 8)
    res = client.get("/api/backtest/report?team_id=1")
    assert res.status_code == 200
    report = res.json()
    assert report["total_weeks_audited"] >= 1
    assert "overall_accuracy_pct" in report

    res = client.post("/api/backtest/tune?team_id=1")
    assert res.status_code == 200
    tune_res = res.json()
    assert "optimized_weights" in tune_res
    assert "message" in tune_res
    assert "original_accuracy_pct" in tune_res

