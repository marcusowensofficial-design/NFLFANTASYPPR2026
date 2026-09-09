"""FastAPI routes for FantasyPros Expert Consensus Rankings, Projections, and Sync."""

import logging
import re
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.fantasypros import fantasypros_client
from src.adapters.fantasypros.client import normalize_team
from src.adapters.nfl.dvp_client import dvp_client
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel
from src.db.session import get_db
from src.services.fantasypros_sync import fantasypros_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fantasypros", tags=["FantasyPros"])


def _extract_opp_code(p: dict[str, Any]) -> str | None:
    opp = p.get("player_opponent_id") or p.get("opponent_id")
    if opp:
        return str(opp).strip().upper()
    opp_str = p.get("player_opponent") or p.get("opponent")
    if not opp_str:
        return None
    cleaned = re.sub(r"^(vs\.?|at|@)\s*", "", str(opp_str), flags=re.IGNORECASE).strip().upper()
    match = re.search(r"([A-Z]{2,3})", cleaned)
    return match.group(1) if match else None


def _extract_player_position(p: dict[str, Any], default_pos: str | None = None) -> str:
    pos = p.get("player_position_id") or p.get("position")
    if pos and pos.upper() not in ("FLX", "FLEX", "TOP100", "ALL", "OVERALL", "OVR"):
        return pos.upper()
    pos_rank = p.get("pos_rank")
    if pos_rank:
        m = re.match(r"^(QB|RB|WR|TE|K|DST)", str(pos_rank), re.IGNORECASE)
        if m:
            return m.group(1).upper()
    if default_pos and default_pos.upper() not in ("FLX", "FLEX", "TOP100", "ALL", "OVERALL", "OVR"):
        return default_pos.upper()
    return "RB"


def _enrich_players_with_dvp(players: list[dict[str, Any]], default_pos: str | None = None) -> list[dict[str, Any]]:
    for p in players:
        opp_code = _extract_opp_code(p)
        pos = _extract_player_position(p, default_pos=default_pos)
        if opp_code:
            opp_norm = normalize_team(opp_code)
            dvp_rank = dvp_client.get_position_rank(opp_norm, pos)
            stars = dvp_client.get_matchup_stars(dvp_rank)
            p["opp_dvp_rank"] = dvp_rank
            p["matchup_stars"] = stars
    return players


class SyncResponse(BaseModel):
    success: bool
    message: str
    enriched_count: int


class ECRPlayerResponse(BaseModel):
    player_id: int | None = None
    player_name: str
    position: str
    team: str
    rank_ecr: int
    pos_rank: str | None = None
    tier: int | None = None
    rank_ave: float | None = None
    rank_std: float | None = None
    rank_min: int | None = None
    rank_max: int | None = None
    start_sit_grade: str | None = None
    r2p_pts: float | None = None
    opponent: str | None = None
    bye_week: str | None = None
    owned_espn: float | None = None
    opp_dvp_rank: int | None = None
    matchup_stars: int | None = None


class StreamerRecommendation(BaseModel):
    player_id: int | None = None
    player_name: str
    position: str
    pro_team: str
    rank_ecr: int
    pos_rank: str
    rank_std: float | None = None
    grade: str | None = None
    r2p_pts: float | None = None
    opponent: str | None = None
    is_rostered: bool
    rostered_by_team_name: str | None = None
    opp_dvp_rank: int | None = None
    matchup_stars: int | None = None


