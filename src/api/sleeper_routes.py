"""API routes for Sleeper / RotoWire weekly projections."""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.services.sleeper_sync import sleeper_sync_service

router = APIRouter(prefix="/api/sleeper", tags=["Sleeper"])


@router.post("/sync")
async def sync_sleeper(
    season: int = Query(default=2024, description="NFL Season year"),
    week: int = Query(default=1, description="NFL Regular season week"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Manually synchronize Sleeper / RotoWire projections for all players."""
    service = sleeper_sync_service
    service._external_db = db
    try:
        res = await service.sync_sleeper_projections(season=season, week=week)
        return res
    finally:
        service._external_db = None
