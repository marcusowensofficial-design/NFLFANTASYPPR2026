"""Tests for FantasyPros API Client, Sync Service, Scoring Engine, and Routes."""

import pytest
from unittest.mock import AsyncMock, patch
from src.adapters.fantasypros.client import FantasyProsClient, normalize_player_name, normalize_team
from src.db.models import PlayerModel, LeagueModel
from src.services.fantasypros_sync import FantasyProsSyncService
from src.services.recommendation.scoring_engine import scoring_engine


def test_fantasypros_client_normalization():
    assert normalize_player_name("Marvin Harrison Jr.") == "marvin harrison"
    assert normalize_player_name("Kenneth Walker III") == "kenneth walker"
    assert normalize_player_name("De'Von Achane") == "devon achane"
    assert normalize_team("LA") == "LAR"
    assert normalize_team("JAC") == "JAX"
    assert normalize_team("WSH") == "WAS"


def test_fantasypros_client_configuration():
    client = FantasyProsClient(api_key="test_key_123")
    assert client.is_configured is True
    assert client._get_headers()["x-api-key"] == "test_key_123"

    empty_client = FantasyProsClient(api_key="")
    assert empty_client.is_configured is False


def test_fantasypros_client_caching():
    client = FantasyProsClient(api_key="dummy_key")
    client._set_cached("test_key", [{"player_name": "Test Player"}])
    assert client._get_cached("test_key") == [{"player_name": "Test Player"}]


def test_fantasypros_client_ppr_routing():
    import asyncio
    client = FantasyProsClient(api_key="dummy_key")

    with patch.object(client, "_fetch_web_rankings", new=AsyncMock(return_value=[{"player_name": "Test RB", "rank_ecr": 1}])) as mock_fetch:
        asyncio.run(client.fetch_consensus_rankings(season=2026, week=1, position="RB", scoring="PPR"))
        mock_fetch.assert_called_once_with("ppr-rb", week=1)

    with patch.object(client, "_fetch_web_rankings", new=AsyncMock(return_value=[{"player_name": "Test WR", "rank_ecr": 1}])) as mock_fetch:
        asyncio.run(client.fetch_consensus_rankings(season=2026, week=1, position="WR", scoring="PPR"))
        mock_fetch.assert_called_once_with("ppr-wr", week=1)

    with patch.object(client, "_fetch_web_rankings", new=AsyncMock(return_value=[{"player_name": "Test TE", "rank_ecr": 1}])) as mock_fetch:
        asyncio.run(client.fetch_consensus_rankings(season=2026, week=1, position="TE", scoring="PPR"))
        mock_fetch.assert_called_once_with("ppr-te", week=1)

    with patch.object(client, "_fetch_web_rankings", new=AsyncMock(return_value=[{"player_name": "Test Top", "rank_ecr": 1}])) as mock_fetch:
        asyncio.run(client.fetch_consensus_rankings(season=2026, week=1, position="TOP100", scoring="PPR"))
        # Top 100 uses ppr-cheatsheets
        assert mock_fetch.call_args_list[0][0][0] == "ppr-cheatsheets"
        assert mock_fetch.call_args_list[0][1]["week"] == 1


def test_fantasypros_sync_service(db_session):
    import asyncio
    # Insert test league and player
    league = LeagueModel(id=1841917737, season=2026, name="Test 8-Man", size=8, current_week=1)
    db_session.add(league)

    from src.db.models import TeamModel, RosterEntryModel
    team = TeamModel(id=1, league_id=league.id, name="Test Team", is_user_team=True)
    db_session.add(team)

    player = PlayerModel(
        id=22968,
        full_name="Jahmyr Gibbs",
        position="RB",
        pro_team="DET",
        projected_points=18.5,
    )
    db_session.add(player)

    roster_entry = RosterEntryModel(
        id=f"{league.id}_1_{player.id}",
        league_id=league.id,
        team_id=1,
        player_id=player.id,
        lineup_slot_id=2,
        is_starter=True,
    )
    db_session.add(roster_entry)
    db_session.commit()

    sync_service = FantasyProsSyncService(db=db_session)

    # Mock client methods
    mock_ecr = {
        "RB": [
            {
                "player_name": "Jahmyr Gibbs",
                "player_team_id": "DET",
                "rank_ecr": 1,
                "pos_rank": "RB1",
                "tier": 1,
                "rank_ave": 1.08,
                "rank_std": 0.27,
                "start_sit_grade": "A+",
                "r2p_pts": 21.6,
            }
        ]
    }
    mock_projs = {
        "RB": [
            {
                "player_name": "Jahmyr Gibbs",
                "team": "DET",
                "position": "RB",
                "projected_points": 20.92,
                "scoring": "PPR",
                "stats": {"points_ppr": 20.92, "rush_yds": 81.1},
            }
        ]
    }
    mock_injuries = [
        {"name": "Jahmyr Gibbs", "status": "ACTIVE", "comment": "Full participant in practice."}
    ]

    with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_all_consensus_rankings", new=AsyncMock(return_value=mock_ecr)):
        with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_all_projections", new=AsyncMock(return_value=mock_projs)):
            with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_injuries", new=AsyncMock(return_value=mock_injuries)):
                res = asyncio.run(sync_service.sync_league_intelligence(league_id=league.id, season=2026, week=1))

    assert res["success"] is True
    assert res["enriched_count"] == 1

    db_session.refresh(player)
    assert player.fp_rank_ecr == 1
    assert player.fp_pos_rank == "RB1"
    assert player.fp_start_sit_grade == "A+"
    assert player.fp_rank_std == 0.27
    assert player.fp_injury_note == "Full participant in practice."


