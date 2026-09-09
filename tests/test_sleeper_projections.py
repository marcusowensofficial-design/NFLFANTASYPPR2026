"""Tests for Sleeper / RotoWire weekly projections integration."""

from fastapi.testclient import TestClient
from src.adapters.sleeper import normalize_sleeper_stats


def test_normalize_sleeper_stats():
    """Verify that raw Sleeper/RotoWire stat keys map properly to unified schema."""
    raw = {
        "pass_att": 35.0,
        "pass_cmp": 22.0,
        "pass_yd": 280.0,
        "pass_td": 2.0,
        "pass_int": 1.0,
        "rush_att": 3.0,
        "rush_yd": 15.0,
        "rush_td": 0.0,
        "rec_tgt": 0.0,
        "rec": 0.0,
        "rec_yd": 0.0,
        "rec_td": 0.0,
        "pts_ppr": 20.7,
    }
    norm = normalize_sleeper_stats(raw)
    assert norm["pass_att"] == 35.0
    assert norm["pass_yds"] == 280.0
    assert norm["pass_tds"] == 2.0
    assert norm["pass_ints"] == 1.0
    assert norm["calculated_ppr"] == 20.7


def test_sleeper_sync_service(client: TestClient):
    """Test that Sleeper sync endpoint runs and populates database players."""
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    sleeper_res = client.post("/api/sleeper/sync?season=2024&week=1")
    assert sleeper_res.status_code == 200
    data = sleeper_res.json()
    assert data["success"] is True
    assert data["enriched_count"] > 0


def test_optimal_lineup_with_sleeper_source(client: TestClient):
    """Test that /api/lineup/optimal resolves successfully with projection_source=SLEEPER."""
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    client.post("/api/sleeper/sync?season=2024&week=1")

    resp = client.get("/api/lineup/optimal?team_id=1&mode=BALANCED&projection_source=SLEEPER")
    assert resp.status_code == 200
    data = resp.json()
    assert data["projection_source"] == "SLEEPER"
    assert data["total_projected_points"] > 0
    assert data["total_sleeper_projected"] > 0
    starters = data.get("starters", [])
    assert len(starters) > 0
    for s in starters:
        p = s.get("recommended_player", {})
        assert p.get("active_projection_source") == "SLEEPER"
        assert p.get("proj_sleeper") is not None


def test_compare_with_sleeper_source(client: TestClient):
    """Test that /api/recommendation/compare accepts projection_source=SLEEPER."""
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    client.post("/api/sleeper/sync?season=2024&week=1")

    lineup_res = client.get("/api/lineup/optimal?team_id=1&projection_source=SLEEPER")
    assert lineup_res.status_code == 200
    starters = lineup_res.json()["starters"]
    assert len(starters) >= 2
    pid1 = starters[0]["recommended_player"]["player_id"]
    pid2 = starters[1]["recommended_player"]["player_id"]

    res_sleeper = client.post(
        "/api/recommendation/compare",
        json={"player_ids": [pid1, pid2], "mode": "BALANCED", "projection_source": "SLEEPER"},
    )
    assert res_sleeper.status_code == 200
    data = res_sleeper.json()
    assert "recommended_player_id" in data
    assert len(data["players"]) == 2
    p0 = data["players"][0]
    assert p0["active_projection_source"] == "SLEEPER"
    assert p0["proj_sleeper"] is not None
