"""Automated tests for DFS REST API endpoints."""

from fastapi.testclient import TestClient


def test_get_dfs_slates(client: TestClient):
    """Test retrieving available DFS slates."""
    res = client.get("/api/dfs/slates")
    assert res.status_code == 200
    slates = res.json()
    assert isinstance(slates, list)
    assert len(slates) >= 2
    slate_ids = [s["id"] for s in slates]
    assert "main" in slate_ids
    assert "early" in slate_ids


def test_get_dfs_slate_data(client: TestClient):
    """Test retrieving enriched DFS slate catalog, stacks, chalk, and leverage targets."""
    res = client.get("/api/dfs/slate-data?slate_id=main")
    assert res.status_code == 200
    data = res.json()
    assert data["slate_id"] == "main"
    assert data["total_players"] > 0
    assert "players" in data
    assert "top_stacks" in data
    assert "leverage_plays" in data
    assert "chalk_plays" in data


def test_optimize_dfs_single_entry_gpp(client: TestClient):
    """Test solving single-entry tournament DFS lineup with correlation stacking."""
    payload = {
        "slate_id": "main",
        "mode": "SINGLE_ENTRY_GPP",
        "min_salary": 58000,
        "max_salary": 60000,
    }
    res = client.post("/api/dfs/optimize", json=payload)
    assert res.status_code == 200
    lineup = res.json()
    assert lineup["mode"] == "SINGLE_ENTRY_GPP"
    assert 58000 <= lineup["total_salary"] <= 60000
    assert len(lineup["roster"]) == 9
    assert lineup["cumulative_ownership"] > 0
    assert "ownership_rating" in lineup
    assert "audit" in lineup


def test_optimize_dfs_cash_mode(client: TestClient):
    """Test solving high-floor cash game DFS lineup."""
    payload = {
        "slate_id": "main",
        "mode": "CASH",
        "min_salary": 58000,
        "max_salary": 60000,
    }
    res = client.post("/api/dfs/optimize", json=payload)
    assert res.status_code == 200
    lineup = res.json()
    assert lineup["mode"] == "CASH"
    assert len(lineup["roster"]) == 9
    assert lineup["total_projected_points"] > 0


def test_upload_slate_csv(client: TestClient):
    """Test uploading a custom FanDuel CSV slate."""
    with open("earlyonlysalariesandrosters.csv", "r", encoding="utf-8") as f:
        csv_content = f.read()

    res = client.post("/api/dfs/upload-slate", json={
        "filename": "earlyonlysalariesandrosters.csv",
        "csv_text": csv_content,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["slate_id"] == "uploaded"
    assert data["total_players"] == 479
    assert len(data["teams"]) >= 14
    assert data["salary_min"] > 0
    assert data["salary_max"] >= 9000
    assert len(data["top_stars"]) == 5


def test_optimize_multi_lineups(client: TestClient):
    """Test generating multiple diverse lineups with portfolio exposure tracking."""
    payload = {
        "slate_id": "main",
        "mode": "SINGLE_ENTRY_GPP",
        "num_lineups": 3,
        "randomness": 0.1,
        "min_salary": 58000,
        "max_salary": 60000,
    }
    res = client.post("/api/dfs/optimize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "lineups" in data
    assert len(data["lineups"]) >= 2
    assert "exposure" in data
    assert len(data["exposure"]) > 0
    # Top exposed player should have percentage
    first_exp = next(iter(data["exposure"].values()))
    assert "pct" in first_exp
    assert first_exp["pct"] > 0


def test_export_lineups_csv(client: TestClient):
    """Test exporting generated lineups to FanDuel CSV upload format."""
    # First optimize a lineup
    payload = {
        "slate_id": "main",
        "mode": "SINGLE_ENTRY_GPP",
        "min_salary": 58000,
        "max_salary": 60000,
    }
    opt_res = client.post("/api/dfs/optimize", json=payload)
    assert opt_res.status_code == 200
    lineup = opt_res.json()

    # Now export
    exp_res = client.post("/api/dfs/export-lineups", json={"lineups": [lineup]})
    assert exp_res.status_code == 200
    export_data = exp_res.json()
    assert "csv_content" in export_data
    assert export_data["filename"] == "fanduel_lineup_import.csv"
    assert "entry_id,contest_id,contest_name,QB,RB,RB,WR,WR,WR,TE,FLEX,DEF" in export_data["csv_content"]


def test_get_slate_data_with_projection_sources(client: TestClient):
    """Test retrieving slate data under different projection sources."""
    for source in ["MODEL", "FANTASYPROS", "SLEEPER", "ESPN", "CONSENSUS"]:
        res = client.get(f"/api/dfs/slate-data?slate_id=main&projection_source={source}")
        assert res.status_code == 200
        data = res.json()
        assert data["projection_source"] == source
        assert len(data["players"]) > 0


def test_optimize_with_projection_source(client: TestClient):
    """Test optimizing lineup under FantasyPros and Consensus projection sources."""
    for source in ["FANTASYPROS", "CONSENSUS"]:
        payload = {
            "slate_id": "main",
            "mode": "SINGLE_ENTRY_GPP",
            "projection_source": source,
            "min_salary": 58000,
            "max_salary": 60000,
        }
        res = client.post("/api/dfs/optimize", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["projection_source"] == source
        assert data["total_projected_points"] > 0
        assert len(data["roster"]) == 9


def test_dfs_opp_soft_rank_is_assigned_accurately(client: TestClient):
    """Test that opponent DvP ranks are assigned accurately and vary across players."""
    res = client.get("/api/dfs/slate-data?slate_id=main")
    assert res.status_code == 200
    players = res.json()["players"]
    ranks = [p["opp_soft_rank"] for p in players if p.get("opp_soft_rank") is not None]
    unique_ranks = set(ranks)
    # Ranks should be diverse, covering all 32 softness tiers, not just all 16
    assert len(unique_ranks) >= 20
    # Must have both soft matchups (<=8) and tough matchups (>=21)
    assert any(r <= 8 for r in ranks)
    assert any(r >= 21 for r in ranks)


