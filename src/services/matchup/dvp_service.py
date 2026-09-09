"""Service for managing Defense vs Position (DvP) database records, synchronization, and query lookups."""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.nfl.draftedge_client import draftedge_client
from src.adapters.nfl.dvp_client import dvp_client
from src.db.models import DefenseVsPositionModel
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


TEAM_ALIASES: dict[str, str] = {
    "WSH": "WAS",
    "JAC": "JAX",
    "LA": "LAR",
}


class DvPService:
    """Synchronizes, stores, and serves Defense vs Position intelligence."""

    def __init__(self, db: Session | None = None):
        self._external_db = db

    def _get_db(self) -> Session:
        return self._external_db if self._external_db is not None else SessionLocal()

    async def sync_dvp_data(self, season: int = 2026, week: int = 1) -> dict[str, Any]:
        """Scrapes or loads latest DvP data from DraftEdge and upserts to database."""
        db = self._get_db()
        should_close = self._external_db is None

        try:
            logger.info("Starting DraftEdge DvP sync for Season %d, Week %d...", season, week)
            all_positions = await draftedge_client.fetch_all_positions()
            total_records = 0

            for pos, records in all_positions.items():
                for r in records:
                    record_id = f"{season}_{week}_{r['pro_team']}_{pos}"
                    existing = db.execute(
                        select(DefenseVsPositionModel).where(DefenseVsPositionModel.id == record_id)
                    ).scalar_one_or_none()

                    supp_json = json.dumps(r.get("supporting_stats", {}))

                    if not existing:
                        model_entry = DefenseVsPositionModel(
                            id=record_id,
                            season=season,
                            week=week,
                            pro_team=r["pro_team"],
                            team_name=r["team_name"],
                            position=pos,
                            rank_softness=r["rank_softness"],
                            rank_defense=r["rank_defense"],
                            tier=r["tier"],
                            tier_label=r["tier_label"],
                            dk_fpa=r["dk_fpa"],
                            fd_fpa=r.get("fd_fpa"),
                            vs_avg=r["vs_avg"],
                            prior_season_fpa=r["prior_season_fpa"],
                            current_season_fpa=r.get("current_season_fpa"),
                            last4_fpa=r.get("last4_fpa"),
                            trend=r.get("trend", "Stable"),
                            supporting_stats_json=supp_json,
                            is_baseline=r.get("is_baseline", True),
                            sample_games_current=r.get("sample_games_current", 0),
                            source=r.get("source", "DraftEdge"),
                            source_url=r.get("source_url", ""),
                            updated_at=utc_now(),
                        )
                        db.add(model_entry)
                    else:
                        existing.team_name = r["team_name"]
                        existing.rank_softness = r["rank_softness"]
                        existing.rank_defense = r["rank_defense"]
                        existing.tier = r["tier"]
                        existing.tier_label = r["tier_label"]
                        existing.dk_fpa = r["dk_fpa"]
                        existing.fd_fpa = r.get("fd_fpa")
                        existing.vs_avg = r["vs_avg"]
                        existing.prior_season_fpa = r["prior_season_fpa"]
                        existing.current_season_fpa = r.get("current_season_fpa")
                        existing.last4_fpa = r.get("last4_fpa")
                        existing.trend = r.get("trend", "Stable")
                        existing.supporting_stats_json = supp_json
                        existing.is_baseline = r.get("is_baseline", True)
                        existing.sample_games_current = r.get("sample_games_current", 0)
                        existing.source = r.get("source", "DraftEdge")
                        existing.source_url = r.get("source_url", "")
                        existing.updated_at = utc_now()

                    # Hydrate in-memory dvp_client profile
                    rank_kwargs = {}
                    if pos == "QB":
                        rank_kwargs["qb_rank"] = r["rank_defense"]
                    elif pos == "RB":
                        rank_kwargs["rb_rank"] = r["rank_defense"]
                    elif pos == "WR":
                        rank_kwargs["wr_rank"] = r["rank_defense"]
                    elif pos == "TE":
                        rank_kwargs["te_rank"] = r["rank_defense"]

                    if rank_kwargs:
                        dvp_client.update_team_profile(r["pro_team"], **rank_kwargs)

                    total_records += 1

            db.commit()
            logger.info("Successfully synchronized %d DvP records.", total_records)
            return {
                "status": "SUCCESS",
                "total_records": total_records,
                "season": season,
                "week": week,
                "synced_at": utc_now().isoformat(),
            }
        except Exception as e:
            db.rollback()
            logger.error("DvP sync failed: %s", e)
            raise e
        finally:
            if should_close:
                db.close()

    def get_dvp_ratings(
        self,
        season: int = 2026,
        week: int = 1,
        position: str | None = None,
        pro_team: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves DvP records, auto-seeding if table is empty."""
        db = self._get_db()
        should_close = self._external_db is None

        try:
            # Check count
            count = db.execute(
                select(DefenseVsPositionModel).where(
                    DefenseVsPositionModel.season == season,
                    DefenseVsPositionModel.week == week,
                )
            ).scalars().all()

            if not count:
                # Seed from bundled snapshot
                logger.info("DvP table empty for Season %d Week %d; seeding from bundled file...", season, week)
                self._seed_database(db, season, week)
                db.commit()

            stmt = select(DefenseVsPositionModel).where(
                DefenseVsPositionModel.season == season,
                DefenseVsPositionModel.week == week,
            )

            if position and position.upper() != "ALL":
                stmt = stmt.where(DefenseVsPositionModel.position == position.upper().strip())

            if pro_team and pro_team.upper() != "ALL":
                stmt = stmt.where(DefenseVsPositionModel.pro_team == pro_team.upper().strip())

            # Sort by rank_softness (1 = softest / most points allowed)
            stmt = stmt.order_by(DefenseVsPositionModel.rank_softness.asc())
            rows = db.execute(stmt).scalars().all()

            out: list[dict[str, Any]] = []
            for m in rows:
                out.append({
                    "id": m.id,
                    "season": m.season,
                    "week": m.week,
                    "pro_team": m.pro_team,
                    "team_name": m.team_name,
                    "position": m.position,
                    "rank_softness": m.rank_softness,
                    "rank_defense": m.rank_defense,
                    "tier": m.tier,
                    "tier_label": m.tier_label,
                    "dk_fpa": m.dk_fpa,
                    "fd_fpa": m.fd_fpa,
                    "vs_avg": m.vs_avg,
                    "prior_season_fpa": m.prior_season_fpa,
                    "current_season_fpa": m.current_season_fpa,
                    "last4_fpa": m.last4_fpa,
                    "trend": m.trend,
                    "supporting_stats": m.supporting_stats,
                    "is_baseline": m.is_baseline,
                    "sample_games_current": m.sample_games_current,
                    "source": m.source,
                    "source_url": m.source_url,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                })
            return out
        finally:
            if should_close:
                db.close()

    def get_matchup_for_player(
        self,
        opponent_team: str,
        position: str,
        season: int = 2026,
        week: int = 1,
    ) -> dict[str, Any] | None:
        """Retrieves exact DvP matchup details for an opponent defense and offensive position."""
        opp = opponent_team.upper().strip()
        opp = TEAM_ALIASES.get(opp, opp)
        pos = position.upper().strip()
        if pos in ("FB",):
            pos = "RB"
        if pos not in ("QB", "RB", "WR", "TE"):
            return None

        db = self._get_db()
        should_close = self._external_db is None

        try:
            record_id = f"{season}_{week}_{opp}_{pos}"
            item = db.execute(
                select(DefenseVsPositionModel).where(DefenseVsPositionModel.id == record_id)
            ).scalar_one_or_none()

            if not item:
                # Fallback to team + pos regardless of week
                item = db.execute(
                    select(DefenseVsPositionModel).where(
                        DefenseVsPositionModel.pro_team == opp,
                        DefenseVsPositionModel.position == pos,
                    ).order_by(DefenseVsPositionModel.updated_at.desc())
                ).scalars().first()

            if not item:
                # Trigger auto-seed
                self._seed_database(db, season, week)
                db.commit()
                item = db.execute(
                    select(DefenseVsPositionModel).where(DefenseVsPositionModel.id == record_id)
                ).scalar_one_or_none()

            if not item:
                return None

            return {
                "season": item.season,
                "week": item.week,
                "defensive_team": item.pro_team,
                "team_name": item.team_name,
                "position": item.position,
                "rank_softness": item.rank_softness,
                "rank_defense": item.rank_defense,
                "tier": item.tier,
                "tier_label": item.tier_label,
                "dk_fpa": item.dk_fpa,
                "fd_fpa": item.fd_fpa,
                "vs_avg": item.vs_avg,
                "prior_season_fpa": item.prior_season_fpa,
                "current_season_fpa": item.current_season_fpa,
                "last4_fpa": item.last4_fpa,
                "trend": item.trend,
                "supporting_stats": item.supporting_stats,
                "is_baseline": item.is_baseline,
                "sample_games_current": item.sample_games_current,
                "source": item.source,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
        finally:
            if should_close:
                db.close()

    def get_dvp_status(self, season: int = 2026, week: int = 1) -> dict[str, Any]:
        """Provides status and data freshness diagnostics."""
        db = self._get_db()
        should_close = self._external_db is None

        try:
            records = db.execute(
                select(DefenseVsPositionModel).where(
                    DefenseVsPositionModel.season == season,
                    DefenseVsPositionModel.week == week,
                )
            ).scalars().all()

            if not records:
                return {
                    "total_records": 0,
                    "is_seeded": False,
                    "last_updated": None,
                    "is_stale": True,
                    "is_baseline": True,
                    "message": "DvP data not yet ingested or seeded.",
                }

            latest_ts = max((r.updated_at for r in records if r.updated_at), default=None)
            now = utc_now()
            if latest_ts:
                if latest_ts.tzinfo is None:
                    latest_ts = latest_ts.replace(tzinfo=timezone.utc)
                hours_old = (now - latest_ts).total_seconds() / 3600
            else:
                hours_old = 999.0
            all_baseline = all(r.is_baseline for r in records)
            max_sample = max((r.sample_games_current for r in records), default=0)

            return {
                "total_records": len(records),
                "is_seeded": True,
                "last_updated": latest_ts.isoformat() if latest_ts else None,
                "hours_since_sync": round(hours_old, 1),
                "is_stale": hours_old > 36.0,
                "is_baseline": all_baseline,
                "sample_games_current": max_sample,
                "baseline_context": (
                    "Week 1 baseline active: Ratings derived from 2025-26 regular season with heavy weighting on the final 8 games. "
                    "As 2026-27 games are completed, current-season data progressively supersedes prior-season weights."
                    if all_baseline
                    else "Current-season games active in DvP rating blend."
                ),
            }
        finally:
            if should_close:
                db.close()

    def _seed_database(self, db: Session, season: int, week: int) -> None:
        """Seeds records from bundled JSON file if DB has not been populated."""
        positions = ["QB", "RB", "WR", "TE"]
        for pos in positions:
            seed_records = draftedge_client._load_seed_for_position(pos)
            for r in seed_records:
                record_id = f"{season}_{week}_{r['pro_team']}_{pos}"
                existing = db.execute(
                    select(DefenseVsPositionModel).where(DefenseVsPositionModel.id == record_id)
                ).scalar_one_or_none()
                if not existing:
                    supp_json = json.dumps(r.get("supporting_stats", {}))
                    entry = DefenseVsPositionModel(
                        id=record_id,
                        season=season,
                        week=week,
                        pro_team=r["pro_team"],
                        team_name=r["team_name"],
                        position=pos,
                        rank_softness=r["rank_softness"],
                        rank_defense=r["rank_defense"],
                        tier=r["tier"],
                        tier_label=r["tier_label"],
                        dk_fpa=r["dk_fpa"],
                        fd_fpa=r.get("fd_fpa"),
                        vs_avg=r["vs_avg"],
                        prior_season_fpa=r["prior_season_fpa"],
                        current_season_fpa=r.get("current_season_fpa"),
                        last4_fpa=r.get("last4_fpa"),
                        trend=r.get("trend", "Stable"),
                        supporting_stats_json=supp_json,
                        is_baseline=r.get("is_baseline", True),
                        sample_games_current=r.get("sample_games_current", 0),
                        source=r.get("source", "DraftEdge (Seed)"),
                        source_url=r.get("source_url", ""),
                        updated_at=utc_now(),
                    )
                    db.add(entry)

                # Also update in-memory dvp_client
                rank_kwargs = {}
                if pos == "QB":
                    rank_kwargs["qb_rank"] = r["rank_defense"]
                elif pos == "RB":
                    rank_kwargs["rb_rank"] = r["rank_defense"]
                elif pos == "WR":
                    rank_kwargs["wr_rank"] = r["rank_defense"]
                elif pos == "TE":
                    rank_kwargs["te_rank"] = r["rank_defense"]
                if rank_kwargs:
                    dvp_client.update_team_profile(r["pro_team"], **rank_kwargs)


dvp_service = DvPService()
