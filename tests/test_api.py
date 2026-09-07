from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["season"] == 2026


def test_espn_status_unconfigured(client):
    with patch("src.main.settings.espn_league_id", None):
        response = client.get("/api/espn/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "ESPN_LEAGUE_ID" in data["message"]


def test_lineup_optimal_endpoint(client):
    # Initialize in-memory test database with fixture data
    sync_resp = client.post("/api/league/sync?use_mock=true")
    assert sync_resp.status_code == 200

    response = client.get("/api/lineup/optimal?team_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == 1
    assert len(data["starters"]) == 9
    assert len(data["bench"]) > 0
    assert data["total_start_score"] > 0
    for s in data["starters"]:
        p = s["recommended_player"]
        assert "itemized_stats" in p
        assert "upcoming_schedule" in p


def test_lineup_push_endpoint(client):
    # Initialize in-memory test database
    sync_resp = client.post("/api/league/sync?use_mock=true")
    assert sync_resp.status_code == 200

    # 1. Pre-flight preview mode (confirm=False)
    payload = {
        "team_id": 1,
        "confirm": False,
    }
    response = client.post("/api/lineup/push", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == 1
    assert "moves" in data
    assert "status_message" in data
    assert "can_push_to_espn" in data

    # 2. Confirmed push mode (confirm=True) with mocked ESPN transaction execution
    with patch("src.api.lineup_routes.settings.espn_swid", "{MOCK-SWID}"), \
         patch("src.api.lineup_routes.settings.espn_s2", "MOCK-S2"), \
         patch("src.adapters.espn.client.ESPNClient.execute_roster_transaction", new_callable=AsyncMock) as mock_exec, \
         patch("src.services.espn_sync.ESPNSyncService.sync", new_callable=AsyncMock) as mock_sync:
        mock_exec.return_value = (True, "Successfully updated ESPN lineup with moves!", {"status": "ok"})
        mock_sync.return_value = (True, "Synced", None)
        payload_confirm = {
            "team_id": 1,
            "confirm": True,
            "selected_moves": [{"player_id": 4361579, "from_slot_id": 20, "to_slot_id": 2}],
        }
        resp = client.post("/api/lineup/push", json=payload_confirm)
        assert resp.status_code == 200
        resp_data = resp.json()
        assert resp_data["success"] is True
        assert resp_data["moves_executed"] == 1
        assert "Successfully updated ESPN lineup" in resp_data["message"]


def test_league_players_and_injuries_endpoints(client):
    sync_resp = client.post("/api/league/sync?use_mock=true")
    assert sync_resp.status_code == 200

    # 1. Test /api/league/players
    resp = client.get("/api/league/players")
    assert resp.status_code == 200
    players = resp.json()
    assert len(players) > 0
    p0 = players[0]
    assert "full_name" in p0
    assert "position" in p0
    assert "is_starter" in p0
    assert "is_free_agent" in p0

    # Test filtering by position
    rb_resp = client.get("/api/league/players?position=RB")
    assert rb_resp.status_code == 200
    for r in rb_resp.json():
        assert r["position"] == "RB"

    # 2. Test /api/injuries
    inj_resp = client.get("/api/injuries?limit=10")
    assert inj_resp.status_code == 200
    inj_data = inj_resp.json()
    assert "total_count" in inj_data
    assert "injuries" in inj_data

    # 3. Test /api/recommendation/compare with 2 players
    if len(players) >= 2:
        compare_resp = client.post(
            "/api/recommendation/compare",
            json={"player_ids": [players[0]["id"], players[1]["id"]]},
        )
        assert compare_resp.status_code == 200
        comp_data = compare_resp.json()
        assert "recommended_player_id" in comp_data
        assert "headline" in comp_data
        assert len(comp_data["players"]) == 2


