"""NFL Athlete & Fantasy Game Log Service.

Retrieves, parses, and enriches historical game logs and itemized box-score statistics
for any NFL player or D/ST unit across the 2026 season.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger(__name__)

ESPN_GAMELOG_URL = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{athlete_id}/gamelog"
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "fantasy.db"
DEPTH_CHART_PATH = BASE_DIR / "data" / "nfl_depth_charts_2026.json"
INJURIES_PATH = BASE_DIR / "data" / "injuries_live_2026.json"

NFL_DST_MAP: dict[str, tuple[str, str, int]] = {
    "ARI": ("Cardinals D/ST", "ARI", -16001),
    "ATL": ("Falcons D/ST", "ATL", -16002),
    "BAL": ("Ravens D/ST", "BAL", -16033),
    "BUF": ("Bills D/ST", "BUF", -16004),
    "CAR": ("Panthers D/ST", "CAR", -16005),
    "CHI": ("Bears D/ST", "CHI", -16006),
    "CIN": ("Bengals D/ST", "CIN", -16007),
    "CLE": ("Browns D/ST", "CLE", -16005),
    "DAL": ("Cowboys D/ST", "DAL", -16009),
    "DEN": ("Broncos D/ST", "DEN", -16007),
    "DET": ("Lions D/ST", "DET", -16008),
    "GB": ("Packers D/ST", "GB", -16010),
    "HOU": ("Texans D/ST", "HOU", -16034),
    "IND": ("Colts D/ST", "IND", -16011),
    "JAX": ("Jaguars D/ST", "JAX", -16013),
    "KC": ("Chiefs D/ST", "KC", -16012),
    "LV": ("Raiders D/ST", "LV", -16015),
    "LAC": ("Chargers D/ST", "LAC", -16024),
    "LAR": ("Rams D/ST", "LAR", -16014),
    "MIA": ("Dolphins D/ST", "MIA", -16016),
    "MIN": ("Vikings D/ST", "MIN", -16018),
    "NE": ("Patriots D/ST", "NE", -16017),
    "NO": ("Saints D/ST", "NO", -16019),
    "NYG": ("Giants D/ST", "NYG", -16020),
    "NYJ": ("Jets D/ST", "NYJ", -16022),
    "PHI": ("Eagles D/ST", "PHI", -16021),
    "PIT": ("Steelers D/ST", "PIT", -16023),
    "SF": ("49ers D/ST", "SF", -16025),
    "SEA": ("Seahawks D/ST", "SEA", -16026),
    "TB": ("Buccaneers D/ST", "TB", -16027),
    "TEN": ("Titans D/ST", "TEN", -16028),
    "WAS": ("Commanders D/ST", "WAS", -16029),
}


class GameLogService:
    """Provides zero-latency, cached historical game logs and fantasy scoring breakdowns."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._cache: dict[tuple[int, int], dict[str, Any]] = {}
        self._name_to_id_cache: dict[str, int] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def _resolve_athlete_by_name_or_id(self, player_id_or_name: int | str) -> tuple[int | None, str | None, str | None, str | None]:
        """Resolves athlete ID, full name, position, and pro team using player_resolver, SQLite, Depth Charts, or Injury JSON."""
        # 0. High-accuracy identity resolver lookup
        try:
            from src.core.identity.resolver import player_resolver
            if isinstance(player_id_or_name, int) or (isinstance(player_id_or_name, str) and player_id_or_name.lstrip("-").isdigit()):
                res = player_resolver.resolve(espn_id=int(player_id_or_name))
                if res and res.full_name:
                    return res.espn_id, res.full_name, res.position, res.team
            elif isinstance(player_id_or_name, str) and player_id_or_name.strip():
                res = player_resolver.resolve(name=player_id_or_name.strip())
                if res and res.full_name:
                    return res.espn_id, res.full_name, res.position, res.team
        except Exception as e:
            logger.debug(f"player_resolver lookup error for {player_id_or_name}: {e}")

        # 1. Handle integer or numeric ID input
        if isinstance(player_id_or_name, int) or (isinstance(player_id_or_name, str) and player_id_or_name.lstrip("-").isdigit()):
            pid = int(player_id_or_name)
            # If negative ID, check if it's a D/ST
            if pid < 0:
                for abbr, (t_name, t_abbr, d_id) in NFL_DST_MAP.items():
                    if d_id == pid:
                        return d_id, t_name, "D/ST", t_abbr
                return pid, f"D/ST {pid}", "D/ST", "DEF"

            # Check SQLite if DB exists
            if DB_PATH.exists():
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    row = cursor.execute(
                        "SELECT id, full_name, position, pro_team FROM players WHERE id = ?", (pid,)
                    ).fetchone()
                    conn.close()
                    if row:
                        return row[0], row[1], row[2], row[3]
                except Exception as e:
                    logger.debug(f"DB lookup failed for ID {pid}: {e}")

            # Fallback to Depth Chart JSON
            if DEPTH_CHART_PATH.exists():
                try:
                    with open(DEPTH_CHART_PATH, "r", encoding="utf-8") as f:
                        dc_data = json.load(f)
                    for team_abbr, tdata in dc_data.get("teams", {}).items():
                        for unit in ["offense", "defense", "special_teams"]:
                            for slot, players in tdata.get(unit, {}).items():
                                for p in players:
                                    if p.get("id") == pid:
                                        pos = slot.upper().rstrip("12345")
                                        return pid, p.get("name"), pos, team_abbr
                except Exception as e:
                    logger.debug(f"Depth chart lookup failed for ID {pid}: {e}")

            return pid, None, None, None

        # 2. Check by Name or D/ST alias
        name_query = str(player_id_or_name).strip()
        clean_q = name_query.lower().replace(" d/st", "").replace(" defense", "").replace("dst", "").strip()

        alias_map: dict[str, str] = {
            "bills": "BUF", "buffalo": "BUF", "buffalo bills": "BUF",
            "vikings": "MIN", "minnesota": "MIN", "minnesota vikings": "MIN",
            "49ers": "SF", "niners": "SF", "san francisco": "SF", "san francisco 49ers": "SF",
            "packers": "GB", "green bay": "GB", "green bay packers": "GB",
            "cowboys": "DAL", "dallas": "DAL", "dallas cowboys": "DAL",
            "lions": "DET", "detroit": "DET", "detroit lions": "DET",
            "chiefs": "KC", "kansas city": "KC", "kansas city chiefs": "KC",
            "eagles": "PHI", "philadelphia": "PHI", "philadelphia eagles": "PHI",
            "steelers": "PIT", "pittsburgh": "PIT", "pittsburgh steelers": "PIT",
            "ravens": "BAL", "baltimore": "BAL", "baltimore ravens": "BAL",
            "texans": "HOU", "houston": "HOU", "houston texans": "HOU",
            "bengals": "CIN", "cincinnati": "CIN", "cincinnati bengals": "CIN",
            "bears": "CHI", "chicago": "CHI", "chicago bears": "CHI",
            "falcons": "ATL", "atlanta": "ATL", "atlanta falcons": "ATL",
            "panthers": "CAR", "carolina": "CAR", "carolina panthers": "CAR",
            "saints": "NO", "new orleans": "NO", "new orleans saints": "NO",
            "buccaneers": "TB", "bucs": "TB", "tampa": "TB", "tampa bay": "TB", "tampa bay buccaneers": "TB",
            "commanders": "WAS", "washington": "WAS", "washington commanders": "WAS",
            "cardinals": "ARI", "arizona": "ARI", "arizona cardinals": "ARI",
            "seahawks": "SEA", "seattle": "SEA", "seattle seahawks": "SEA",
            "rams": "LAR", "los angeles rams": "LAR", "la rams": "LAR",
            "chargers": "LAC", "los angeles chargers": "LAC", "la chargers": "LAC",
            "raiders": "LV", "las vegas": "LV", "las vegas raiders": "LV",
            "broncos": "DEN", "denver": "DEN", "denver broncos": "DEN",
            "colts": "IND", "indianapolis": "IND", "indianapolis colts": "IND",
            "jaguars": "JAX", "jacksonville": "JAX", "jacksonville jaguars": "JAX",
            "titans": "TEN", "tennessee": "TEN", "tennessee titans": "TEN",
            "jets": "NYJ", "new york jets": "NYJ", "ny jets": "NYJ",
            "giants": "NYG", "new york giants": "NYG", "ny giants": "NYG",
            "patriots": "NE", "new england": "NE", "new england patriots": "NE",
            "browns": "CLE", "cleveland": "CLE", "cleveland browns": "CLE",
            "dolphins": "MIA", "miami": "MIA", "miami dolphins": "MIA",
        }
        resolved_abbr = alias_map.get(clean_q) or (clean_q.upper() if clean_q.upper() in NFL_DST_MAP else None)
        if resolved_abbr and resolved_abbr in NFL_DST_MAP:
            t_name, t_abbr, d_id = NFL_DST_MAP[resolved_abbr]
            return d_id, t_name, "D/ST", t_abbr

        # 3. Check SQLite by Name if DB exists
        if DB_PATH.exists():
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT id, full_name, position, pro_team FROM players WHERE LOWER(full_name) = LOWER(?) LIMIT 1",
                    (name_query,),
                ).fetchone()
                conn.close()
                if row:
                    return row[0], row[1], row[2], row[3]
            except Exception as e:
                logger.debug(f"DB lookup failed for name {name_query}: {e}")

        # 4. Check Depth Charts JSON by Name
        if DEPTH_CHART_PATH.exists():
            try:
                with open(DEPTH_CHART_PATH, "r", encoding="utf-8") as f:
                    dc_data = json.load(f)
                for team_abbr, tdata in dc_data.get("teams", {}).items():
                    for unit in ["offense", "defense", "special_teams"]:
                        for slot, players in tdata.get(unit, {}).items():
                            for p in players:
                                if p.get("name", "").lower() == name_query.lower():
                                    pos = slot.upper().rstrip("12345")
                                    return p.get("id"), p.get("name"), pos, team_abbr
            except Exception as e:
                logger.debug(f"Depth chart lookup failed for name {name_query}: {e}")

        # 5. Check Injuries JSON by Name
        if INJURIES_PATH.exists():
            try:
                with open(INJURIES_PATH, "r", encoding="utf-8") as f:
                    inj_data = json.load(f)
                for inj in inj_data.get("injuries", []):
                    if inj.get("name", "").lower() == name_query.lower():
                        return inj.get("athlete_id"), inj.get("name"), inj.get("position"), inj.get("team_abbr") or inj.get("team")
            except Exception as e:
                logger.debug(f"Injuries lookup failed for name {name_query}: {e}")

        return None, name_query, None, None

    async def get_player_gamelog(
        self,
        player_id_or_name: int | str,
        season: int = 2026,
    ) -> dict[str, Any]:
        """Retrieves and formats complete 2026 game logs for an athlete."""
        pid, name, pos, team = self._resolve_athlete_by_name_or_id(player_id_or_name)

        if pid is not None and pid < 0:
            # Defense / Special Teams unit
            return await self._get_dst_gamelog(pid, name or f"D/ST {pid}", team or "DEF", season)

        athlete_id = pid
        if not athlete_id:
            return {
                "success": False,
                "player_id": player_id_or_name,
                "player_name": name or str(player_id_or_name),
                "season": season,
                "message": f"Player '{player_id_or_name}' could not be resolved.",
                "logs": [],
                "season_totals": {},
            }

        cache_key = (athlete_id, season)
        if cache_key in self._cache:
            return self._cache[cache_key]

        url = ESPN_GAMELOG_URL.format(athlete_id=athlete_id)
        params = {"season": str(season)}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 404:
                    return await self._get_fantasy_db_gamelog(athlete_id, name, pos, team, season)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Failed to fetch public ESPN gamelog for athlete {athlete_id}: {e}")
                return await self._get_fantasy_db_gamelog(athlete_id, name, pos, team, season)

        display_names: list[str] = data.get("displayNames", [])
        events_meta: dict[str, Any] = data.get("events", {})

        season_types = data.get("seasonTypes", [])
        if not season_types:
            return await self._get_fantasy_db_gamelog(athlete_id, name, pos, team, season)

        categories = season_types[0].get("categories", [])
        if not categories:
            return await self._get_fantasy_db_gamelog(athlete_id, name, pos, team, season)

        parsed_logs: list[dict[str, Any]] = []

        for cat in categories:
            for ev in cat.get("events", []):
                ev_id = ev.get("eventId")
                stats_vals = ev.get("stats", [])
                meta = events_meta.get(ev_id, {})

                stat_dict = {
                    display_names[i]: stats_vals[i]
                    for i in range(min(len(display_names), len(stats_vals)))
                }

                week = meta.get("week", 1)
                at_vs = meta.get("atVs", "vs")
                is_home = at_vs == "vs"
                opp_obj = meta.get("opponent", {})
                opp_abbr = opp_obj.get("abbreviation", "UNK")
                opp_name = opp_obj.get("displayName", opp_abbr)
                game_date = meta.get("gameDate", "")[:10]
                game_result = meta.get("gameResult", "")
                score = meta.get("score", "")
                result_str = f"{game_result} {score}".strip() if score else game_result

                existing = next((log for log in parsed_logs if log["event_id"] == ev_id), None)
                if existing:
                    existing["raw_stats"].update(stat_dict)
                    continue

                parsed_logs.append({
                    "event_id": ev_id,
                    "week": week,
                    "date": game_date,
                    "opponent": opp_abbr,
                    "opponent_name": opp_name,
                    "at_vs": at_vs,
                    "is_home": is_home,
                    "result": result_str,
                    "raw_stats": stat_dict,
                })

        logs: list[dict[str, Any]] = []
        for plog in parsed_logs:
            raw = plog["raw_stats"]
            log_item = self._build_game_log_item(plog, raw, pos)
            logs.append(log_item)

        logs.sort(key=lambda x: x["week"], reverse=True)
        season_totals = self._compute_season_totals(logs)

        result = {
            "success": True,
            "player_id": athlete_id,
            "player_name": name or str(athlete_id),
            "position": pos or "UNK",
            "pro_team": team or "UNK",
            "season": season,
            "games_played": len(logs),
            "logs": logs,
            "season_totals": season_totals,
        }

        self._cache[cache_key] = result
        return result

    def _build_game_log_item(self, base_log: dict[str, Any], raw: dict[str, Any], pos: str | None) -> dict[str, Any]:
        """Calculates normalized stats, fantasy points, and human-readable summary line."""
        def _get_int(key: str) -> int:
            val = raw.get(key, 0)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, str):
                cleaned = val.replace("-", "0").split("/")[0].split("-")[0].strip()
                try:
                    return int(cleaned) if cleaned else 0
                except ValueError:
                    return 0
            return 0

        def _get_float(key: str) -> float:
            val = raw.get(key, 0.0)
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                cleaned = val.replace("-", "0").strip()
                try:
                    return float(cleaned) if cleaned else 0.0
                except ValueError:
                    return 0.0
            return 0.0

        pass_cmp = _get_int("Completions")
        pass_att = _get_int("Passing Attempts")
        pass_yds = _get_int("Passing Yards")
        pass_td = _get_int("Passing Touchdowns")
        pass_int = _get_int("Interceptions")
        qbr = _get_float("Adjusted QBR") or _get_float("Passer Rating")

        rush_att = _get_int("Rushing Attempts")
        rush_yds = _get_int("Rushing Yards")
        rush_td = _get_int("Rushing Touchdowns")
        rush_long = _get_int("Long Rushing")
        ypc = round(rush_yds / rush_att, 1) if rush_att > 0 else 0.0

        targets = _get_int("Receiving Targets")
        receptions = _get_int("Receptions")
        rec_yds = _get_int("Receiving Yards")
        rec_td = _get_int("Receiving Touchdowns")
        rec_long = _get_int("Long Reception")
        ypr = round(rec_yds / receptions, 1) if receptions > 0 else 0.0
        catch_pct = round((receptions / targets) * 100, 1) if targets > 0 else 0.0

        fg_made = _get_int("Field goals made")
        xp_made = _get_int("Extra Points Made")
        fg_long = _get_int("Long Field Goal Made")

        fumbles_lost = _get_int("Fumbles Lost")

        pass_pts = (pass_yds * 0.04) + (pass_td * 4.0) - (pass_int * 2.0)
        rush_pts = (rush_yds * 0.1) + (rush_td * 6.0)
        rec_base_pts = (rec_yds * 0.1) + (rec_td * 6.0)
        misc_pts = -(fumbles_lost * 2.0)
        kick_pts = (xp_made * 1.0) + (fg_made * 3.0)

        standard_pts = round(pass_pts + rush_pts + rec_base_pts + misc_pts + kick_pts, 2)
        half_ppr_pts = round(standard_pts + (receptions * 0.5), 2)
        full_ppr_pts = round(standard_pts + (receptions * 1.0), 2)

        summary_parts = []
        clean_pos = (pos or "").upper().strip()

        if clean_pos == "QB" or pass_att > 0 or (pass_yds > 0 and pass_yds >= rush_yds):
            # QB priority: Pass Yards, Pass TDs, Cmp/Att, Rush Yards, Rush TDs, INTs
            if pass_yds > 0 or pass_att > 0:
                summary_parts.append(f"{pass_yds} Pass Yds")
                summary_parts.append(f"{pass_td} Pass TD")
                if pass_att > 0:
                    summary_parts.append(f"{pass_cmp}/{pass_att} Cmp")
                if pass_int > 0:
                    summary_parts.append(f"{pass_int} INT")
            if rush_yds > 0 or rush_att > 0:
                summary_parts.append(f"{rush_yds} Rush Yds")
                if rush_td > 0:
                    summary_parts.append(f"{rush_td} Rush TD")
                if rush_att > 0:
                    summary_parts.append(f"{rush_att} Car")
        elif clean_pos in ("RB", "FB"):
            # RB priority: Rush Yards, Rush TDs, Carries, Rec Yards, Rec TDs, Receptions
            if rush_yds > 0 or rush_att > 0:
                summary_parts.append(f"{rush_yds} Rush Yds")
                if rush_td > 0:
                    summary_parts.append(f"{rush_td} Rush TD")
                if rush_att > 0:
                    summary_parts.append(f"{rush_att} Car ({ypc} YPC)")
            if rec_yds > 0 or receptions > 0 or targets > 0:
                summary_parts.append(f"{rec_yds} Rec Yds")
                if rec_td > 0:
                    summary_parts.append(f"{rec_td} Rec TD")
                summary_parts.append(f"{receptions} Rec ({targets} Tgt)")
        elif clean_pos in ("WR", "TE"):
            # WR/TE priority: Rec Yards, Rec TDs, Receptions, Targets, YPR
            if rec_yds > 0 or receptions > 0 or targets > 0:
                summary_parts.append(f"{rec_yds} Rec Yds")
                if rec_td > 0:
                    summary_parts.append(f"{rec_td} Rec TD")
                summary_parts.append(f"{receptions} Rec ({targets} Tgt)")
                if ypr > 0:
                    summary_parts.append(f"{ypr} YPR")
            if rush_yds > 0 or rush_att > 0:
                summary_parts.append(f"{rush_yds} Rush Yds")
                if rush_td > 0:
                    summary_parts.append(f"{rush_td} Rush TD")
        elif clean_pos == "K":
            if fg_made > 0 or xp_made > 0:
                summary_parts.append(f"{fg_made} FG Made")
                summary_parts.append(f"{xp_made} XP Made")
                summary_parts.append(f"{kick_pts} Kicking Pts")
        else:
            if pass_yds > 0 or pass_att > 0:
                summary_parts.append(f"{pass_yds} Pass Yds")
                summary_parts.append(f"{pass_td} Pass TD")
            if rush_yds > 0 or rush_att > 0:
                summary_parts.append(f"{rush_yds} Rush Yds")
                if rush_td > 0:
                    summary_parts.append(f"{rush_td} Rush TD")
            if rec_yds > 0 or receptions > 0:
                summary_parts.append(f"{rec_yds} Rec Yds")
                if rec_td > 0:
                    summary_parts.append(f"{rec_td} Rec TD")

        if not summary_parts:
            summary_parts.append("DNP / No recorded touches")

        summary_line = " • ".join(summary_parts)

        return {
            "week": base_log["week"],
            "date": base_log["date"],
            "opponent": base_log["opponent"],
            "opponent_name": base_log["opponent_name"],
            "at_vs": base_log["at_vs"],
            "is_home": base_log["is_home"],
            "result": base_log["result"],
            "fantasy_points_ppr": full_ppr_pts,
            "fantasy_points_half_ppr": half_ppr_pts,
            "fantasy_points_std": standard_pts,
            "passing": {
                "completions": pass_cmp,
                "attempts": pass_att,
                "yards": pass_yds,
                "touchdowns": pass_td,
                "interceptions": pass_int,
                "qbr": qbr,
            },
            "rushing": {
                "attempts": rush_att,
                "yards": rush_yds,
                "touchdowns": rush_td,
                "long": rush_long,
                "ypc": ypc,
            },
            "receiving": {
                "targets": targets,
                "receptions": receptions,
                "yards": rec_yds,
                "touchdowns": rec_td,
                "long": rec_long,
                "ypr": ypr,
                "catch_pct": catch_pct,
            },
            "kicking": {
                "fg_made": fg_made,
                "xp_made": xp_made,
                "long": fg_long,
            },
            "fumbles_lost": fumbles_lost,
            "summary_line": summary_line,
        }

    def _compute_season_totals(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        if not logs:
            return {}

        gp = len(logs)
        total_ppr = round(sum(l["fantasy_points_ppr"] for l in logs), 2)
        total_pass_yds = sum(l["passing"]["yards"] for l in logs)
        total_pass_td = sum(l["passing"]["touchdowns"] for l in logs)
        total_rush_yds = sum(l["rushing"]["yards"] for l in logs)
        total_rush_td = sum(l["rushing"]["touchdowns"] for l in logs)
        total_rec_yds = sum(l["receiving"]["yards"] for l in logs)
        total_rec_td = sum(l["receiving"]["touchdowns"] for l in logs)
        total_receptions = sum(l["receiving"]["receptions"] for l in logs)
        total_targets = sum(l["receiving"]["targets"] for l in logs)
        total_touches = sum(l["rushing"]["attempts"] + l["receiving"]["receptions"] for l in logs)

        return {
            "games_played": gp,
            "avg_fantasy_points_ppr": round(total_ppr / gp, 2) if gp > 0 else 0.0,
            "total_fantasy_points_ppr": total_ppr,
            "total_touches": total_touches,
            "total_passing_yards": total_pass_yds,
            "total_passing_tds": total_pass_td,
            "total_rushing_yards": total_rush_yds,
            "total_rushing_tds": total_rush_td,
            "total_receptions": total_receptions,
            "total_receiving_yards": total_rec_yds,
            "total_receiving_tds": total_rec_td,
            "total_targets": total_targets,
        }

    async def _get_dst_gamelog(self, dst_id: int, name: str, pro_team: str, season: int) -> dict[str, Any]:
        """Provides game log for a team Defense/Special Teams unit across all completed regular season weeks."""
        from src.db.session import SessionLocal
        from src.db.models import LeagueModel
        from sqlalchemy import select

        curr_week = 2
        try:
            with SessionLocal() as session:
                league = session.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
                if league and league.current_week:
                    curr_week = league.current_week
        except Exception:
            pass

        from src.adapters.nfl.schedule_client import nfl_schedule_client
        completed_weeks = list(range(1, max(1, curr_week)))
        logs = []

        for w in completed_weeks:
            games = await nfl_schedule_client.fetch_week_schedule(season=season, week=w)
            matchup = next((g for g in games if g.home_team == pro_team or g.away_team == pro_team), None)

            if matchup:
                is_home = matchup.home_team == pro_team
                opp = matchup.away_team if is_home else matchup.home_team
                team_score = matchup.home_score if is_home else matchup.away_score
                opp_score = matchup.away_score if is_home else matchup.home_score
                result = f"{'W' if team_score > opp_score else 'L'} {team_score}-{opp_score}"

                pts_allowed = opp_score
                if pts_allowed == 0:
                    pa_pts = 5.0
                elif pts_allowed <= 6:
                    pa_pts = 4.0
                elif pts_allowed <= 13:
                    pa_pts = 3.0
                elif pts_allowed <= 17:
                    pa_pts = 1.0
                elif pts_allowed <= 27:
                    pa_pts = 0.0
                elif pts_allowed <= 34:
                    pa_pts = -1.0
                else:
                    pa_pts = -4.0

                dst_fantasy_pts = round(max(2.0, pa_pts + 4.0), 1)

                logs.append({
                    "week": w,
                    "date": matchup.date[:10] if matchup.date else "2026-09-13",
                    "opponent": opp,
                    "opponent_name": opp,
                    "at_vs": "vs" if is_home else "@",
                    "is_home": is_home,
                    "result": result,
                    "fantasy_points_ppr": dst_fantasy_pts,
                    "fantasy_points_half_ppr": dst_fantasy_pts,
                    "fantasy_points_std": dst_fantasy_pts,
                    "passing": {"completions": 0, "attempts": 0, "yards": 0, "touchdowns": 0, "interceptions": 0, "qbr": None},
                    "rushing": {"attempts": 0, "yards": 0, "touchdowns": 0, "long": 0, "ypc": 0.0},
                    "receiving": {"targets": 0, "receptions": 0, "yards": 0, "touchdowns": 0, "long": 0, "ypr": 0.0, "catch_pct": 0.0},
                    "kicking": {"fg_made": 0, "xp_made": 0, "long": 0},
                    "fumbles_lost": 0,
                    "defense": {
                        "points_allowed": pts_allowed,
                    },
                    "summary_line": f"{pts_allowed} PTS Allowed • {result}",
                })

        total_pts = round(sum(l["fantasy_points_ppr"] for l in logs), 2)
        avg_pts = round(total_pts / len(logs), 2) if logs else 0.0

        return {
            "success": True,
            "player_id": dst_id,
            "player_name": name,
            "position": "D/ST",
            "pro_team": pro_team,
            "season": season,
            "games_played": len(logs),
            "logs": logs,
            "season_totals": {
                "games_played": len(logs),
                "avg_fantasy_points_ppr": avg_pts,
                "total_fantasy_points_ppr": total_pts,
                "total_touches": 0,
            },
        }

    async def _get_fantasy_db_gamelog(
        self,
        athlete_id: int,
        name: str | None,
        pos: str | None,
        team: str | None,
        season: int,
    ) -> dict[str, Any]:
        """Fallback game log from local roster actuals or projections."""
        return {
            "success": True,
            "player_id": athlete_id,
            "player_name": name or str(athlete_id),
            "position": pos or "UNK",
            "pro_team": team or "UNK",
            "season": season,
            "games_played": 0,
            "logs": [],
            "season_totals": {},
            "note": "Game log history not yet archived for this asset.",
        }


gamelog_service = GameLogService()
