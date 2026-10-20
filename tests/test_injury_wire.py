"""Tests for enhanced NFL Injury Wire features: practice trends, decoy risk, and depth chart beneficiaries."""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.adapters.nfl.injuries_client import PlayerInjuryReport, nfl_injuries_client, NFLInjuriesClient
from src.adapters.nfl.depthchart_client import TeamDepthChart, DepthChartAthlete, NFLDepthChartClient, nfl_depthchart_client


def test_practice_trend_parsing():
    """Verify various practice progression narratives are accurately categorized."""
    # Setback / Downgrade
    inj_setback = PlayerInjuryReport(
        athlete_id=1,
        name="Star WR",
        position="WR",
        team="KC",
        status="QUESTIONABLE",
        headline="Suffered setback in practice",
        notes="Held out after experiencing hamstring tightness Thursday",
    )
    assert inj_setback.practice_trend == "SETBACK (DNP)"

    # Friday DNP
    inj_fri = PlayerInjuryReport(
        athlete_id=2,
        name="Star RB",
        position="RB",
        team="SF",
        status="QUESTIONABLE",
        headline="Did not practice Friday",
        notes="Missed Friday session due to ankle soreness",
    )
    assert inj_fri.practice_trend == "FRIDAY DNP"

    # Upgraded
    inj_upgrade = PlayerInjuryReport(
        athlete_id=3,
        name="Star TE",
        position="TE",
        team="DET",
        status="QUESTIONABLE",
        headline="Upgraded to full participant Friday",
        notes="Practiced in full after being limited earlier in week",
    )
    assert inj_upgrade.practice_trend == "UPWARD (➔ FP)"


def test_decoy_risk_detection():
    """Verify soft-tissue injuries trigger appropriate decoy trap risk levels."""
    # High decoy risk: Hamstring + DNP
    inj_high = PlayerInjuryReport(
        athlete_id=10,
        name="Deep Threat WR",
        position="WR",
        team="MIA",
        status="QUESTIONABLE",
        headline="Managing hamstring strain",
        notes="Did not practice Friday; game-time decision",
    )
    assert inj_high.decoy_risk == "HIGH"

    # Moderate decoy risk: Groin + Limited
    inj_mod = PlayerInjuryReport(
        athlete_id=11,
        name="Slot WR",
        position="WR",
        team="LAR",
        status="QUESTIONABLE",
        headline="Limited participant with groin issue",
        notes="Participated in individual drills on a limited basis",
    )
    assert inj_mod.decoy_risk == "MODERATE"

    # Non-soft-tissue (e.g. thumb/wrist) should not trigger decoy risk
    inj_none = PlayerInjuryReport(
        athlete_id=12,
        name="QB1",
        position="QB",
        team="BUF",
        status="QUESTIONABLE",
        headline="Thumb contusion",
        notes="Full practice Friday",
    )
    assert inj_none.decoy_risk is None


def test_depthchart_get_next_man_up():
    """Verify TeamDepthChart finds the direct rank-2 backup or slot beneficiary."""
    chart = TeamDepthChart(
        pro_team="KC",
        last_updated=1000.0,
        offense={
            "rb": [
                DepthChartAthlete(athlete_id=101, display_name="Kenneth Walker III", short_name="K. Walker", rank=1, position_slot="rb"),
                DepthChartAthlete(athlete_id=102, display_name="Zach Charbonnet", short_name="Z. Charbonnet", rank=2, position_slot="rb"),
            ],
            "wr1": [
                DepthChartAthlete(athlete_id=201, display_name="Rashee Rice", short_name="R. Rice", rank=1, position_slot="wr1"),
                DepthChartAthlete(athlete_id=202, display_name="Cyrus Allen", short_name="C. Allen", rank=2, position_slot="wr1"),
            ],
        },
    )

    # Kenneth Walker backup should be Zach Charbonnet
    backup_rb = chart.get_next_man_up("Kenneth Walker III", "RB")
    assert backup_rb is not None
    assert backup_rb["display_name"] == "Zach Charbonnet"
    assert backup_rb["rank"] == 2

    # Rashee Rice backup should be Cyrus Allen
    backup_wr = chart.get_next_man_up("Rashee Rice", "WR")
    assert backup_wr is not None
    assert backup_wr["display_name"] == "Cyrus Allen"
    assert backup_wr["rank"] == 2


