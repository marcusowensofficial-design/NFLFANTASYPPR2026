"""API route handlers for live official 2026 NFL injury reports and practice statuses."""

from typing import Any
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.adapters.nfl.injuries_client import PlayerInjuryReport, nfl_injuries_client

router = APIRouter(prefix="/api/injuries", tags=["Injuries"])


class InjuryResponseItem(BaseModel):
    athlete_id: int
    name: str
    position: str
    team: str
    status: str
    practice_status: str | None = None
    headline: str | None = None
    notes: str | None = None
    date: str | None = None
    is_playable: bool
    is_out: bool


class InjuryFeedResponse(BaseModel):
    total_count: int
    matched_count: int
    injuries: list[InjuryResponseItem]


@router.get("", response_model=InjuryFeedResponse)
async def get_injuries(
    team: str | None = Query(default=None, description="Filter by NFL team display name or abbreviation"),
    position: str | None = Query(default=None, description="Filter by position (QB, RB, WR, TE, K, D/ST)"),
    status: str | None = Query(default=None, description="Filter by status (QUESTIONABLE, OUT, IR, ACTIVE)"),
    search: str | None = Query(default=None, description="Search by player name"),
    limit: int = Query(default=100, ge=1, le=800, description="Max items to return"),
) -> InjuryFeedResponse:
    """Retrieve live official NFL injury reports with beat reporter notes and practice progression."""
    all_injuries = await nfl_injuries_client.fetch_injuries()
    results = list(all_injuries.values())

    # Sort priority: OUT / IR / DOUBTFUL first, then QUESTIONABLE, then ACTIVE
    def sort_key(inj: PlayerInjuryReport) -> int:
        st = inj.status.upper()
        if "OUT" in st or "IR" in st or "DOUBTFUL" in st:
            return 0
        if "QUESTIONABLE" in st:
            return 1
        return 2

    results.sort(key=sort_key)

    filtered: list[PlayerInjuryReport] = []
    for inj in results:
        if team and team.lower() not in inj.team.lower():
            continue
        if position and inj.position.upper() != position.upper():
            continue
        if status and status.upper() not in inj.status.upper():
            continue
        if search and search.lower() not in inj.name.lower():
            continue
        filtered.append(inj)

    items = [
        InjuryResponseItem(
            athlete_id=inj.athlete_id,
            name=inj.name,
            position=inj.position,
            team=inj.team,
            status=inj.status,
            practice_status=inj.practice_status,
            headline=inj.headline,
            notes=inj.notes,
            date=inj.date,
            is_playable=inj.is_playable,
            is_out=inj.is_out,
        )
        for inj in filtered[:limit]
    ]

    return InjuryFeedResponse(
        total_count=len(all_injuries),
        matched_count=len(filtered),
        injuries=items,
    )
