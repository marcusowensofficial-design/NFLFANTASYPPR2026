"""Unit and directionality tests for Start/Sit Comparator Factor Scores."""

import pytest
from src.services.recommendation.start_sit_factor_scores import (
    calculate_start_sit_projection_score,
    calculate_start_sit_opportunity_score,
    calculate_start_sit_matchup_score,
    calculate_start_sit_environment_score,
    calculate_comparator_factors_for_evaluation,
)
from src.adapters.nfl.schedule_client import NFLGame
from src.adapters.weather.client import WeatherReport
from src.services.recommendation.scoring_engine import StartSitEvaluation, ComponentScores


# ============================================================================
# 1. PROJECTION SCORE TESTS
# ============================================================================

def test_projection_score_monotonicity_within_position():
    """Higher projected PPR points within a position must strictly produce equal or higher Projection Score."""
    projections = [5.0, 8.0, 10.5, 12.0, 14.5, 16.0, 18.5, 21.0, 24.0, 28.0]
    
    for pos in ["WR", "RB", "QB", "TE"]:
        scores = [
            calculate_start_sit_projection_score(p, pos).score
            for p in projections
        ]
        # Verify monotonically non-decreasing
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], (
                f"Monotonicity violation at {pos}: proj {projections[i]} -> {scores[i]} "
                f"exceeds proj {projections[i+1]} -> {scores[i+1]}"
            )


def test_projection_score_bucket_boundaries():
    """Verify distinct score buckets (ELITE, STRONG, VIABLE, WEAK) for WR."""
    weak_res = calculate_start_sit_projection_score(7.0, "WR")
    assert weak_res.bucket == "WEAK"
    assert weak_res.score < 50.0

    viable_res = calculate_start_sit_projection_score(12.0, "WR")
    assert viable_res.bucket == "VIABLE"
    assert 50.0 <= viable_res.score < 70.0

    strong_res = calculate_start_sit_projection_score(16.5, "WR")
    assert strong_res.bucket == "STRONG"
    assert 70.0 <= strong_res.score < 85.0

    elite_res = calculate_start_sit_projection_score(23.0, "WR")
    assert elite_res.bucket == "ELITE"
    assert elite_res.score >= 85.0


def test_projection_score_consensus_modifier_bounded():
    """Analyst consensus modifier must be bounded and not allow a materially inferior projection to beat a superior one."""
    high_proj_poor_rank = calculate_start_sit_projection_score(18.0, "WR", consensus_rank=40.0)
    low_proj_great_rank = calculate_start_sit_projection_score(12.0, "WR", consensus_rank=2.0)

    assert high_proj_poor_rank.score > low_proj_great_rank.score, (
        f"Materially higher projection ({high_proj_poor_rank.score}) must exceed lower projection ({low_proj_great_rank.score})"
    )


# ============================================================================
# 2. OPPORTUNITY VOLUME TESTS
# ============================================================================

def test_wr_5_9_targets_capped_at_viable():
    """A WR with 5.9 projected targets must NOT receive an Elite or Strong volume score."""
    res = calculate_start_sit_opportunity_score(
        "WR",
        stats={"targets": 5.9, "receptions": 3.8, "rush_att": 0.0, "rec_td": 0.3},
        volume_share=16.5,
    )
    assert res.score < 70.0, f"WR with 5.9 targets scored {res.score}, must be capped below 70.0"
    assert res.bucket in ("VIABLE", "WEAK")
    assert res.raw_inputs["volume_cap_applied"] is True


def test_wr_opportunity_monotonicity():
    """Increasing WR targets strictly increases or maintains Opportunity Volume."""
    target_levels = [3.0, 5.0, 6.5, 8.0, 10.0, 12.0]
    scores = [
        calculate_start_sit_opportunity_score("WR", {"targets": t, "receptions": t * 0.68}).score
        for t in target_levels
    ]
    for i in range(len(scores) - 1):
        assert scores[i] <= scores[i + 1]


