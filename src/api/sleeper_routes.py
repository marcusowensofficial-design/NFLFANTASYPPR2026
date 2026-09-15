"""API routes for Sleeper / RotoWire weekly projections."""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.sleeper_sync import sleeper_sync_service

router = APIRouter(prefix="/api/sleeper", tags=["Sleeper"])


@router.post("/sync")
async def sync_sleeper(
    season: int = Query(default=2026, description="NFL Season year"),
    week: int | None = Query(default=None, description="NFL Regular season week"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually synchronize Sleeper / RotoWire projections for all players."""
    eff_week = week
    if eff_week is None:
        from src.db.models import LeagueModel
        league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
        eff_week = league.current_week if (league and league.current_week) else 2

    service = sleeper_sync_service
    service._external_db = db
    try:
        res = await service.sync_sleeper_projections(season=season, week=eff_week)
        return res
    finally:
        service._external_db = None
