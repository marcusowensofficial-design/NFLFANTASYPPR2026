"""FastAPI routes for FantasyPros Expert Consensus Rankings, Projections, and Sync."""

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.fantasypros import fantasypros_client
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel
from src.db.session import get_db
from src.services.fantasypros_sync import fantasypros_sync_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fantasypros", tags=["FantasyPros"])


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
        return {"season": season, "week": eff_week, "scoring": scoring_upper, "rankings": rankings}
    else:
        rankings = await fantasypros_client.fetch_consensus_rankings(
            season=season, week=eff_week, position=pos_upper, scoring=scoring_upper
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
            )
        )

    return recommendations
