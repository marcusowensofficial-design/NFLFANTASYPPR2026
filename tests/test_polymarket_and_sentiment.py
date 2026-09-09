"""Unit and integration tests for Polymarket prediction market client & sentiment service."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.nfl.injuries_client import PlayerInjuryReport
from src.adapters.nfl.schedule_client import NFLGame
from src.adapters.polymarket.client import PolymarketClient, polymarket_client
from src.main import app
from src.services.market.sentiment_service import MarketSentimentService, market_sentiment_service


@pytest.mark.asyncio
async def test_polymarket_client_nfl_events_and_fallback():
    """Verify Polymarket client returns structured events with binary markets."""
    client = PolymarketClient(timeout=3.0)
    events = await client.fetch_nfl_events()

    assert len(events) >= 2
    starter_event = next((e for e in events if "starter" in e.slug.lower() or "steelers" in e.slug.lower()), None)
    assert starter_event is not None
    assert len(starter_event.markets) >= 2

    # Check that market prices parse into probabilities
    fields_market = next((m for m in starter_event.markets if "fields" in m.question.lower()), None)
    assert fields_market is not None
    assert 0.0 <= fields_market.yes_probability <= 1.0


@pytest.mark.asyncio
async def test_polymarket_player_matching():
    """Verify fuzzy matching maps players like Justin Fields and Jayden Daniels to markets."""
    client = PolymarketClient(timeout=3.0)

    # Match Justin Fields
    fields_markets = await client.get_market_for_player("Justin Fields")
    assert len(fields_markets) > 0
    assert any("fields" in m.question.lower() for m in fields_markets)

    # Match Jayden Daniels
    daniels_markets = await client.get_market_for_player("Jayden Daniels")
    assert len(daniels_markets) > 0
    assert any("daniels" in m.question.lower() for m in daniels_markets)


@pytest.mark.asyncio
async def test_sentiment_service_starter_controversy():
    """Verify MarketSentimentService calculates starter confidence and tactical advice."""
    service = MarketSentimentService()

    sentiment = await service.get_player_sentiment(
        player_id=999,
        player_name="Justin Fields",
        position="QB",
        pro_team="PIT",
        week=1,
        season=2026,
    )

    assert sentiment.player_name == "Justin Fields"
    assert sentiment.has_starter_controversy is True
    assert 0.0 < sentiment.starter_confidence < 1.0
    assert "Market Starter Odds" in sentiment.market_headline
    assert len(sentiment.tactical_advice) > 10


@pytest.mark.asyncio
async def test_sentiment_service_injury_decoy_risk():
    """Verify injury practice trends generate high decoy risk tags."""
    service = MarketSentimentService()

    # Mock an injury report with Questionable status and DNP
    mock_injuries = {
        888: PlayerInjuryReport(
            athlete_id=888,
            name="Tee Higgins",
            position="WR",
            team="CIN",
            status="QUESTIONABLE",
            headline="Tee Higgins missed practice with hamstring strain",
            notes="Did not practice on Wednesday",
        )
    }

    sentiment = await service.get_player_sentiment(
        player_id=888,
        player_name="Tee Higgins",
        position="WR",
        pro_team="CIN",
        week=1,
        season=2026,
        injuries=mock_injuries,
    )

    assert sentiment.injury_status == "QUESTIONABLE"
    assert sentiment.practice_status == "DNP"
    assert sentiment.decoy_risk == "HIGH"
    assert "HIGH DECOY" in sentiment.market_headline
    assert "DNP" in sentiment.tactical_advice or "snap count" in sentiment.tactical_advice


@pytest.mark.asyncio
async def test_sentiment_service_thursday_kickoff_alert():
    """Verify Thursday Night Football kickoff triggers urgency and FLEX warning."""
    service = MarketSentimentService()

    mock_schedule = [
        NFLGame(
            id="401547400",
            name="Baltimore Ravens at Kansas City Chiefs",
            home_team="KC",
            away_team="BAL",
            date="2026-09-10T20:20Z",
            venue_name="GEHA Field at Arrowhead Stadium",
        ),
        NFLGame(
            id="401547401",
            name="Green Bay Packers at Philadelphia Eagles",
            home_team="PHI",
            away_team="GB",
            date="2026-09-13T13:00Z",
            venue_name="Lincoln Financial Field",
        ),
    ]

    sentiment = await service.get_player_sentiment(
        player_id=777,
        player_name="Patrick Mahomes",
        position="QB",
        pro_team="KC",
        week=1,
        season=2026,
        schedule=mock_schedule,
    )

    assert sentiment.is_thursday_kickoff is True
    assert sentiment.urgency_level == "CRITICAL_TNF"
    assert "FLEX" in sentiment.tactical_advice


@pytest.mark.asyncio
async def test_sentiment_service_rookie_breakout_tier():
    """Verify top rookies receive Day-1 Alpha pedigree ratings."""
    service = MarketSentimentService()

    sentiment = await service.get_player_sentiment(
        player_id=555,
        player_name="Marvin Harrison Jr.",
        position="WR",
        pro_team="ARI",
        week=1,
        season=2026,
    )

    assert sentiment.is_rookie is True
    assert sentiment.rookie_tier == "DAY1_ALPHA"
    assert sentiment.oroy_implied_prob is not None
    assert "Rookie Pedigree" in sentiment.market_headline


@pytest.mark.asyncio
async def test_market_sentiment_buzz_api_endpoint():
    """Test GET /api/analysis/market-sentiment/buzz endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/analysis/market-sentiment/buzz?week=1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            first = data[0]
            assert "player_id" in first
            assert "starter_confidence" in first
            assert "decoy_risk" in first
            assert "tactical_advice" in first
