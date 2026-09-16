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
import re
import sqlite3
import statistics
from pathlib import Path
from typing import Any
import pandas as pd

from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.adapters.nfl.dvp_client import dvp_client
from src.services.recommendation.projection_engine import (
    quant_projection_engine,
    get_receiver_micro_metrics,
    get_team_trench_metrics,
)
from src.db.models import PlayerModel

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
        week: int | None = None,
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

        # Auto-detect week from CSV content or SQLite current_week
        eff_week = week
        if eff_week is None:
            if "DET@BUF" in str(df_raw.to_dict()) or "detvsbuffalo" in str(target_csv).lower():
                eff_week = 2
            elif "9-13" in str(target_csv) or "NO@DET" in str(df_raw.to_dict()) or "BUF@HOU" in str(df_raw.to_dict()):
                eff_week = 1
            else:
                try:
                    conn_tmp = sqlite3.connect(DB_PATH)
                    cw = conn_tmp.execute("SELECT current_week FROM leagues LIMIT 1").fetchone()
                    conn_tmp.close()
                    eff_week = cw[0] if cw and cw[0] else 2
                except Exception:
                    eff_week = 2

        # 1. Fetch Schedule & Vegas Lines
        sched = await nfl_schedule_client.fetch_week_schedule(season=season, week=eff_week)
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

        # 3b. Load Live Injury Wire & Beneficiary Hierarchies
        live_inactives: set[str] = set()
        live_beneficiaries: dict[str, dict[str, Any]] = {}
        inj_path = Path(self.data_dir) / "injuries_live_2026.json"
        if inj_path.exists():
            try:
                with open(inj_path, encoding="utf-8") as f:
                    inj_wire = json.load(f)
                for inj_item in inj_wire.get("injuries", []):
                    st = str(inj_item.get("status", "")).upper()
                    is_out_flag = inj_item.get("is_out") or st in ("OUT", "IR", "INACTIVE", "DOUBTFUL") or "IR" in st
                    p_norm = re.sub(r"[^\w\s]", "", str(inj_item.get("name", "")).lower()).strip()
                    if is_out_flag and p_norm:
                        live_inactives.add(p_norm)

                        # Verified Starters Sidelined -> Direct Beneficiaries
                        if "BOWERS" in p_norm.upper():
                            live_beneficiaries["michael mayer"] = {
                                "injured_name": "Brock Bowers",
                                "pos": "TE",
                                "team": "LV",
                                "status": "OUT",
                                "note": "Assumes starting inline TE role and red-zone targets with Brock Bowers OUT.",
                                "baseline_boost": 11.5,
                            }
                        elif "JACOBS" in p_norm.upper():
                            live_beneficiaries["marshawn lloyd"] = {
                                "injured_name": "Josh Jacobs",
                                "pos": "RB",
                                "team": "GB",
                                "status": "OUT",
                                "note": "Primary starting running back with Josh Jacobs OUT.",
                                "baseline_boost": 13.0,
                            }
                            live_beneficiaries["emanuel wilson"] = {
                                "injured_name": "Josh Jacobs",
                                "pos": "RB",
                                "team": "GB",
                                "status": "OUT",
                                "note": "Rotational goal-line and change-of-pace back with Josh Jacobs OUT.",
                                "baseline_boost": 9.0,
                            }
                        elif "TUCKER" in p_norm.upper():
                            live_beneficiaries["bucky irving"] = {
                                "injured_name": "Sean Tucker",
                                "pos": "RB",
                                "team": "TB",
                                "status": "DOUBTFUL",
                                "note": "Consolidated workhorse bellcow role with Sean Tucker doubtful.",
                                "baseline_boost": 17.5,
                            }
                        elif "DARNOLD" in p_norm.upper():
                            live_beneficiaries["drew lock"] = {
                                "injured_name": "Sam Darnold",
                                "pos": "QB",
                                "team": "SEA",
                                "status": "DOUBTFUL",
                                "note": "Starting QB taking over first-team snaps with Sam Darnold doubtful.",
                                "baseline_boost": 13.5,
                            }
                        elif "MCMILLAN" in p_norm.upper():
                            live_beneficiaries["emeka egbuka"] = {
                                "injured_name": "Jalen McMillan",
                                "pos": "WR",
                                "team": "TB",
                                "status": "DOUBTFUL",
                                "note": "Target progression expansion with Jalen McMillan doubtful.",
                                "baseline_boost": 14.5,
                            }
                        elif "HENDERSON" in p_norm.upper():
                            live_beneficiaries["rhamondre stevenson"] = {
                                "injured_name": "TreVeyon Henderson",
                                "pos": "RB",
                                "team": "NE",
                                "status": "OUT",
                                "note": "Workhorse consolidation with TreVeyon Henderson OUT.",
                                "baseline_boost": 15.0,
                            }
                        elif "BROWN" in p_norm.upper() and "A.J." in inj_item.get("name", ""):
                            live_beneficiaries["demario douglas"] = {
                                "injured_name": "A.J. Brown",
                                "pos": "WR",
                                "team": "NE",
                                "status": "IR",
                                "note": "Primary perimeter target with A.J. Brown on IR.",
                                "baseline_boost": 12.0,
                            }
                        elif "LOVE" in p_norm.upper() and st in ("OUT", "DOUBTFUL"):
                            live_beneficiaries["tyler allgeier"] = {
                                "injured_name": "Jeremiyah Love",
                                "pos": "RB",
                                "team": "ARI",
                                "status": st,
                                "note": "Workhorse starter with Jeremiyah Love sidelined.",
                                "baseline_boost": 13.5,
                            }
            except Exception as e:
                logger.debug(f"Failed to load live injury wire in loader: {e}")

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

            norm_name = re.sub(r"[^\w\s]", "", name.lower()).strip()
            is_out = (
                inj in ("IR", "O", "OUT", "DOUBTFUL")
                or db_status in ("IR", "OUT", "DOUBTFUL")
                or norm_name in live_inactives
            )
            if is_out and inj not in ("IR", "OUT", "DOUBTFUL"):
                inj = "OUT"

            is_beneficiary = False
            beneficiary_of = None
            vacated_note = None
            milestone_bonus = 0.0
            wr_micro = get_receiver_micro_metrics(name)

            if is_out:
                base_proj = 0.0
                final_proj = 0.0
                ceiling_proj = 0.0
                floor_proj = 0.0
                value_ratio = 0.0
            else:
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
                    # MODEL: Institutional Quant Engine in HALF_PPR mode
                    temp_player = PlayerModel(
                        id=0,
                        full_name=name,
                        position=pos,
                        pro_team=team,
                        projected_points_espn=float(db_info.get("proj_espn") or fppg or 0.0),
                        projected_points_fp=float(db_info.get("proj_fp") or 0.0),
                        projected_points_model=float(db_info.get("proj_model") or 0.0),
                        fp_rank_ecr=int(db_info.get("consensus_rank")) if db_info.get("consensus_rank") else None,
                        fp_pos_rank=str(db_info.get("fp_pos_rank") or ""),
                        injury_status="OUT" if is_out else db_status,
                    )
                    model_res = quant_projection_engine.calculate_player_projection(
                        temp_player,
                        scoring_format="HALF_PPR",
                        projection_source="MODEL",
                    )
                    base_proj = model_res.projected_points
                    final_proj = model_res.projected_points
                    milestone_bonus = model_res.milestone_bonus_points

                # Check beneficiary mapping for elevated vacated workload
                b_match = live_beneficiaries.get(norm_name)
                if not b_match:
                    for bk_key, bk_val in live_beneficiaries.items():
                        if bk_key in norm_name or norm_name in bk_key:
                            b_match = bk_val
                            break
                if b_match:
                    is_beneficiary = True
                    beneficiary_of = b_match["injured_name"]
                    vacated_note = b_match["note"]
                    boost = float(b_match.get("baseline_boost", 10.5))
                    # Convert boost to Half-PPR if needed
                    base_proj = max(base_proj, boost * 0.88)
                    final_proj = max(final_proj, base_proj)

                # Algorithm Adjusted Fantasy Projection for non-MODEL sources
                if source_clean != "MODEL":
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
                        matchup_adj = (16.5 - soft_rank) * 0.14
                        implied_adj = (v.get("team_implied", 22.0) - 22.0) * 0.25
                        script_adj = 0.0
                        if pos == "RB":
                            if v.get("is_fav") and v.get("fav_margin", 0) >= 3.0:
                                script_adj = 1.2
                            elif not v.get("is_fav") and abs(v.get("spread", 0)) >= 6.0:
                                script_adj = -0.8
                        final_proj = round(max(1.0, base_proj + matchup_adj + implied_adj + script_adj), 2)

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
                "is_out": is_out,
                "is_beneficiary": is_beneficiary,
                "beneficiary_of": beneficiary_of,
                "vacated_note": vacated_note,
                "base_proj": base_proj,
                "proj": final_proj,
                "ceiling_proj": ceiling_proj,
                "floor_proj": floor_proj,
                "value_ratio": value_ratio,
                "milestone_bonus": milestone_bonus,
                "separation_score": wr_micro.get("separation_score"),
                "first_read_pct": wr_micro.get("first_read_pct"),
                "regression_index": wr_micro.get("regression_index"),
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
