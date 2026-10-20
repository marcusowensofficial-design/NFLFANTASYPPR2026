"""API route handlers for live official 2026 NFL injury reports and practice statuses."""

from typing import Any
from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.adapters.nfl.injuries_client import PlayerInjuryReport, nfl_injuries_client, resolve_team_abbrev

router = APIRouter(prefix="/api/injuries", tags=["Injuries"])


class InjuryResponseItem(BaseModel):
    athlete_id: int
    name: str
    position: str
    team: str
    team_abbr: str | None = None
    status: str
    practice_status: str | None = None
    practice_trend: str | None = None
    decoy_risk: str | None = None
    headline: str | None = None
    notes: str | None = None
    date: str | None = None
    is_playable: bool
    is_out: bool
    backup_player_name: str | None = None
    backup_player_id: int | None = None
    backup_slot: str | None = None
    vacated_opportunity_note: str | None = None


class InjuryFeedResponse(BaseModel):
    total_count: int
    matched_count: int
    injuries: list[InjuryResponseItem]


@router.get("", response_model=InjuryFeedResponse)
async def get_injuries(
    team: str | None = Query(default=None, description="Filter by NFL team display name or abbreviation"),
    position: str | None = Query(default=None, description="Filter by position (QB, RB, WR, TE, K, D/ST)"),
    status: str | None = Query(default=None, description="Filter by status (QUESTIONABLE, OUT, IR, ACTIVE)"),
    practice_status: str | None = Query(default=None, description="Filter by practice status (DNP, LIMITED, FULL, NOT_REPORTED)"),
    search: str | None = Query(default=None, description="Search by player name"),
    limit: int = Query(default=100, ge=1, le=800, description="Max items to return"),
    force: bool = Query(default=False, description="Bypass cache and fetch live updates"),
) -> InjuryFeedResponse:
    """Retrieve live official NFL injury reports with beat reporter notes and practice progression."""
    if force:
        nfl_injuries_client.clear_cache()
    all_injuries = await nfl_injuries_client.fetch_injuries(force=force)
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
        if team:
            t_clean = resolve_team_abbrev(team)
            t_abbr = resolve_team_abbrev(inj.team)
            if t_clean != t_abbr and team.lower() not in inj.team.lower():
                continue
        if position and position.strip().upper() not in ("ALL", "") and inj.position.upper() != position.strip().upper():
            continue
        if status:
            st_clean = status.strip().upper()
            st = inj.status.upper()
            if st_clean == "OUT":
                if not inj.is_out:
                    continue
            elif st_clean in ("IR", "INJURED RESERVE", "RESERVE"):
                if not (st in ("IR", "INJURED RESERVE") or "IR" in st or "RESERVE" in st):
                    continue
            elif st_clean == "ACTIVE":
                if inj.is_out or "QUESTIONABLE" in st:
                    continue
            elif st_clean not in ("ALL", ""):
                if st_clean not in st:
                    continue
        if practice_status and practice_status.strip().upper() not in ("ALL", ""):
            ps_clean = practice_status.strip().upper()
            curr_ps = (inj.practice_status or "NOT_REPORTED").upper()
            if curr_ps != ps_clean and (inj.practice_status or "").upper() != ps_clean:
                continue
        if search and search.lower() not in inj.name.lower():
            continue
        filtered.append(inj)

    slice_to_enrich = filtered[:limit]
    enriched = await nfl_injuries_client.enrich_beneficiaries(slice_to_enrich)

    items = [
        InjuryResponseItem(
            athlete_id=inj.athlete_id,
            name=inj.name,
            position=inj.position,
            team=inj.team,
            team_abbr=resolve_team_abbrev(inj.team),
            status=inj.status,
            practice_status=inj.practice_status,
            practice_trend=inj.practice_trend,
            decoy_risk=inj.decoy_risk,
            headline=inj.headline,
            notes=inj.notes,
            date=inj.date,
            is_playable=inj.is_playable,
            is_out=inj.is_out,
            backup_player_name=inj.backup_athlete_name,
            backup_player_id=inj.backup_athlete_id,
            backup_slot=inj.backup_slot,
            vacated_opportunity_note=inj.vacated_opportunity_note,
        )
        for inj in enriched
    ]

    return InjuryFeedResponse(
        total_count=len(all_injuries),
        matched_count=len(filtered),
        injuries=items,
    )
