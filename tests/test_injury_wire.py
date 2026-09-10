"""Tests for enhanced NFL Injury Wire features: practice trends, decoy risk, and depth chart beneficiaries."""

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.adapters.nfl.injuries_client import PlayerInjuryReport, nfl_injuries_client
from src.adapters.nfl.depthchart_client import TeamDepthChart, DepthChartAthlete


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