@router.get("/rankings")
async def get_rankings(
    position: str = Query(default="ALL", description="Position: ALL, TOP100, QB, RB, WR, TE, FLX, K, DST"),
    week: int | None = Query(default=None, description="NFL Week number"),
    scoring: str = Query(default="PPR", description="Scoring format: strictly PPR"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve weekly FantasyPros Expert Consensus Rankings (ECR) for the selected week."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    eff_week = week or (league.current_week if league else 1)
    season = league.season if league else 2026
    scoring_upper = scoring.upper()

    pos_upper = position.upper().replace("D/ST", "DST")
    if pos_upper == "ALL":
        rankings = await fantasypros_client.fetch_all_consensus_rankings(
            season=season, week=eff_week, scoring=scoring_upper
        )
        if isinstance(rankings, dict):
            for pos_key, p_list in rankings.items():
                if isinstance(p_list, list):
                    _enrich_players_with_dvp(p_list, default_pos=pos_key if pos_key != "TOP100" else None)
        return {"season": season, "week": eff_week, "scoring": scoring_upper, "rankings": rankings}
    else:
        rankings = await fantasypros_client.fetch_consensus_rankings(
            season=season, week=eff_week, position=pos_upper, scoring=scoring_upper
        )
        if isinstance(rankings, list):
            _enrich_players_with_dvp(
                rankings,
                default_pos=pos_upper if pos_upper not in ("TOP100", "OVERALL", "OVR", "ALL") else None,
            )
        return {
            "season": season,
            "week": eff_week,
            "position": pos_upper,
            "scoring": scoring_upper,
            "players": rankings,
        }


@router.get("/projections")
async def get_projections(
    position: str = Query(default="ALL", description="Position: ALL, QB, RB, WR, TE, FLX, K, DST"),
    week: int | None = Query(default=None, description="NFL Week number"),
    scoring: str = Query(default="PPR", description="Scoring format: strictly PPR"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve weekly statistical projections from FantasyPros for the selected week."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    eff_week = week or (league.current_week if league else 1)
    season = league.season if league else 2026
    scoring_upper = scoring.upper()

    pos_upper = position.upper().replace("D/ST", "DST")
    if pos_upper == "ALL":
        projections = await fantasypros_client.fetch_all_projections(
            season=season, week=eff_week, scoring=scoring_upper
        )
        return {
            "season": season,
            "week": eff_week,
            "scoring": scoring_upper,
            "projections": projections,
        }
    else:
        players = await fantasypros_client.fetch_projections(
            season=season, week=eff_week, position=pos_upper, scoring=scoring_upper
        )
        return {
            "season": season,
            "week": eff_week,
            "position": pos_upper,
            "scoring": scoring_upper,
            "players": players,
        }


@router.get("/injuries")
async def get_injuries(
    team_id: str | None = Query(default=None, description="Optional NFL team abbreviation"),
) -> dict[str, Any]:
    """Retrieve live NFL injury reports and beat writer notes from FantasyPros."""
    injuries = await fantasypros_client.fetch_injuries(team_id=team_id)
    return {"count": len(injuries), "injuries": injuries}


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    league_id: int | None = None,
    week: int | None = None,
    db: Session = Depends(get_db),
) -> SyncResponse:
    """Trigger FantasyPros intelligence sync for rostered players and available talent."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    eff_league_id = league_id or (league.id if league else None)
    eff_week = week or (league.current_week if league else 1)
    season = league.season if league else 2026

    res = await fantasypros_sync_service.sync_league_intelligence(
        league_id=eff_league_id,
        season=season,
        week=eff_week,
    )
    return SyncResponse(
        success=res.get("success", False),
        message=res.get("message", "Sync complete"),
        enriched_count=res.get("enriched_count", 0),
    )


@router.get("/streamers", response_model=list[StreamerRecommendation])
async def get_streamers(
    position: str = Query(default="DST", description="Position to stream: DST or K"),
    week: int | None = Query(default=None, description="NFL Week number"),
    db: Session = Depends(get_db),
) -> list[StreamerRecommendation]:
    """Get top 8-man league streaming recommendations (D/ST or Kicker) grounded in FantasyPros ECR."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    eff_week = week or (league.current_week if league else 1)
    season = league.season if league else 2026

    pos_clean = position.upper().replace("D/ST", "DST")
    if pos_clean not in ("DST", "K"):
        raise HTTPException(status_code=400, detail="Streaming recommendations only supported for DST and K.")

    ecr_list = await fantasypros_client.fetch_consensus_rankings(
        season=season,
        week=eff_week,
        position=pos_clean,
        scoring="PPR",
    )

    # Cross-reference with database rosters
    rostered_query = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(RosterEntryModel.league_id == (league.id if league else 0))
    ).all()

    rostered_by_pid = {r.player_id: r for r, _ in rostered_query}
    rostered_teams_by_name = {p.full_name: r.team_id for r, p in rostered_query}

    recommendations: list[StreamerRecommendation] = []
    for p in ecr_list:
        p_name = p.get("player_name") or p.get("name") or ""
        p_team = p.get("player_team_id") or p.get("team_id") or "FA"
        rank_ecr = p.get("rank_ecr", 99)
        pos_rank = p.get("pos_rank", f"{pos_clean}{rank_ecr}")
        std = p.get("rank_std")
        grade = p.get("start_sit_grade")
        r2p = p.get("r2p_pts")
        opp = p.get("player_opponent")

        # Check if rostered
        is_rostered = p_name in rostered_teams_by_name
        rostered_team_id = rostered_teams_by_name.get(p_name)

        opp_code = _extract_opp_code(p)
        dvp_rank = None
        stars = None
        if opp_code:
            opp_norm = normalize_team(opp_code)
            dvp_rank = dvp_client.get_position_rank(opp_norm, pos_clean)
            stars = dvp_client.get_matchup_stars(dvp_rank)

        recommendations.append(
            StreamerRecommendation(
                player_name=p_name,
                position=pos_clean,
                pro_team=p_team,
                rank_ecr=int(rank_ecr),
                pos_rank=pos_rank,
                rank_std=float(std) if std is not None else None,
                grade=grade,
                r2p_pts=float(r2p) if r2p is not None else None,
                opponent=opp,
                is_rostered=is_rostered,
                rostered_by_team_name=f"Team {rostered_team_id}" if rostered_team_id else None,
                opp_dvp_rank=dvp_rank,
                matchup_stars=stars,
            )
        )

    return recommendations