def test_api_injuries_endpoint_with_force():
    """Test /api/injuries with force=true query parameter."""
    client = TestClient(app)
    resp = client.get("/api/injuries?limit=5&force=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_count" in data
    assert "matched_count" in data
    assert "injuries" in data
    if len(data["injuries"]) > 0:
        item = data["injuries"][0]
        assert "athlete_id" in item
        assert "name" in item
        assert "position" in item
        assert "status" in item
        assert "practice_trend" in item
        assert "decoy_risk" in item
        assert "backup_player_name" in item


def test_practice_nlp_negative_guards():
    """Verify negative guards prevent false positives for practice squad, barring setbacks, and limited action."""
    # Guard 1: "practice squad" should not be marked as practice participation
    inj_ps = PlayerInjuryReport(
        athlete_id=20,
        name="Depth CB",
        position="CB",
        team="PHI",
        status="ACTIVE",
        headline="Signed to active roster",
        notes="Promoted from the practice squad to the active roster Tuesday",
    )
    assert inj_ps.practice_status is None or inj_ps.practice_status == "NOT_REPORTED"

    # Guard 2: "Barring any setbacks" should not trigger SETBACK trend
    inj_barring = PlayerInjuryReport(
        athlete_id=21,
        name="Lead RB",
        position="RB",
        team="NE",
        status="QUESTIONABLE",
        headline="Estimated as full participant",
        notes="Barring any setbacks, he is expected to carry a normal workload Sunday",
    )
    assert inj_barring.practice_trend != "SETBACK (DNP)"

    # Guard 3: "Limited action on Sunday" should not trigger LIMITED practice status
    inj_game_action = PlayerInjuryReport(
        athlete_id=22,
        name="WR3",
        position="WR",
        team="DEN",
        status="ACTIVE",
        headline="Played limited snaps in Week 6",
        notes="Caught 2 passes for 18 yards in limited action during Sunday's game",
    )
    assert inj_game_action.practice_status != "LIMITED"


@pytest.mark.anyio
async def test_offline_disk_fallback_injuries(monkeypatch):
    """Verify NFLInjuriesClient falls back to local data/injuries_live_2026.json when network is offline."""
    import httpx
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Simulated offline network")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = NFLInjuriesClient()
    results = await client.fetch_injuries(force=True)
    assert len(results) == 800
    # Verify 100% of records have non-zero athlete IDs
    assert all(aid > 0 for aid in results.keys())
    # Spot check that practice status and decoy risk are populated
    any_dnp = any(r.practice_status == "DNP" for r in results.values())
    assert any_dnp


@pytest.mark.anyio
async def test_offline_disk_fallback_depthcharts(monkeypatch):
    """Verify NFLDepthChartClient falls back to local data/nfl_depth_charts_2026.json for all 32 teams."""
    import httpx
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Simulated offline network")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    client = NFLDepthChartClient()
    all_charts = await client.fetch_all_depth_charts(force=True)
    assert len(all_charts) >= 32
    for team in ("KC", "SF", "GB", "BUF", "DET", "WAS"):
        assert team in all_charts
        assert all_charts[team].pro_team in ("KC", "SF", "GB", "BUF", "DET", "WAS", "WSH")


@pytest.mark.anyio
async def test_depthchart_washington_abbreviations():
    """Verify both WAS and WSH resolve Washington depth chart cleanly without errors."""
    chart_was = await nfl_depthchart_client.fetch_team_depth_chart("WAS")
    chart_wsh = await nfl_depthchart_client.fetch_team_depth_chart("WSH")
    assert chart_was is not None
    assert chart_wsh is not None
    assert chart_was.pro_team in ("WAS", "WSH")
    assert chart_wsh.pro_team in ("WAS", "WSH")


def test_injury_report_type_aliases_and_team_model():
    """Verify InjuryReport alias and TeamInjuries data structures."""
    from src.adapters.nfl.injuries_client import InjuryReport, TeamInjuries
    assert InjuryReport is PlayerInjuryReport

    report_out = PlayerInjuryReport(athlete_id=101, name="P1", position="RB", team="KC", status="OUT")
    report_q = PlayerInjuryReport(athlete_id=102, name="P2", position="WR", team="KC", status="QUESTIONABLE")
    report_act = PlayerInjuryReport(athlete_id=103, name="P3", position="QB", team="KC", status="ACTIVE")

    team_inj = TeamInjuries(pro_team="KC", injuries=[report_out, report_q, report_act])
    assert team_inj.total_count == 3
    assert team_inj.out_count == 1
    assert team_inj.questionable_count == 1


def test_api_team_abbreviation_filtering():
    """Verify /api/injuries supports team abbreviations like KC, SF, GB, WAS."""
    client = TestClient(app)
    for team_abbr in ("KC", "SF", "GB", "WAS"):
        resp = client.get(f"/api/injuries?team={team_abbr}&limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched_count"] > 0
        for item in data["injuries"]:
            assert item["team_abbr"] == ("WAS" if team_abbr in ("WAS", "WSH") else team_abbr)


def test_api_status_out_filtering_includes_ir():
    """Verify /api/injuries?status=OUT matches all ruled out players including IR, PUP, and OUT."""
    client = TestClient(app)
    resp = client.get("/api/injuries?status=OUT&limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] > 0
    for item in data["injuries"]:
        assert item["is_out"] is True


def test_api_team_alias_wsh_filtering():
    """Verify /api/injuries?team=WSH matches Washington records identically to WAS."""
    client = TestClient(app)
    resp_was = client.get("/api/injuries?team=WAS&limit=50")
    resp_wsh = client.get("/api/injuries?team=WSH&limit=50")
    assert resp_was.status_code == 200
    assert resp_wsh.status_code == 200
    assert resp_was.json()["matched_count"] > 0
    assert resp_wsh.json()["matched_count"] == resp_was.json()["matched_count"]


def test_api_status_ir_filtering():
    """Verify /api/injuries?status=IR matches players with INJURED RESERVE status."""
    client = TestClient(app)
    resp = client.get("/api/injuries?status=IR&limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] > 0
    for item in data["injuries"]:
        assert "IR" in item["status"] or "RESERVE" in item["status"]


def test_api_practice_status_filtering():
    """Verify /api/injuries?practice_status=DNP filters exclusively for DNP players."""
    client = TestClient(app)
    resp = client.get("/api/injuries?practice_status=DNP&limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] > 0
    for item in data["injuries"]:
        assert item["practice_status"] == "DNP"


def test_parenthesized_dnp_parsing():
    """Verify parenthesized (DNP) and trailing punctuation parse properly as DNP."""
    inj = PlayerInjuryReport(
        athlete_id=99,
        name="Test WR",
        position="WR",
        team="KC",
        status="QUESTIONABLE",
        headline="Knee - (DNP)",
    )
    assert inj.practice_status == "DNP"

