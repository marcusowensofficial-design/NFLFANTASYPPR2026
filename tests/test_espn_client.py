"""Unit tests for ESPN Fantasy client, response parsing, error handling, and schemas."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from src.adapters.espn.client import (
    ESPNAPIError,
    ESPNClient,
    ESPNNotFoundError,
    ESPNRateLimitError,
    ESPNUnauthorizedError,
)
from src.adapters.espn.constants import RosterSlot
from src.adapters.espn.schemas import ESPNAthlete, ESPNLeagueResponse, ESPNRosterEntry


@pytest.fixture
def mock_league_payload() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "mock_espn_league.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_mock_league_schema_validation(mock_league_payload):
    """Test full parsing and validation of mock 2026 8-team PPR league."""
    league = ESPNLeagueResponse.model_validate(mock_league_payload)
    assert league.id == 84920174
    assert league.season_id == 2026
    assert league.scoring_period_id == 1
    assert len(league.teams) == 8

    # Settings verification
    assert league.settings is not None
    assert league.settings.name == "The Apex 2026 Invitational"
    assert league.settings.size == 8

    # Roster slot mapping
    slot_counts = league.settings.roster_settings.parsed_slot_counts
    assert slot_counts["QB"] == 1
    assert slot_counts["RB"] == 2
    assert slot_counts["WR"] == 2
    assert slot_counts["TE"] == 1
    assert slot_counts["FLEX"] == 1
    assert slot_counts["D/ST"] == 1
    assert slot_counts["K"] == 1
    assert slot_counts["BE"] == 7
    assert slot_counts["IR"] == 2

    # Scoring settings (PPR check)
    assert league.settings.scoring_settings.is_ppr is True
    assert league.settings.scoring_settings.reception_points == 1.0

    # Team 1 verification
    team1 = league.teams[0]
    assert team1.full_name == "Gridiron Gurus"
    assert team1.abbrev == "GURU"
    assert team1.primary_owner == "Marco"
    assert team1.roster is not None
    assert len(team1.roster.entries) == 11

    # Check starter count
    starters = [e for e in team1.roster.entries if e.is_starter]
    bench = [e for e in team1.roster.entries if e.lineup_slot_id == RosterSlot.BENCH]
    assert len(starters) == 9  # 1 QB + 2 RB + 2 WR + 1 TE + 1 FLEX + 1 DST + 1 K
    assert len(bench) == 2


def test_client_swid_normalization():
    """Test SWID normalization with and without braces."""
    guid_without_braces = "12345678-ABCD-EF01-2345-6789ABCDEF01"
    guid_with_braces = "{12345678-ABCD-EF01-2345-6789ABCDEF01}"

    client1 = ESPNClient(league_id=123, swid=guid_without_braces)
    assert client1.swid == guid_with_braces

    client2 = ESPNClient(league_id=123, swid=guid_with_braces)
    assert client2.swid == guid_with_braces


def test_client_cookies_and_credentials():
    """Test cookie dictionary construction."""
    client = ESPNClient(
        league_id=123,
        swid="{TEST-SWID}",
        espn_s2="TEST-ESPN-S2-TOKEN",
    )
    assert client.has_credentials is True
    cookies = client._get_cookies()
    assert cookies["SWID"] == "{TEST-SWID}"
    assert cookies["espn_s2"] == "TEST-ESPN-S2-TOKEN"


@pytest.mark.asyncio
async def test_client_401_unauthorized_error():
    """Test that HTTP 401 raises ESPNUnauthorizedError with actionable message."""
    client = ESPNClient(league_id=99999999)

    mock_response = httpx.Response(
        status_code=401,
        content=b'{"messages": ["You are not authorized to view this league."]}',
        request=httpx.Request("GET", client.league_url),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(ESPNUnauthorizedError) as exc_info:
            await client.fetch_league_raw()

        assert "PRIVATE" in str(exc_info.value)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_client_404_not_found_error():
    """Test that HTTP 404 raises ESPNNotFoundError."""
    client = ESPNClient(league_id=99999999)

    mock_response = httpx.Response(
        status_code=404,
        content=b'{"messages": ["Not Found"]}',
        request=httpx.Request("GET", client.league_url),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(ESPNNotFoundError) as exc_info:
            await client.fetch_league_raw()

        assert "was not found" in str(exc_info.value)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_client_429_rate_limit_error():
    """Test that HTTP 429 raises ESPNRateLimitError."""
    client = ESPNClient(league_id=123)

    mock_response = httpx.Response(
        status_code=429,
        content=b"Too Many Requests",
        request=httpx.Request("GET", client.league_url),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        with pytest.raises(ESPNRateLimitError) as exc_info:
            await client.fetch_league_raw()

        assert "Rate Limited" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_test_connection_success(mock_league_payload):
    """Test test_connection returns success and formatted summary."""
    client = ESPNClient(league_id=84920174)

    with patch.object(client, "fetch_league_raw", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_league_payload
        success, message, summary = await client.test_connection()

        assert success is True
        assert "Successfully connected" in message
        assert summary is not None
        assert summary.league_id == 84920174
        assert summary.name == "The Apex 2026 Invitational"
        assert summary.size == 8
        assert summary.is_ppr is True
        assert len(summary.teams) == 8


def test_athlete_projection_extraction(mock_league_payload):
    """Test projection parsing for a specific week."""
    athlete_data = mock_league_payload["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"]
    athlete = ESPNAthlete.model_validate(athlete_data)

    assert athlete.full_name == "Jayden Daniels"
    assert athlete.position == "QB"
    assert athlete.pro_team == "WSH"
    assert athlete.get_projection_for_week(1) == 21.4
    assert athlete.get_projection_for_week(2) == 0.0


@pytest.mark.asyncio
async def test_client_execute_roster_transaction():
    """Test execute_roster_transaction dry-run, missing creds, and successful POST."""
    # 1. Missing credentials
    unauthed_client = ESPNClient(league_id=1841917737)
    success, msg, _ = await unauthed_client.execute_roster_transaction(team_id=6, moves=[])
    assert success is False
    assert "missing SWID or espn_s2" in msg

    # 2. Dry run preview
    authed_client = ESPNClient(
        league_id=1841917737,
        swid="{TEST-SWID}",
        espn_s2="TEST-TOKEN",
    )
    moves = [
        {"player_id": 4361579, "player_name": "Bijan Robinson", "from_slot_id": 20, "to_slot_id": 2},
    ]
    success, msg, payload = await authed_client.execute_roster_transaction(team_id=6, moves=moves, dry_run=True)
    assert success is True
    assert "Dry-run preview" in msg
    assert payload["type"] == "ROSTER"
    assert payload["items"][0]["playerId"] == 4361579
    assert payload["items"][0]["toLineupSlotId"] == 2

    # 3. Successful POST
    mock_post_resp = httpx.Response(
        status_code=200,
        content=b'{"status": "success"}',
        request=httpx.Request("POST", f"{authed_client.league_url}/transactions/roster"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_post_resp
        success, msg, _ = await authed_client.execute_roster_transaction(team_id=6, moves=moves, dry_run=False)
        assert success is True
        assert "Successfully updated ESPN lineup" in msg
