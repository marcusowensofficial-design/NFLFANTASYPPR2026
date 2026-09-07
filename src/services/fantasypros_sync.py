"""Service to synchronize and enrich database players with FantasyPros intelligence.

Enriches rostered players and free agents with Expert Consensus Rankings (ECR),
Standard Deviation (expert agreement/volatility), Start/Sit letter grades,
FantasyPros projections, and real-time beat reporter injury notes.
"""

import asyncio
import json
import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.fantasypros import fantasypros_client
from src.adapters.fantasypros.client import normalize_player_name, normalize_team
from src.adapters.nfl.dvp_client import dvp_client
from src.db.models import PlayerModel, RosterEntryModel
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


class FantasyProsSyncService:
    """Enriches players with FantasyPros consensus intelligence."""

    def __init__(self, db: Session | None = None):
        self._external_db = db

    def _get_db(self) -> Session:
        return self._external_db if self._external_db is not None else SessionLocal()

    async def sync_league_intelligence(
        self,
        league_id: int | None = None,
        season: int = 2026,
        week: int = 1,
    ) -> dict[str, Any]:
        db = self._get_db()
        try:
            # 1. Concurrently fetch all PPR ECR rankings, weekly PPR projections, and live injuries
            all_ecr, all_projs, injuries = await asyncio.gather(
                fantasypros_client.fetch_all_consensus_rankings(
                    season=season,
                    week=week,
                    scoring="PPR",
                ),
                fantasypros_client.fetch_all_projections(
                    season=season,
                    week=week,
                    scoring="PPR",
                ),
                fantasypros_client.fetch_injuries(),
                return_exceptions=True,
            )

            if not isinstance(all_ecr, dict):
                all_ecr = {}
            if not isinstance(all_projs, dict):
                all_projs = {}
            if not isinstance(injuries, list):
                injuries = []

            # Flatten projections by normalized name
            projs_by_norm_name: dict[str, dict[str, Any]] = {}
            for pos_key, proj_list in all_projs.items():
                if isinstance(proj_list, list):
                    for pr in proj_list:
                        norm = normalize_player_name(pr.get("player_name"))
                        if norm and norm not in projs_by_norm_name:
                            projs_by_norm_name[norm] = pr

            # Flatten ECR players by normalized name with intelligent field merging
            ecr_by_norm_name: dict[str, dict[str, Any]] = {}
            ecr_by_team_dst: dict[str, dict[str, Any]] = {}

            # Process positional tables first (they have start_sit_grade and pos_rank)
            pos_priority = ["QB", "RB", "WR", "TE", "FLX", "K", "DST", "TOP100"]
            for pos in pos_priority:
                p_list = all_ecr.get(pos, [])
                for p in p_list:
                    p_name = p.get("player_name") or p.get("name") or ""
                    p_team = normalize_team(p.get("player_team_id") or p.get("team_id"))
                    norm_name = normalize_player_name(p_name)
                    if norm_name:
                        if norm_name not in ecr_by_norm_name:
                            ecr_by_norm_name[norm_name] = dict(p)
                            if pos != "TOP100" and not ecr_by_norm_name[norm_name].get("pos_rank"):
                                r = p.get("rank_ecr")
                                if r:
                                    ecr_by_norm_name[norm_name]["pos_rank"] = f"{pos}{r}"
                        else:
                            existing = ecr_by_norm_name[norm_name]
                            for k in ("start_sit_grade", "pos_rank", "r2p_pts", "tier", "player_opponent", "rank_ave", "rank_std"):
                                if not existing.get(k) and p.get(k):
                                    existing[k] = p.get(k)
                            if pos != "TOP100" and not existing.get("pos_rank"):
                                r = p.get("rank_ecr")
                                if r:
                                    existing["pos_rank"] = f"{pos}{r}"

                    if pos == "DST" and p_team:
                        ecr_by_team_dst[p_team] = p
                        dst_rank = p.get("rank_ecr")
                        if dst_rank is not None:
                            try:
                                dvp_client.update_team_profile(p_team, overall_def_rank=int(dst_rank))
                            except Exception:
                                pass

            # 2. Index live injuries
            injuries_by_name: dict[str, dict[str, Any]] = {}
            for inj in injuries:
                name = inj.get("name") or ""
                norm = normalize_player_name(name)
                if norm and norm not in injuries_by_name:
                    injuries_by_name[norm] = inj

            # 3. Retrieve all players from database (rosters + available talent)
            stmt = select(PlayerModel)
            players = db.execute(stmt).scalars().all()

            enriched_count = 0
            for p in players:
                norm_name = normalize_player_name(p.full_name)
                pos = p.position.upper().replace("D/ST", "DST")
                norm_team = normalize_team(p.pro_team)

                matched_ecr = None
                if pos == "DST":
                    matched_ecr = ecr_by_team_dst.get(norm_team)
                if not matched_ecr:
                    matched_ecr = ecr_by_norm_name.get(norm_name)

                # Update ECR intelligence if matched
                if matched_ecr:
                    rank_ecr = matched_ecr.get("rank_ecr")
                    rank_ave = matched_ecr.get("rank_ave")
                    rank_std = matched_ecr.get("rank_std")
                    tier = matched_ecr.get("tier")
                    pos_rank = matched_ecr.get("pos_rank")
                    grade = matched_ecr.get("start_sit_grade")
                    r2p = matched_ecr.get("r2p_pts")

                    p.fp_rank_ecr = int(rank_ecr) if rank_ecr is not None else None
                    p.fp_pos_rank = pos_rank
                    p.fp_tier = int(tier) if tier is not None else None
                    p.fp_rank_ave = float(rank_ave) if rank_ave is not None else None
                    p.fp_rank_std = float(rank_std) if rank_std is not None else None
                    p.fp_start_sit_grade = grade
                    p.fp_r2p_pts = float(r2p) if r2p is not None else None

                    # If ESPN consensus rank was default 999 or missing, populate with ECR
                    if p.consensus_rank is None or p.consensus_rank >= 900.0:
                        if rank_ave is not None:
                            p.consensus_rank = float(rank_ave)
                        elif rank_ecr is not None:
                            p.consensus_rank = float(rank_ecr)

                    enriched_count += 1

                # Update projection intelligence if matched
                has_real_stats = False
                matched_proj = projs_by_norm_name.get(norm_name)
                if matched_proj:
                    proj_pts = matched_proj.get("projected_points")
                    if proj_pts:
                        p.projected_points_fp = round(float(proj_pts), 2)
                        if p.fp_r2p_pts is None or p.fp_r2p_pts == 0.0:
                            p.fp_r2p_pts = float(proj_pts)
                    itemized = matched_proj.get("stats")
                    if itemized and isinstance(itemized, dict):
                        has_real_stats = any(
                            itemized.get(k, 0.0) > 0
                            for k in (
                                "rush_att", "rush_yds", "rec_rec", "receptions",
                                "pass_att", "pass_cmp", "fg", "fga", "def_sack", "def_pa"
                            )
                        )
                        if has_real_stats:
                            p.projected_stats = {**p.projected_stats, **itemized}
                            p.fp_projected_stats_json = json.dumps(itemized)
                elif p.fp_r2p_pts:
                    p.projected_points_fp = round(float(p.fp_r2p_pts), 2)

                # If player has FP projection points but no direct FP itemized breakdown,
                # scale baseline volume proportionally so all cards display complete real stats
                if not has_real_stats and p.projected_points_fp > 0:
                    base_stats = p.projected_stats or {}
                    base_pts = p.projected_points_espn or p.projected_points or base_stats.get("calculated_ppr", 0.0)
                    if base_stats and base_pts and base_pts > 0:
                        ratio = max(0.2, min(3.0, p.projected_points_fp / base_pts))
                        scaled_fp = {}
                        for sk, sv in base_stats.items():
                            if isinstance(sv, (int, float)):
                                scaled_fp[sk] = round(sv * ratio, 2)
                        scaled_fp["points_ppr"] = p.projected_points_fp
                        scaled_fp["r2p_pts"] = p.projected_points_fp
                        p.fp_projected_stats_json = json.dumps(scaled_fp)

                # Ensure ESPN baseline is captured if missing
                if not p.projected_points_espn and p.projected_points > 0:
                    p.projected_points_espn = round(p.projected_points, 2)

                # Update injury intelligence
                matched_inj = injuries_by_name.get(norm_name)
                if matched_inj:
                    comment = matched_inj.get("comment")
                    status = matched_inj.get("status")
                    if comment:
                        p.fp_injury_note = comment
                    if status in ("OUT", "IR", "PUP", "DOUBTFUL", "QUESTIONABLE"):
                        p.injury_status = status
                        p.injured = status in ("OUT", "IR", "PUP")

            db.commit()
            logger.info("Enriched %d players with FantasyPros intelligence.", enriched_count)
            return {
                "success": True,
                "message": f"Successfully enriched {enriched_count} players with FantasyPros ECR and injury intelligence.",
                "enriched_count": enriched_count,
            }
        except Exception as e:
            db.rollback()
            logger.error("Error syncing FantasyPros intelligence: %s", e)
            return {
                "success": False,
                "message": f"Sync failed: {e}",
                "enriched_count": 0,
            }
        finally:
            if self._external_db is None:
                db.close()


fantasypros_sync_service = FantasyProsSyncService()
