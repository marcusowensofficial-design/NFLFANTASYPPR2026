"""Bulk Projection Calibration Service.

Iterates through all database players, fetches the official NFL schedule and Vegas game environments,
runs the institutional Quant Projection Engine, and persists:
- projected_points_model
- projected_points_consensus
- projected_points
- projected_stats_json (reconciled itemized statline)
into the SQLite database.
"""

import json
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.nfl.schedule_client import NFLGame, nfl_schedule_client
from src.db.models import PlayerModel
from src.db.session import SessionLocal
from src.services.recommendation.projection_engine import quant_projection_engine

logger = logging.getLogger(__name__)


class BulkProjectionCalibrationService:
    """Orchestrates league-wide calibration and persistence of quant projections."""

    def __init__(self, db: Session | None = None):
        self._external_db = db

    def _get_db(self) -> Session:
        return self._external_db if self._external_db is not None else SessionLocal()

    async def calibrate_all_players(
        self,
        season: int = 2026,
        week: int = 1,
        projection_source: str = "MODEL",
    ) -> dict[str, Any]:
        """Calibrates and persists institutional quant projections for all players in the database."""
        db = self._get_db()
        try:
            # 1. Fetch official week schedule
            games = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)
            game_by_team: dict[str, NFLGame] = {}
            for g in games:
                game_by_team[g.home_team.upper().strip()] = g
                game_by_team[g.away_team.upper().strip()] = g

            # 2. Retrieve all players
            stmt = select(PlayerModel)
            players = db.execute(stmt).scalars().all()
            if not players:
                logger.warning("No players found in database to calibrate.")
                return {"success": False, "calibrated_count": 0, "message": "No players found"}

            calibrated_count = 0
            position_counts: dict[str, int] = {}
            top_performers: list[dict[str, Any]] = []

            for p in players:
                team_clean = p.pro_team.upper().strip()
                nfl_game = game_by_team.get(team_clean)

                # Run Institutional Quant Engine
                proj_res = quant_projection_engine.calculate_player_projection(
                    player=p,
                    nfl_game=nfl_game,
                    projection_source=projection_source,
                )

                # Persist mathematical calibrations
                p.projected_points_model = proj_res.model_points
                p.projected_points_consensus = proj_res.consensus_points
                p.projected_points = proj_res.projected_points
                p.projected_stats_json = json.dumps(proj_res.itemized_stats.model_dump())

                calibrated_count += 1
                pos_key = p.position.upper().strip()
                position_counts[pos_key] = position_counts.get(pos_key, 0) + 1

                if proj_res.projected_points >= 15.0:
                    top_performers.append({
                        "id": p.id,
                        "name": p.full_name,
                        "pos": p.position,
                        "team": p.pro_team,
                        "proj_model": proj_res.model_points,
                        "proj_consensus": proj_res.consensus_points,
                        "active": proj_res.projected_points,
                        "opponent": nfl_game.get_opponent_for_team(team_clean) if nfl_game else "BYE",
                    })

            db.commit()
            top_performers.sort(key=lambda x: x["active"], reverse=True)

            logger.info(
                f"Successfully calibrated {calibrated_count} players across {len(position_counts)} positions."
            )
            return {
                "success": True,
                "calibrated_count": calibrated_count,
                "position_counts": position_counts,
                "top_performers": top_performers[:15],
            }

        except Exception as e:
            db.rollback()
            logger.exception("Failed bulk player projection calibration")
            return {"success": False, "error": str(e), "calibrated_count": 0}
        finally:
            if self._external_db is None:
                db.close()


bulk_projection_service = BulkProjectionCalibrationService()
