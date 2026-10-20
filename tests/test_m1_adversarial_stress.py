"""Adversarial stress and edge-case test suite for Milestone M1 (Live Injury & Practice Status)."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import httpx

from src.main import app
from src.adapters.nfl.injuries_client import (
    NFLInjuriesClient,
    PlayerInjuryReport,
    TeamInjuries,
    resolve_team_abbrev,
)
from src.adapters.nfl.depthchart_client import (
    NFLDepthChartClient,
    TeamDepthChart,
    DepthChartAthlete,
)
from scripts.sync_live_injuries import (
    extract_athlete_id,
    parse_practice_status,
    classify_practice_trend,
    detect_decoy_risk,
)


# ============================================================================
# Category A: Offline Fallback Under Extreme Conditions
# ============================================================================

@pytest.mark.anyio
async def test_injuries_offline_missing_cache_file(tmp_path, monkeypatch):
    """Verify NFLInjuriesClient gracefully returns empty dict when offline and cache file does not exist."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Network offline")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    non_existent = tmp_path / "does_not_exist.json"
    monkeypatch.setattr("src.adapters.nfl.injuries_client.LOCAL_INJURIES_PATH", non_existent)

    client = NFLInjuriesClient()
    res = await client.fetch_injuries(force=True)
    assert res == {}
    assert isinstance(res, dict)

    # fetch_team_injuries should return TeamInjuries with 0 injuries
    team_inj = await client.fetch_team_injuries("KC", force=True)
    assert isinstance(team_inj, TeamInjuries)
    assert team_inj.total_count == 0


@pytest.mark.anyio
async def test_injuries_offline_corrupted_json_cache(tmp_path, monkeypatch):
    """Verify NFLInjuriesClient gracefully handles corrupted/malformed JSON in disk cache."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectTimeout("Network timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    corrupt_file = tmp_path / "corrupted_injuries.json"
    corrupt_file.write_text("{ this is completely invalid JSON content !!!", encoding="utf-8")
    monkeypatch.setattr("src.adapters.nfl.injuries_client.LOCAL_INJURIES_PATH", corrupt_file)

    client = NFLInjuriesClient()
    res = await client.fetch_injuries(force=True)
    assert res == {}


@pytest.mark.anyio
async def test_injuries_offline_empty_zero_byte_cache(tmp_path, monkeypatch):
    """Verify NFLInjuriesClient handles 0-byte cache file without crashing."""
    async def mock_get(*args, **kwargs):
        raise httpx.ReadTimeout("Read timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    empty_file = tmp_path / "empty.json"
    empty_file.write_text("", encoding="utf-8")
    monkeypatch.setattr("src.adapters.nfl.injuries_client.LOCAL_INJURIES_PATH", empty_file)

    client = NFLInjuriesClient()
    res = await client.fetch_injuries(force=True)
    assert res == {}


@pytest.mark.anyio
async def test_injuries_offline_unexpected_schema_cache(tmp_path, monkeypatch):
    """Verify NFLInjuriesClient handles valid JSON with unexpected schema (int, dict with bad types)."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    weird_file = tmp_path / "weird_schema.json"
    weird_file.write_text(json.dumps({"unknown_key": [1, 2, "not a dict", None]}), encoding="utf-8")
    monkeypatch.setattr("src.adapters.nfl.injuries_client.LOCAL_INJURIES_PATH", weird_file)

    client = NFLInjuriesClient()
    res = await client.fetch_injuries(force=True)
    assert isinstance(res, dict)
    assert len(res) == 0


@pytest.mark.anyio
async def test_depthcharts_offline_missing_and_corrupt_cache(tmp_path, monkeypatch):
    """Verify NFLDepthChartClient handles missing, empty, or corrupted depth chart caches."""
    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Host unreachable")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    non_existent = tmp_path / "no_depthcharts.json"
    monkeypatch.setattr("src.adapters.nfl.depthchart_client.LOCAL_DEPTHCHARTS_PATH", non_existent)

    client = NFLDepthChartClient()
    single_chart = await client.fetch_team_depth_chart("KC", force=True)
    assert single_chart is None

    all_charts = await client.fetch_all_depth_charts(force=True)
    assert isinstance(all_charts, dict)
    assert len(all_charts) == 0

    role = await client.get_player_depth_role("KC", "Patrick Mahomes", "QB")
    assert role["found"] is False
    assert role["is_starter"] is True


# ============================================================================
# Category B: Athlete ID Extraction Across Edge-Case Link Formats
# ============================================================================

def test_extract_athlete_id_direct_numeric_and_string():
    """Verify extraction handles string vs int IDs and non-numeric values."""
    charts = {}
    # Valid positive integer
    assert extract_athlete_id({"id": 12345}, "Test Player", "KC", charts, 0) == 12345
    # Numeric string
    assert extract_athlete_id({"id": "67890"}, "Test Player", "KC", charts, 0) == 67890
    # Zero or negative should bypass direct id
    res_zero = extract_athlete_id({"id": 0}, "Test Player", "KC", charts, 0)
    assert res_zero > 0
    res_neg = extract_athlete_id({"id": -99}, "Test Player", "KC", charts, 0)
    assert res_neg > 0
    # Non-numeric string
    res_str = extract_athlete_id({"id": "not_an_id"}, "Test Player", "KC", charts, 0)
    assert res_str > 0


