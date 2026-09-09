"""DFS Slate Loader & Data Enrichment Engine.

Parses FanDuel / DraftKings player list CSVs and enriches every athlete with:
1. SQLite player projections and status
2. DraftEdge Defense-vs-Position (DvP) softness ranks and points allowed
3. Live Vegas game environments (spreads, game over/unders, team implied totals, dome status)
"""

import glob
import json
import logging
import os
import sqlite3
import statistics
from typing import Any
import pandas as pd

from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.adapters.nfl.dvp_client import dvp_client

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath("data/fantasy.db")


class DFSSlateLoader:
    """Ingests DFS CSVs and enriches player pools with Vegas and DvP metrics."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def find_latest_fanduel_csv(self) -> str | None:
        """Locates the latest FanDuel NFL player list CSV in the data directory."""
        pattern = os.path.join(self.data_dir, "FanDuel-NFL-*.csv")
        matches = glob.glob(pattern)
        if not matches:
            return None
        # Sort by modification time descending
        matches.sort(key=os.path.getmtime, reverse=True)
        return matches[0]

    async def load_slate(
        self,
        csv_path: str | None = None,
        season: int = 2026,
        week: int = 1,
        custom_projections: dict[str, float] | None = None,
        projection_source: str = "MODEL",
    ) -> pd.DataFrame:
        """Loads and enriches the complete player slate with Vegas, DvP, and source-specific projections."""
        target_csv = csv_path or self.find_latest_fanduel_csv()
        if not target_csv or not os.path.exists(target_csv):
            raise FileNotFoundError(
                f"Could not find a valid FanDuel player CSV in '{self.data_dir}'"
            )

        logger.info(f"Loading DFS slate from: {target_csv} with source: {projection_source}")
        df_raw = pd.read_csv(target_csv)

        # 1. Fetch Schedule & Vegas Lines
        sched = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)
        team_vegas: dict[str, dict[str, Any]] = {}
        for g in sched:
            # Home team
            team_vegas[g.home_team] = {
                "opponent": g.away_team,
                "is_home": True,
                "game": f"{g.away_team}@{g.home_team}",
                "game_ou": g.over_under,
                "spread": g.spread,
                "team_implied": g.home_implied_total,
                "opp_implied": g.away_implied_total,
                "is_fav": g.spread < 0,
                "fav_margin": abs(g.spread) if g.spread < 0 else 0,
                "is_dome": g.is_dome,
                "venue": g.venue_name,
            }
            # Away team
            team_vegas[g.away_team] = {
                "opponent": g.home_team,
                "is_home": False,
                "game": f"{g.away_team}@{g.home_team}",
                "game_ou": g.over_under,
                "spread": -g.spread,
                "team_implied": g.away_implied_total,
                "opp_implied": g.home_implied_total,
                "is_fav": g.spread > 0,
                "fav_margin": g.spread if g.spread > 0 else 0,
                "is_dome": g.is_dome,
                "venue": g.venue_name,
            }

        # 2. Fetch DvP Matrix from SQLite defense_vs_position table
        dvp_map: dict[tuple[str, str], dict[str, Any]] = {}
        try:
            conn = sqlite3.connect(DB_PATH)
            df_dvp = pd.read_sql_query(
                "SELECT pro_team, position, rank_softness, rank_defense, tier, tier_label, fd_fpa, dk_fpa FROM defense_vs_position",
                conn,
            )
            conn.close()
            for _, r in df_dvp.iterrows():
                t = str(r["pro_team"]).upper().strip()
                p = str(r["position"]).upper().strip()
                info = {
                    "softness_rank": int(r["rank_softness"]),
                    "rank_defense": int(r["rank_defense"]),
                    "tier": str(r["tier"]),
                    "tier_label": str(r["tier_label"]),
                    "fd_fpa": float(r["fd_fpa"]) if pd.notna(r.get("fd_fpa")) else 20.0,
                    "dk_fpa": float(r["dk_fpa"]) if pd.notna(r.get("dk_fpa")) else 20.0,
                }
                dvp_map[(t, p)] = info
                if t == "WAS":
                    dvp_map[("WSH", p)] = info
                elif t == "WSH":
                    dvp_map[("WAS", p)] = info
                if t == "JAX":
                    dvp_map[("JAC", p)] = info
                elif t == "JAC":
                    dvp_map[("JAX", p)] = info
        except Exception as e:
            logger.warning(f"Could not load SQLite DvP table, using neutral baselines: {e}")

        # 3. Query Players table from SQLite with multi-source projections
        conn = sqlite3.connect(DB_PATH)
        df_db_players = pd.read_sql_query(
            """SELECT id, full_name, pro_team, position, injury_status,
                      projected_points, projected_points_model, projected_points_fp,
                      projected_points_sleeper, projected_points_espn, projected_points_consensus
               FROM players""",
            conn,
        )
        conn.close()

        db_player_map: dict[tuple[str, str], dict[str, Any]] = {}
        for _, r in df_db_players.iterrows():
            norm_name = r["full_name"].strip().lower()
            db_player_map[(norm_name, r["pro_team"])] = {
                "db_proj": r["projected_points"],
                "proj_model": r["projected_points_model"],
                "proj_fp": r["projected_points_fp"],
                "proj_sleeper": r["projected_points_sleeper"],
                "proj_espn": r["projected_points_espn"],
                "proj_consensus": r["projected_points_consensus"],
                "injury_status": r["injury_status"],
            }

        source_clean = (projection_source or "MODEL").upper().strip()

        # 4. Enrich every slate player
        enriched: list[dict[str, Any]] = []
        for _, r in df_raw.iterrows():
            raw_name = r.get("Nickname")
            if pd.isna(raw_name) or not str(raw_name).strip():
                raw_name = f"{r.get('First Name', '')} {r.get('Last Name', '')}".strip()
            name = str(raw_name).strip()
            pos = str(r.get("Position", "")).strip()
            team = str(r.get("Team", "")).strip()
            opp = str(r.get("Opponent", "")).strip()
            salary = int(r.get("Salary", 0)) if pd.notna(r.get("Salary")) else 4000
            fppg = float(r["FPPG"]) if pd.notna(r.get("FPPG")) else 0.0
            played = int(r["Played"]) if pd.notna(r.get("Played")) else 0
            inj = str(r["Injury Indicator"]) if pd.notna(r.get("Injury Indicator")) else ""
            inj_det = str(r["Injury Details"]) if pd.notna(r.get("Injury Details")) else ""

            # Check Vegas context with fallback to CSV columns
            v = team_vegas.get(team)
            if not v:
                game_str = str(r.get("Game", "")) if pd.notna(r.get("Game")) else f"{team} vs {opp}"
                is_home = False
                if "@" in game_str:
                    parts = game_str.split("@")
                    if len(parts) == 2 and parts[1].strip().upper() == team.upper():
                        is_home = True
                v = {
                    "opponent": opp,
                    "is_home": is_home,
                    "game": game_str,
                    "game_ou": 44.5,
                    "spread": 0.0,
                    "team_implied": 22.25,
                    "opp_implied": 22.25,
                    "is_fav": False,
                    "fav_margin": 0.0,
                    "is_dome": False,
                    "venue": "NFL Stadium",
                }

            # Check DvP context
            opp_clean = "WAS" if opp.upper().strip() in ["WAS", "WSH"] else ("JAX" if opp.upper().strip() in ["JAC", "JAX"] else opp.upper().strip())
            pos_clean = pos.upper().strip()

            if pos_clean in ("D", "DEF", "D/ST", "DST"):
                raw_dst_rank = dvp_client.get_position_rank(opp_clean, "DST")
                soft_rank = 33 - raw_dst_rank if raw_dst_rank else 16
                if soft_rank <= 8:
                    tier, tier_label = "SMASH", "Elite Smash Matchup"
                elif soft_rank <= 15:
                    tier, tier_label = "FAVORABLE", "Favorable Matchup"
                elif soft_rank <= 20:
                    tier, tier_label = "NEUTRAL", "Neutral Matchup"
                else:
                    tier, tier_label = "TOUGH", "Stout Opponent"
                dvp = {
                    "softness_rank": soft_rank,
                    "tier": tier,
                    "tier_label": tier_label,
                    "fd_fpa": 8.0,
                }
            else:
                dvp = dvp_map.get((opp_clean, pos_clean), {})
                if not dvp:
                    # Fallback to dvp_client profile
                    raw_rank = dvp_client.get_position_rank(opp_clean, pos_clean)
                    soft_rank = 33 - raw_rank if raw_rank else 16
                    dvp = {
                        "softness_rank": soft_rank,
                        "tier": "NEUTRAL" if 9 <= soft_rank <= 20 else ("SMASH" if soft_rank <= 8 else "TOUGH"),
                        "tier_label": "Neutral Matchup" if 9 <= soft_rank <= 20 else ("Favorable Matchup" if soft_rank <= 8 else "Stout Defense"),
                        "fd_fpa": 20.0,
                    }
                else:
                    soft_rank = dvp.get("softness_rank", 16)

            # DB projection lookup
            db_info = db_player_map.get((name.strip().lower(), team), {})
            db_status = db_info.get("injury_status", "ACTIVE")

            # Determine source-specific baseline projection
            if source_clean == "FANTASYPROS":
                val = db_info.get("proj_fp")
                if val is not None and pd.notna(val) and float(val) > 0:
                    base_proj = float(val)
                elif db_info.get("db_proj") and pd.notna(db_info.get("db_proj")) and float(db_info["db_proj"]) > 0:
                    base_proj = float(db_info["db_proj"])
                elif fppg > 0:
                    base_proj = fppg
                else:
                    base_proj = 4.0 if pos != "D" else 5.0
            elif source_clean == "SLEEPER":
                val = db_info.get("proj_sleeper")
                if val is not None and pd.notna(val) and float(val) > 0:
                    base_proj = float(val)
                elif db_info.get("db_proj") and pd.notna(db_info.get("db_proj")) and float(db_info["db_proj"]) > 0:
                    base_proj = float(db_info["db_proj"])
                elif fppg > 0:
                    base_proj = fppg
                else:
                    base_proj = 4.0 if pos != "D" else 5.0
            elif source_clean == "ESPN":
                val = db_info.get("proj_espn")
                if val is not None and pd.notna(val) and float(val) > 0:
                    base_proj = float(val)
                elif db_info.get("db_proj") and pd.notna(db_info.get("db_proj")) and float(db_info["db_proj"]) > 0:
                    base_proj = float(db_info["db_proj"])
                elif fppg > 0:
                    base_proj = fppg
                else:
                    base_proj = 4.0 if pos != "D" else 5.0
            elif source_clean == "CONSENSUS":
                val = db_info.get("proj_consensus")
                if val is not None and pd.notna(val) and float(val) > 0:
                    base_proj = float(val)
                else:
                    signals = [
                        float(db_info[k]) for k in ("proj_model", "proj_fp", "proj_sleeper", "proj_espn", "db_proj")
                        if db_info.get(k) is not None and pd.notna(db_info.get(k)) and float(db_info[k]) > 0
                    ]
                    if signals:
                        med = float(statistics.median(signals))
                        clamped = [med + max(-0.35 * med, min(0.35 * med, s - med)) for s in signals]
                        base_proj = float(sum(clamped) / len(clamped))
                    elif fppg > 0:
                        base_proj = fppg
                    else:
                        base_proj = 4.0 if pos != "D" else 5.0
            else:
                # MODEL
                val = db_info.get("proj_model")
                if val is not None and pd.notna(val) and float(val) > 0:
                    base_proj = float(val)
                elif db_info.get("db_proj") and pd.notna(db_info.get("db_proj")) and float(db_info["db_proj"]) > 0:
                    base_proj = float(db_info["db_proj"])
                elif fppg > 0:
                    base_proj = fppg
                else:
                    base_proj = 4.0 if pos != "D" else 5.0

            # Algorithm Adjusted Fantasy Projection
            if pos == "D":
                if base_proj > 0 and base_proj not in (4.0, 5.0):
                    final_proj = round(max(3.0, base_proj), 2)
                else:
                    opp_imp = v.get("opp_implied", 22.0)
                    is_fav = v.get("is_fav", False)
                    margin = v.get("fav_margin", 0.0)
                    dst_score = (25.0 - opp_imp) * 0.4 + (3.0 if is_fav else 0.0) + (margin * 0.2) + (fppg * 0.4)
                    final_proj = round(max(3.0, dst_score), 2)
            else:
                if source_clean == "MODEL":
                    # If base_proj came from our calibrated Quant Model, it already has macro Vegas + DvP applied
                    if db_info.get("proj_model") and float(db_info["proj_model"]) > 0:
                        final_proj = round(max(1.0, base_proj), 2)
                    else:
                        matchup_adj = (16.5 - soft_rank) * 0.14
                        implied_adj = (v.get("team_implied", 22.0) - 22.0) * 0.25
                        script_adj = 0.0
                        if pos == "RB":
                            if v.get("is_fav") and v.get("fav_margin", 0) >= 3.0:
                                script_adj = 1.2
                            elif not v.get("is_fav") and abs(v.get("spread", 0)) >= 6.0:
                                script_adj = -0.8
                        final_proj = round(max(1.0, base_proj + matchup_adj + implied_adj + script_adj), 2)
                else:
                    # Provider direct projections
                    final_proj = round(max(1.0, base_proj), 2)

            # Check for user-defined custom projection overrides
            if custom_projections:
                player_id_key = str(r.get("Id", "")).strip()
                if name in custom_projections:
                    final_proj = round(float(custom_projections[name]), 2)
                elif player_id_key in custom_projections:
                    final_proj = round(float(custom_projections[player_id_key]), 2)

            value_ratio = round(final_proj / (salary / 1000), 2) if salary > 0 else 0.0

            # 90th Percentile Ceiling & Safety Floor Modeling (FanDuel Half-PPR Nuances)
            game_ou = v.get("game_ou", 44.0)
            team_imp = v.get("team_implied", 22.0)
            is_fav = v.get("is_fav", False)

            if pos == "QB":
                shootout_boost = 2.0 if game_ou >= 48.0 else 0.0
                ceiling_proj = round(final_proj * 1.35 + shootout_boost, 2)
                floor_proj = round(final_proj * 0.70, 2)
            elif pos == "RB":
                goal_line_boost = 2.5 if (is_fav and team_imp >= 24.0) else 0.0
                ceiling_proj = round(final_proj * 1.40 + goal_line_boost, 2)
                floor_proj = round(final_proj * 0.65, 2)
            elif pos == "WR":
                boom_boost = 3.0 if game_ou >= 48.0 else (1.2 if soft_rank <= 8 else 0.0)
                ceiling_proj = round(final_proj * 1.45 + boom_boost, 2)
                floor_proj = round(final_proj * 0.55, 2)
            elif pos == "TE":
                redzone_boost = 2.0 if team_imp >= 24.0 else 0.0
                ceiling_proj = round(final_proj * 1.40 + redzone_boost, 2)
                floor_proj = round(final_proj * 0.50, 2)
            else:  # Defense
                ceiling_proj = round(final_proj * 1.65, 2)
                floor_proj = round(final_proj * 0.40, 2)

            enriched.append({
                "player_id": r["Id"],
                "name": name,
                "position": pos,
                "team": team,
                "opponent": opp,
                "salary": salary,
                "fppg": fppg,
                "played": played,
                "injury": inj,
                "injury_details": inj_det,
                "db_status": db_status,
                "base_proj": base_proj,
                "proj": final_proj,
                "ceiling_proj": ceiling_proj,
                "floor_proj": floor_proj,
                "value_ratio": value_ratio,
                # Vegas Metrics
                "game": v.get("game"),
                "is_home": v.get("is_home"),
                "is_dome": v.get("is_dome"),
                "game_ou": v.get("game_ou"),
                "spread": v.get("spread"),
                "team_implied": v.get("team_implied"),
                "opp_implied": v.get("opp_implied"),
                "is_fav": v.get("is_fav"),
                "fav_margin": v.get("fav_margin"),
                # DvP Metrics
                "opp_soft_rank": soft_rank,
                "opp_tier": dvp.get("tier", "NEUTRAL"),
                "opp_tier_label": dvp.get("tier_label", "Neutral"),
                "opp_fd_fpa": dvp.get("fd_fpa", 20.0),
                "opp_rush_yds_allowed": dvp.get("rush_yds_allowed", 0.0),
                "opp_rush_td_allowed": dvp.get("rush_td_allowed", 0.0),
            })

        df_enriched = pd.DataFrame(enriched)
        
        # 5. Enrich with Ownership Projections and Leverage Scores
        from src.dfs.ownership import dfs_ownership
        df_enriched = dfs_ownership.calculate_ownership(df_enriched)

        logger.info(f"Successfully enriched {len(df_enriched)} slate players with Vegas, DvP, and Ownership")
        return df_enriched


dfs_loader = DFSSlateLoader()