def test_rb_high_value_touches_ppr_multiplier():
    """RB with PPR targets produces higher opportunity than rush-only back with same touch count."""
    workhorse_receiver = calculate_start_sit_opportunity_score(
        "RB",
        stats={"rush_att": 12.0, "targets": 6.0, "rush_td": 0.5},
        volume_share=65.0,
    )
    plodder_ground = calculate_start_sit_opportunity_score(
        "RB",
        stats={"rush_att": 18.0, "targets": 0.0, "rush_td": 0.5},
        volume_share=65.0,
    )
    # 12 carries + 6 targets (18 touches, with 6 HVTs) vs 18 carries + 0 targets
    assert workhorse_receiver.score > plodder_ground.score


def test_qb_konami_rush_opportunity():
    """QB rushing attempts provide significant opportunity boost over statue pocket passer."""
    mobile_qb = calculate_start_sit_opportunity_score("QB", {"pass_att": 30.0, "rush_att": 6.0, "rush_yds": 42.0})
    statue_qb = calculate_start_sit_opportunity_score("QB", {"pass_att": 30.0, "rush_att": 0.5, "rush_yds": 2.0})
    assert mobile_qb.score > statue_qb.score + 10.0


# ============================================================================
# 3. DEFENSIVE MATCHUP TESTS
# ============================================================================

def test_defensive_matchup_directionality():
    """Easier opponent (higher DvP rank) must produce a higher matchup score than tough defense (lower DvP rank)."""
    # BAL is DvP #5 vs WR (tough), CAR is DvP #31 vs WR (soft)
    tough_res = calculate_start_sit_matchup_score("WR", "BAL")
    soft_res = calculate_start_sit_matchup_score("WR", "CAR")

    assert soft_res.score > tough_res.score
    assert tough_res.score < 50.0  # Tough opponent yields lower score
    assert soft_res.score >= 75.0   # Soft opponent yields high score
    assert soft_res.bucket in ("SMASH", "FAVORABLE")
    assert tough_res.bucket in ("BRUTAL", "TOUGH")


def test_lockdown_defense_reconciles_with_copy():
    """A top-3 defense vs position yields a low score and driver alerts."""
    lockdown = calculate_start_sit_matchup_score("WR", "NYJ") # NYJ is #1 vs WR
    assert lockdown.score < 40.0
    assert lockdown.bucket == "BRUTAL"
    assert any("Lockdown" in r or "stifling" in r for r in lockdown.reasons)


# ============================================================================
# 4. GAME ENVIRONMENT TESTS
# ============================================================================

def test_game_environment_implied_total_directionality():
    """Higher team implied total yields higher environment score."""
    game_high = NFLGame(
        id="G1", name="KC vs BUF", date="2026-09-10T20:00:00Z", venue_name="Arrowhead",
        home_team="KC", away_team="BUF", home_score=0, away_score=0,
        spread=-2.5, over_under=51.0, home_implied_total=26.75, away_implied_total=24.25,
        is_finished=False,
    )
    game_low = NFLGame(
        id="G2", name="NE vs TEN", date="2026-09-13T13:00:00Z", venue_name="Gillette",
        home_team="NE", away_team="TEN", home_score=0, away_score=0,
        spread=-1.0, over_under=39.0, home_implied_total=20.0, away_implied_total=19.0,
        is_finished=False,
    )
    res_high = calculate_start_sit_environment_score("WR", game_high, pro_team="KC")
    res_low = calculate_start_sit_environment_score("WR", game_low, pro_team="NE")

    assert res_high.score > res_low.score
    assert res_high.bucket in ("SHOOTOUT", "FAVORABLE")
    assert res_low.bucket in ("AVERAGE", "HOSTILE")


def test_weather_dome_vs_high_wind():
    """Climate-controlled dome removes weather friction compared to 22 mph adverse wind."""
    dome_weather = WeatherReport(team="DET", temperature_f=72.0, wind_speed_mph=0.0, is_dome=True)
    wind_weather = WeatherReport(team="CLE", temperature_f=38.0, wind_speed_mph=22.0, is_dome=False)

    dome_res = calculate_start_sit_environment_score("WR", weather=dome_weather)
    wind_res = calculate_start_sit_environment_score("WR", weather=wind_weather)

    assert dome_res.score > wind_res.score
    assert dome_res.raw_inputs["is_dome"] is True
    assert wind_res.raw_inputs["wind_speed_mph"] == 22.0