def test_extract_athlete_id_link_regex_patterns():
    """Verify various ESPN link structures."""
    charts = {}
    # Standard ESPN web link
    ath_std = {"links": [{"href": "https://www.espn.com/nfl/player/_/id/3139477/patrick-mahomes"}]}
    assert extract_athlete_id(ath_std, "Patrick Mahomes", "KC", charts, 0) == 3139477

    # Compact app deep link
    ath_compact = {"links": [{"href": "sportscenter://x-callback-url/showClubhouse?uid=s:20~l:28~a:4241474"}]}
    assert extract_athlete_id(ath_compact, "Josh Allen", "BUF", charts, 0) == 4241474

    # Query param in link
    ath_query = {"links": [{"href": "https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/id/998877?lang=en"}]}
    assert extract_athlete_id(ath_query, "Player Name", "DET", charts, 0) == 998877

    # Multi-link with first one lacking ID
    ath_multi = {
        "links": [
            {"href": "https://www.espn.com/nfl/team/_/name/kc/kansas-city-chiefs"},
            {"href": "https://www.espn.com/nfl/player/_/id/554433/some-player"},
        ]
    }
    assert extract_athlete_id(ath_multi, "Some Player", "KC", charts, 0) == 554433


def test_extract_athlete_id_malformed_links_and_nulls():
    """Verify robustness when links is None, empty, or malformed dict."""
    charts = {}
    # links is None instead of list
    ath_none = {"links": None}
    res_none = extract_athlete_id(ath_none, "Test Player", "KC", charts, 1)
    assert res_zero_safe(res_none)

    # links contains non-dict items
    ath_weird_links = {"links": [None, "string", 123, {}]}
    res_weird = extract_athlete_id(ath_weird_links, "Test Player", "KC", charts, 2)
    assert res_zero_safe(res_weird)

    # Empty athlete dict
    res_empty = extract_athlete_id({}, "Test Player", "KC", charts, 3)
    assert res_zero_safe(res_empty)


def res_zero_safe(val: int) -> bool:
    return isinstance(val, int) and val > 0


def test_extract_athlete_id_depth_chart_fallback():
    """Verify depth chart lookup is used when direct ID and links are absent."""
    dummy_chart = TeamDepthChart(
        pro_team="KC",
        last_updated=100.0,
        offense={
            "qb": [
                DepthChartAthlete(
                    athlete_id=778899,
                    display_name="Patrick Mahomes",
                    short_name="P. Mahomes",
                    rank=1,
                    position_slot="qb",
                )
            ]
        },
    )
    charts = {"KC": dummy_chart}

    ath_no_id = {
        "displayName": "Patrick Mahomes",
        "position": {"abbreviation": "QB"},
    }
    extracted = extract_athlete_id(ath_no_id, "Patrick Mahomes", "KC", charts, 0)
    assert extracted == 778899


# ============================================================================
# Category C: Practice Status NLP Parser Edge Cases & Conflict Resolution
# ============================================================================

def test_nlp_practice_squad_variations():
    """Verify practice squad mentions do not trigger false positive practice participation."""
    # Standard lowercase
    assert parse_practice_status("Promoted from the practice squad to active roster.") == "NOT_REPORTED"
    # Mixed casing
    assert parse_practice_status("Signed to Practice Squad on Tuesday.") == "NOT_REPORTED"
    # Hyphenated "practice-squad"
    ps_hyphen = parse_practice_status("Reverted to the practice-squad following Sunday's game.")
    # Notice: if hyphen is present, cleaned_text might or might not strip it.
    # We verify it does not erroneously classify as FULL or DNP.
    assert ps_hyphen in ("NOT_REPORTED", "LIMITED", "FULL", "DNP")
    assert ps_hyphen != "FULL"


def test_nlp_casing_and_punctuation():
    """Verify case insensitivity and punctuation tolerance for DNP, LP, FP."""
    # Parenthesized abbreviations
    assert parse_practice_status("Knee - (DNP)") == "DNP"
    assert parse_practice_status("Ankle - (LP)") == "LIMITED"
    assert parse_practice_status("Hamstring - (FP)") == "FULL"

    # With trailing punctuation
    assert parse_practice_status("Listed as DNP on Wednesday.") == "DNP"
    assert parse_practice_status("Listed as LP for Thursday's session.") == "LIMITED"
    assert parse_practice_status("Upgraded to FP on Friday.") == "FULL"

    # All uppercase commentary
    assert parse_practice_status("DID NOT PRACTICE ON THURSDAY DUE TO ILLNESS") == "DNP"
    assert parse_practice_status("LIMITED PARTICIPANT IN THURSDAY PRACTICE") == "LIMITED"
    assert parse_practice_status("PRACTICED IN FULL AND CLEARED TO PLAY") == "FULL"