def test_scoring_engine_fantasypros_integration():
    player = PlayerModel(
        id=99999,
        full_name="Alpha Receiver",
        position="WR",
        pro_team="CIN",
        projected_points=19.0,
        fp_rank_ecr=2,
        fp_pos_rank="WR2",
        fp_tier=1,
        fp_rank_ave=2.1,
        fp_rank_std=1.6,
        fp_start_sit_grade="A+",
        fp_r2p_pts=20.5,
    )

    # Balanced mode
    ev_balanced = scoring_engine.evaluate_player(player, mode="BALANCED", league_size=8)
    assert ev_balanced.fp_rank_ecr == 2
    assert ev_balanced.fp_start_sit_grade == "A+"
    assert any("FantasyPros ECR #2" in r for r in ev_balanced.reasons_positive)

    # Ceiling mode - rewards high expert std dev
    ev_ceiling = scoring_engine.evaluate_player(player, mode="CEILING", league_size=8)
    assert any("boom ceiling" in r or "Expert divergence" in r for r in ev_ceiling.reasons_positive)
    assert ev_ceiling.ceiling_score > 0.0


def test_api_fantasypros_routes(client, db_session):
    league = LeagueModel(id=1841917737, season=2026, name="Test 8-Man", size=8, current_week=1)
    db_session.add(league)
    db_session.commit()

    mock_streamers = [
        {
            "player_name": "Chargers D/ST",
            "player_team_id": "LAC",
            "rank_ecr": 2,
            "pos_rank": "DST2",
            "rank_std": 1.42,
            "start_sit_grade": "A-",
            "r2p_pts": 7.4,
            "player_opponent": "vs. LV",
        }
    ]

    with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_consensus_rankings", new=AsyncMock(return_value=mock_streamers)):
        resp = client.get("/api/fantasypros/streamers?position=DST")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["player_name"] == "Chargers D/ST"
        assert data[0]["rank_ecr"] == 2
        assert data[0]["is_rostered"] is False


def test_api_fantasypros_top_100_and_projections(client):
    mock_top_100 = [
        {
            "player_name": "Ja'Marr Chase",
            "player_team_id": "CIN",
            "player_position_id": "WR",
            "rank_ecr": 1,
            "pos_rank": "WR1",
            "tier": 1,
            "start_sit_grade": "A+",
            "r2p_pts": 14.5,
            "player_opponent": "vs. TB",
        },
        {
            "player_name": "Jahmyr Gibbs",
            "player_team_id": "DET",
            "player_position_id": "RB",
            "rank_ecr": 2,
            "pos_rank": "RB1",
            "tier": 1,
            "start_sit_grade": "A+",
            "r2p_pts": 18.2,
            "player_opponent": "at KC",
        },
    ]

    mock_projections = [
        {
            "player_id": 22968,
            "player_name": "Jahmyr Gibbs",
            "position": "RB",
            "team": "DET",
            "projected_points": 20.92,
            "scoring": "PPR",
            "stats": {"points_ppr": 20.92, "rush_yds": 81.1},
        }
    ]

    with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_consensus_rankings", new=AsyncMock(return_value=mock_top_100)):
        resp = client.get("/api/fantasypros/rankings?position=TOP100&week=1&scoring=PPR")
        assert resp.status_code == 200
        data = resp.json()
        assert data["position"] == "TOP100"
        assert data["scoring"] == "PPR"
        assert data["week"] == 1
        assert len(data["players"]) == 2
        assert data["players"][0]["player_name"] == "Ja'Marr Chase"
        assert data["players"][0]["rank_ecr"] == 1
        assert data["players"][0]["start_sit_grade"] == "A+"
        assert data["players"][0]["opp_dvp_rank"] == 23
        assert data["players"][0]["matchup_stars"] == 4
        assert data["players"][1]["opp_dvp_rank"] == 10
        assert data["players"][1]["matchup_stars"] == 2

    with patch("src.adapters.fantasypros.client.fantasypros_client.fetch_projections", new=AsyncMock(return_value=mock_projections)):
        resp_proj = client.get("/api/fantasypros/projections?position=RB&week=1&scoring=PPR")
        assert resp_proj.status_code == 200
        p_data = resp_proj.json()
        assert p_data["position"] == "RB"
        assert p_data["week"] == 1
        assert p_data["scoring"] == "PPR"
        assert len(p_data["players"]) == 1
        assert p_data["players"][0]["player_name"] == "Jahmyr Gibbs"
        assert p_data["players"][0]["projected_points"] == 20.92