# ============================================================================
# 5. MASTER BUNDLE & EVALUATION PARITY
# ============================================================================

def test_calculate_comparator_factors_for_evaluation():
    """Verify that bundle calculates all 4 factors and generates correct structure."""
    ev = StartSitEvaluation(
        player_id=101,
        full_name="Justin Jefferson",
        position="WR",
        pro_team="MIN",
        projected_points=18.4,
        start_score=84.2,
        confidence="HIGH",
        recommendation="STRONG START",
        matchup_grade="FAVORABLE",
        opponent="CAR",
        is_home=True,
        implied_team_total=25.5,
        injury_status="ACTIVE",
        itemized_stats={"targets": 9.2, "receptions": 6.8, "rec_yds": 92.0, "rec_td": 0.6},
        volume_share=27.5,
        opp_dvp_rank=31,
    )

    bundle = calculate_comparator_factors_for_evaluation(ev)
    assert bundle.projection.score >= 80.0
    assert bundle.opportunity.score >= 80.0
    assert bundle.matchup.score >= 75.0
    assert bundle.environment.score >= 60.0

    # Ensure all components have non-empty provenance descriptions and reasons
    assert bundle.projection.formula_description
    assert len(bundle.projection.reasons) > 0
    assert bundle.opportunity.formula_description
    assert len(bundle.opportunity.reasons) > 0


# ============================================================================
# 6. API ENDPOINT INTEGRATION & STRICT SCOPE ISOLATION TESTS
# ============================================================================

def test_compare_api_endpoint_integration(client):
    """Verify POST /api/recommendation/compare returns enriched comparator_factors matching component scores."""
    # Ensure test database has players
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    # Get players
    players_res = client.get("/api/league/players")
    assert players_res.status_code == 200
    players = players_res.json()
    assert len(players) >= 2

    p1_id = players[0]["id"]
    p2_id = players[1]["id"]

    res = client.post("/api/recommendation/compare", json={"player_ids": [p1_id, p2_id], "mode": "BALANCED"})
    assert res.status_code == 200
    data = res.json()

    assert "players" in data
    assert len(data["players"]) == 2

    for p in data["players"]:
        # Verify comparator_factors bundle is present
        assert "comparator_factors" in p
        cf = p["comparator_factors"]
        assert cf is not None
        assert "projection" in cf
        assert "opportunity" in cf
        assert "matchup" in cf
        assert "environment" in cf

        # Verify exact mathematical parity with the displayed component scores
        comps = p["components"]
        assert comps["projection_score"] == cf["projection"]["score"]
        assert comps["opportunity_score"] == cf["opportunity"]["score"]
        assert comps["matchup_score"] == cf["matchup"]["score"]
        assert comps["environment_score"] == cf["environment"]["score"]

        # Verify transparent formula fields
        assert "raw_inputs" in cf["projection"]
        assert "contributions" in cf["projection"]
        assert "formula_description" in cf["projection"]
        assert "bucket" in cf["projection"]


def test_scope_isolation_no_other_tools_affected(client):
    """Verify that global weights, settings, and other endpoints remain 100% untouched."""
    # 1. Check scoring weights endpoint
    weights_res = client.get("/api/recommendation/weights")
    assert weights_res.status_code == 200
    w = weights_res.json()
    assert w["projection_weight"] == 0.35
    assert w["opportunity_weight"] == 0.20
    assert w["matchup_weight"] == 0.20
    assert w["environment_weight"] == 0.10
    assert w["health_weight"] == 0.10
    assert w["weather_weight"] == 0.05

    # 2. Check lineup optimizer endpoint produces standard structure without tampering
    sync_res = client.post("/api/league/sync?use_mock=true")
    assert sync_res.status_code == 200

    lineup_res = client.get("/api/lineup/optimal?team_id=1")
    assert lineup_res.status_code == 200
    lineup_data = lineup_res.json()
    assert len(lineup_data["starters"]) == 9
    assert lineup_data["total_start_score"] > 0
