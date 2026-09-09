"""Service to synchronize and enrich database players with Sleeper (RotoWire) weekly projections."""

import json
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.sleeper import sleeper_client, normalize_sleeper_stats, DEFENSE_NAME_TO_TEAM
from src.adapters.fantasypros.client import normalize_player_name, normalize_team
from src.db.models import PlayerModel
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


class SleeperSyncService:
    """Synchronizes Sleeper weekly player projections into PlayerModel."""

    def __init__(self, db: Session | None = None):
        self._external_db = db

    async def sync_sleeper_projections(
        self,
        season: int = 2024,
        week: int = 1,
        season_type: str = "regular",
    ) -> dict[str, Any]:
        """Fetch weekly projections from Sleeper/RotoWire and enrich players in DB."""
        db = self._external_db or SessionLocal()
        try:
            raw_projs = await sleeper_client.fetch_projections(
                season=season, week=week, season_type=season_type
            )
            if not raw_projs:
                logger.warning("No Sleeper projections returned for season %d week %d", season, week)
                return {
                    "success": False,
                    "message": "No Sleeper projections retrieved",
                    "enriched_count": 0,
                }

            # Index Sleeper projections
            projs_by_norm_name: dict[str, dict[str, Any]] = {}
            projs_by_team_dst: dict[str, dict[str, Any]] = {}

            for item in raw_projs:
                p_meta = item.get("player") or {}
                stats = item.get("stats") or {}
                first_name = p_meta.get("first_name") or ""
                last_name = p_meta.get("last_name") or ""
                full_name = f"{first_name} {last_name}".strip()
                pos = (p_meta.get("position") or "").upper().strip()
                team = normalize_team(p_meta.get("team") or item.get("team"))

                norm_name = normalize_player_name(full_name)
                pts_ppr = float(stats.get("pts_ppr", 0.0) or 0.0)

                # Skip blank projection placeholders if pts == 0 and no stats
                if pts_ppr == 0.0 and not any(stats.get(k, 0) > 0 for k in ("pass_att", "rush_att", "rec", "sack")):
                    continue

                if pos in ("DEF", "DST"):
                    if team and team != "FA":
                        projs_by_team_dst[team] = item
                    # Also map full defense name
                    norm_def_key = full_name.lower()
                    mapped_team = DEFENSE_NAME_TO_TEAM.get(norm_def_key)
                    if mapped_team:
                        projs_by_team_dst[mapped_team] = item
                else:
                    if norm_name:
                        # Prefer player with higher projection or existing active entry
                        if norm_name not in projs_by_norm_name or pts_ppr > float(projs_by_norm_name[norm_name].get("stats", {}).get("pts_ppr", 0.0)):
                            projs_by_norm_name[norm_name] = item

            # Retrieve database players
            stmt = select(PlayerModel)
            db_players = db.execute(stmt).scalars().all()

            enriched_count = 0
            for p in db_players:
                norm_name = normalize_player_name(p.full_name)
                pos = p.position.upper().replace("D/ST", "DST")
                norm_team = normalize_team(p.pro_team)

                matched_item = None
                if pos in ("DST", "DEF"):
                    matched_item = projs_by_team_dst.get(norm_team)
                if not matched_item:
                    matched_item = projs_by_norm_name.get(norm_name)

                if matched_item:
                    raw_stats = matched_item.get("stats") or {}
                    sleeper_pts = float(raw_stats.get("pts_ppr", 0.0) or 0.0)
                    itemized = normalize_sleeper_stats(raw_stats)

                    p.projected_points_sleeper = round(sleeper_pts, 2)
                    p.sleeper_projected_stats_json = json.dumps(itemized)
                    enriched_count += 1

            db.commit()
            logger.info("Successfully enriched %d players with Sleeper / RotoWire projections", enriched_count)
            return {
                "success": True,
                "message": f"Successfully enriched {enriched_count} players with Sleeper / RotoWire weekly projections.",
                "enriched_count": enriched_count,
            }
        except Exception as e:
            db.rollback()
            logger.error("Error syncing Sleeper projections: %s", e)
            return {
                "success": False,
                "message": f"Sleeper sync failed: {e}",
                "enriched_count": 0,
            }
        finally:
            if self._external_db is None:
                db.close()


sleeper_sync_service = SleeperSyncService()