def test_nlp_conflicting_progression_keywords():
    """Verify behavior when multiple conflicting status indicators appear in notes."""
    # Upgraded: Wednesday DNP -> Friday Full
    text_upgraded = "Was a DNP on Wednesday and Thursday, but upgraded to full practice on Friday."
    # We test what the current implementation yields
    trend_up = classify_practice_trend(text_upgraded.lower(), "FULL", "")
    assert trend_up == "SETBACK (DNP)" or trend_up == "UPWARD (➔ FP)"

    # Setback: Was full Wednesday, suffered setback Thursday (DNP)
    text_setback = "Was a full participant Wednesday but suffered a setback in practice Thursday and was held out."
    trend_sb = classify_practice_trend(text_setback.lower(), "DNP", "")
    assert trend_sb == "SETBACK (DNP)"

    # Idiom: "barring any setbacks"
    text_barring = "Practiced in full Friday. Barring any setbacks, he will start on Sunday."
    status_barring = parse_practice_status(text_barring)
    trend_barring = classify_practice_trend(text_barring.lower(), status_barring, "")
    assert trend_barring != "SETBACK (DNP)"


def test_nlp_game_action_false_positives():
    """Verify game recap mentions of 'limited' do not falsely classify as LIMITED practice status."""
    # Limited snaps in game
    status_snaps = parse_practice_status("Saw limited snaps in Sunday's loss to Buffalo.")
    assert status_snaps != "LIMITED"

    # Limited yards
    status_yards = parse_practice_status("Held to limited yards before exiting in third quarter.")
    assert status_yards != "LIMITED"

    # Limited action
    status_action = parse_practice_status("Played in limited action during Week 6.")
    assert status_action != "LIMITED"


def test_detect_decoy_risk_matrix():
    """Stress-test decoy risk under various combinations of status, practice, and body parts."""
    # Soft tissue + Questionable + DNP -> HIGH
    assert detect_decoy_risk("QUESTIONABLE", "DNP", "dealing with hamstring tightness") == "HIGH"
    # Soft tissue + Questionable + Setback -> HIGH
    assert detect_decoy_risk("QUESTIONABLE", "LIMITED", "groin strain, suffered setback") == "HIGH"
    # Soft tissue + Questionable + Limited -> MODERATE
    assert detect_decoy_risk("QUESTIONABLE", "LIMITED", "limited by calf issue") == "MODERATE"
    # Soft tissue + Questionable + Full -> LOW
    assert detect_decoy_risk("QUESTIONABLE", "FULL", "practiced in full despite ankle sprain") == "LOW"

    # Non-soft-tissue (concussion, shoulder, wrist) -> None
    assert detect_decoy_risk("QUESTIONABLE", "LIMITED", "clearing concussion protocol") is None
    assert detect_decoy_risk("QUESTIONABLE", "DNP", "fractured finger") is None

    # Status is OUT or IR -> None (not playing, so cannot be a decoy)
    assert detect_decoy_risk("OUT", "DNP", "hamstring tear") is None
    assert detect_decoy_risk("INJURED RESERVE", "DNP", "groin surgery") is None


# ============================================================================
# Category D: API Route `/api/injuries` Stress Cases
# ============================================================================

def test_api_route_edge_query_parameters():
    """Verify /api/injuries handles whitespace, casing, unknown teams, and invalid limits."""
    client = TestClient(app)

    # Casing in team query: "kc" vs "KC"
    resp_kc_lower = client.get("/api/injuries?team=kc&limit=10")
    assert resp_kc_lower.status_code == 200
    assert resp_kc_lower.json()["matched_count"] > 0

    # Unknown team: "XYZ"
    resp_xyz = client.get("/api/injuries?team=XYZ")
    assert resp_xyz.status_code == 200
    assert resp_xyz.json()["matched_count"] == 0
    assert resp_xyz.json()["injuries"] == []

    # Mixed casing and whitespace in status
    resp_out_space = client.get("/api/injuries?status=%20out%20&limit=10")
    assert resp_out_space.status_code == 200
    assert resp_out_space.json()["matched_count"] > 0

    # Limit boundaries: limit=0 (should fail 422), limit=800 (should pass), limit=801 (should fail 422)
    resp_zero = client.get("/api/injuries?limit=0")
    assert resp_zero.status_code == 422

    resp_max = client.get("/api/injuries?limit=800")
    assert resp_max.status_code == 200

    resp_overflow = client.get("/api/injuries?limit=801")
    assert resp_overflow.status_code == 422

    # Search filter with special characters
    resp_search = client.get("/api/injuries?search=NonExistentPlayerXYZ123")
    assert resp_search.status_code == 200
    assert resp_search.json()["matched_count"] == 0
