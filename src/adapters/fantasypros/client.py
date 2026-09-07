"""FantasyPros Public REST API Client.

Provides high-efficiency access to Expert Consensus Rankings (ECR), Standard Deviation,
Tiers, Projections, and live Injury feeds for 8-man ESPN PPR fantasy football strategy.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

# Team abbreviation normalization map
TEAM_MAP: dict[str, str] = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "JAC": "JAX",
    "LA": "LAR",
    "SD": "LAC",
    "WSH": "WAS",
}


def normalize_team(team: str | None) -> str:
    if not team:
        return "FA"
    cleaned = team.strip().upper()
    return TEAM_MAP.get(cleaned, cleaned)


def normalize_player_name(name: str | None) -> str:
    if not name:
        return ""
    # Strip suffixes like Jr., Sr., III, II, IV, and punctuation
    cleaned = name.strip().lower()
    cleaned = re.sub(r"\b(jr\.?|sr\.?|iii|ii|iv|v)\b", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_fp_stats(stats: dict[str, Any]) -> dict[str, float]:
    """Normalize FantasyPros raw stat keys into standardized schema with both singular and plural keys."""
    if not stats or not isinstance(stats, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in stats.items():
        try:
            out[k] = float(v)
        except (ValueError, TypeError):
            continue

    # Map synonyms & dual-key consistency
    # Rush TDs
    if "rush_tds" in out and "rush_td" not in out:
        out["rush_td"] = out["rush_tds"]
    elif "rush_td" in out and "rush_tds" not in out:
        out["rush_tds"] = out["rush_td"]

    # Rec TDs
    if "rec_tds" in out and "rec_td" not in out:
        out["rec_td"] = out["rec_tds"]
    elif "rec_td" in out and "rec_tds" not in out:
        out["rec_tds"] = out["rec_td"]

    # Pass TDs
    if "pass_tds" in out and "pass_td" not in out:
        out["pass_td"] = out["pass_tds"]
    elif "pass_td" in out and "pass_tds" not in out:
        out["pass_tds"] = out["pass_td"]

    # Pass INTs
    if "pass_ints" in out and "pass_int" not in out:
        out["pass_int"] = out["pass_ints"]
    elif "pass_int" in out and "pass_ints" not in out:
        out["pass_ints"] = out["pass_int"]

    # Receptions
    if "rec_rec" in out and "receptions" not in out:
        out["receptions"] = out["rec_rec"]
    elif "receptions" in out and "rec_rec" not in out:
        out["rec_rec"] = out["receptions"]

    # Targets (synthesize from receptions assuming ~72% catch rate if missing)
    if "targets" not in out:
        rec = out.get("receptions", out.get("rec_rec", 0.0))
        if rec > 0:
            out["targets"] = round(rec / 0.72, 1)
        else:
            out["targets"] = 0.0

    return out


class FantasyProsClient:
    """Client for interacting with FantasyPros Public v2 REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 12.0,
    ):
        self.api_key = settings.fantasypros_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.fantasypros_base_url).rstrip("/")
        self.timeout = timeout


        # In-memory cache: key -> (timestamp, data)
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_key_lock(self, key: str) -> asyncio.Lock:
        """Retrieve or create an asyncio.Lock for a specific cache key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _get_cached(self, key: str, ttl_seconds: int = 1800) -> Any | None:
        """Retrieve cached item if within TTL."""
        if key in self._cache:
            ts, data = self._cache[key]
            if (datetime.now(timezone.utc) - ts).total_seconds() < ttl_seconds:
                return data
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        self._cache[key] = (datetime.now(timezone.utc), data)

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "FantasyDFS-Assistant/1.0",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key.strip()
        return headers

    async def _fetch_web_rankings(
        self, page_name: str, week: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch consensus dataset directly from official FantasyPros web sheets with optional week parameter."""
        url = f"https://www.fantasypros.com/nfl/rankings/{page_name}.php"
        if week is not None:
            url += f"?week={week}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    m = re.search(r"var ecrData\s*=\s*(\{.*?\});", resp.text)
                    if m:
                        data = json.loads(m.group(1))
                        return data.get("players", [])
        except Exception as e:
            logger.debug("FantasyPros web fetch for %s (week %s) fell back: %s", page_name, week, e)
        return []

    async def _fetch_web_projections(
        self, position: str, week: int = 1, scoring: str = "PPR"
    ) -> list[dict[str, Any]]:
        """Fetch weekly statistical projections from official FantasyPros web projections table."""
        pos_clean = position.lower().replace("dst", "dst")
        scoring_clean = scoring.upper()
        url = f"https://www.fantasypros.com/nfl/projections/{pos_clean}.php?week={week}&scoring={scoring_clean}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            from bs4 import BeautifulSoup
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    table = soup.find("table", id="data")
                    if not table or not table.find("tbody"):
                        return []
                    rows = table.find("tbody").find_all("tr")
                    projections = []
                    for r in rows:
                        tds = r.find_all("td")
                        if not tds or len(tds) < 3:
                            continue
                        player_link = r.find("a", class_="player-name")
                        p_name = player_link.get_text(strip=True) if player_link else tds[0].get_text(strip=True)
                        full_cell = tds[0].get_text(strip=True)
                        team_match = re.search(r"([A-Z]{2,3})$", full_cell)
                        team = team_match.group(1) if team_match else ""
                        if team and p_name.endswith(team):
                            p_name = p_name[:-len(team)].strip()

                        fpts_str = tds[-1].get_text(strip=True).replace(",", "")
                        try:
                            fpts = float(fpts_str)
                        except ValueError:
                            fpts = 0.0

                        # Map itemized cells by position
                        cell_texts = [td.get_text(strip=True) for td in tds]
                        itemized_stats: dict[str, float] = {}
                        pos_u = position.upper()
                        if pos_u == "QB" and len(cell_texts) >= 11:
                            # ['Player', 'ATT', 'CMP', 'YDS', 'TDS', 'INTS', 'ATT', 'YDS', 'TDS', 'FL', 'FPTS']
                            try:
                                itemized_stats = {
                                    "pass_att": float(cell_texts[1]),
                                    "pass_cmp": float(cell_texts[2]),
                                    "pass_yds": float(cell_texts[3]),
                                    "pass_tds": float(cell_texts[4]),
                                    "pass_ints": float(cell_texts[5]),
                                    "rush_att": float(cell_texts[6]),
                                    "rush_yds": float(cell_texts[7]),
                                    "rush_tds": float(cell_texts[8]),
                                    "fumbles": float(cell_texts[9]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass
                        elif pos_u == "RB" and len(cell_texts) >= 9:
                            # ['Player', 'ATT', 'YDS', 'TDS', 'REC', 'YDS', 'TDS', 'FL', 'FPTS']
                            try:
                                itemized_stats = {
                                    "rush_att": float(cell_texts[1]),
                                    "rush_yds": float(cell_texts[2]),
                                    "rush_tds": float(cell_texts[3]),
                                    "rec_rec": float(cell_texts[4]),
                                    "rec_yds": float(cell_texts[5]),
                                    "rec_tds": float(cell_texts[6]),
                                    "fumbles": float(cell_texts[7]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass
                        elif pos_u == "WR" and len(cell_texts) >= 9:
                            # ['Player', 'REC', 'YDS', 'TDS', 'ATT', 'YDS', 'TDS', 'FL', 'FPTS']
                            try:
                                itemized_stats = {
                                    "rec_rec": float(cell_texts[1]),
                                    "rec_yds": float(cell_texts[2]),
                                    "rec_tds": float(cell_texts[3]),
                                    "rush_att": float(cell_texts[4]),
                                    "rush_yds": float(cell_texts[5]),
                                    "rush_tds": float(cell_texts[6]),
                                    "fumbles": float(cell_texts[7]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass
                        elif pos_u == "TE" and len(cell_texts) >= 6:
                            # ['Player', 'REC', 'YDS', 'TDS', 'FL', 'FPTS']
                            try:
                                itemized_stats = {
                                    "rec_rec": float(cell_texts[1]),
                                    "rec_yds": float(cell_texts[2]),
                                    "rec_tds": float(cell_texts[3]),
                                    "fumbles": float(cell_texts[4]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass
                        elif pos_u == "K" and len(cell_texts) >= 5:
                            # ['Player', 'FG', 'FGA', 'XPT', 'FPTS']
                            try:
                                itemized_stats = {
                                    "fg": float(cell_texts[1]),
                                    "fga": float(cell_texts[2]),
                                    "xpt": float(cell_texts[3]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass
                        elif pos_u == "DST" and len(cell_texts) >= 10:
                            # ['Player', 'SACK', 'INT', 'FR', 'FF', 'TD', 'SAFETY', 'PA', 'YDS AGN', 'FPTS']
                            try:
                                itemized_stats = {
                                    "def_sack": float(cell_texts[1]),
                                    "def_int": float(cell_texts[2]),
                                    "def_fr": float(cell_texts[3]),
                                    "def_ff": float(cell_texts[4]),
                                    "def_td": float(cell_texts[5]),
                                    "def_safety": float(cell_texts[6]),
                                    "def_pa": float(cell_texts[7]),
                                    "def_tyda": float(cell_texts[8]),
                                    "points_ppr": fpts,
                                }
                            except ValueError:
                                pass

                        projections.append({
                            "player_name": p_name,
                            "position": pos_u,
                            "team": normalize_team(team),
                            "projected_points": fpts,
                            "scoring": scoring_clean,
                            "stats": normalize_fp_stats(itemized_stats),
                        })
                    return projections
        except Exception as e:
            logger.debug("FantasyPros web projections fetch for %s (week %s) failed: %s", position, week, e)
        return []

    async def fetch_consensus_rankings(
        self,
        season: int = 2026,
        week: int = 1,
        position: str = "FLX",
        scoring: str = "PPR",
    ) -> list[dict[str, Any]]:
        """Fetch weekly Expert Consensus Rankings (ECR) for a position or Top 100 overall with strict PPR support."""
        pos_clean = position.upper().replace("D/ST", "DST")
        scoring_clean = scoring.upper()
        cache_key = f"ecr_{season}_w{week}_{pos_clean}_{scoring_clean}"
        cached = self._get_cached(cache_key, ttl_seconds=1800)
        if cached is not None:
            return cached

        async with self._get_key_lock(cache_key):
            cached = self._get_cached(cache_key, ttl_seconds=1800)
            if cached is not None:
                return cached

            # 1. TOP 100 / OVERALL Rankings Handler
            if pos_clean in ("TOP100", "OVERALL", "OVR"):
                cheatsheet_page = (
                    "ppr-cheatsheets"
                    if scoring_clean == "PPR"
                    else "half-point-ppr-cheatsheets"
                    if scoring_clean == "HALF"
                    else "consensus-cheatsheets"
                )
                raw_players = await self._fetch_web_rankings(cheatsheet_page, week=week)
                if raw_players:
                    top_100 = raw_players[:100]

                    # Enrich top 100 with positional start_sit_grades & opponents (strictly PPR if PPR selected)
                    pos_enrich_pages = (
                        ["qb", "ppr-rb", "ppr-wr", "ppr-te", "k", "dst"]
                        if scoring_clean == "PPR"
                        else ["qb", "half-point-ppr-rb", "half-point-ppr-wr", "half-point-ppr-te", "k", "dst"]
                        if scoring_clean == "HALF"
                        else ["qb", "rb", "wr", "te", "k", "dst"]
                    )
                    pos_tasks = [
                        self._fetch_web_rankings(p, week=week)
                        for p in pos_enrich_pages
                    ]
                    pos_results = await asyncio.gather(*pos_tasks, return_exceptions=True)
                    pos_lookup: dict[str, dict[str, Any]] = {}
                    for p_list in pos_results:
                        if isinstance(p_list, list):
                            for p in p_list:
                                norm = normalize_player_name(p.get("player_name"))
                                if norm:
                                    pos_lookup[norm] = p

                    for p in top_100:
                        norm = normalize_player_name(p.get("player_name"))
                        matched = pos_lookup.get(norm)
                        if matched:
                            if not p.get("start_sit_grade") and matched.get("start_sit_grade"):
                                p["start_sit_grade"] = matched.get("start_sit_grade")
                            if not p.get("player_opponent") and matched.get("player_opponent"):
                                p["player_opponent"] = matched.get("player_opponent")
                            if not p.get("r2p_pts") and matched.get("r2p_pts"):
                                p["r2p_pts"] = matched.get("r2p_pts")

                    self._set_cached(cache_key, top_100)
                    return top_100

            # 2. Positional Web Sheet Handler (Full List of 30-186+ Players with Grades)
            # CRITICAL: If PPR, route RB, WR, TE, FLX to their respective ppr-*.php pages!
            if scoring_clean == "PPR":
                web_page_map = {
                    "QB": "qb",
                    "RB": "ppr-rb",
                    "WR": "ppr-wr",
                    "TE": "ppr-te",
                    "FLX": "ppr-flex",
                    "FLEX": "ppr-flex",
                    "K": "k",
                    "DST": "dst",
                }
            elif scoring_clean == "HALF":
                web_page_map = {
                    "QB": "qb",
                    "RB": "half-point-ppr-rb",
                    "WR": "half-point-ppr-wr",
                    "TE": "half-point-ppr-te",
                    "FLX": "half-point-ppr-flex",
                    "FLEX": "half-point-ppr-flex",
                    "K": "k",
                    "DST": "dst",
                }
            else:
                web_page_map = {
                    "QB": "qb",
                    "RB": "rb",
                    "WR": "wr",
                    "TE": "te",
                    "FLX": "flex",
                    "FLEX": "flex",
                    "K": "k",
                    "DST": "dst",
                }

            if pos_clean in web_page_map:
                web_players = await self._fetch_web_rankings(web_page_map[pos_clean], week=week)
                if web_players and len(web_players) > 0:
                    self._set_cached(cache_key, web_players)
                    return web_players

            # 3. REST API Fallback
            if not self.is_configured:
                return []

            url = f"{self.base_url}/nfl/{season}/consensus-rankings"
            params = {
                "position": pos_clean if pos_clean != "TOP100" else "FLX",
                "scoring": scoring_clean,
                "week": str(week),
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, params=params, headers=self._get_headers())
                    if resp.status_code == 200:
                        data = resp.json()
                        players = data.get("players", [])
                        self._set_cached(cache_key, players)
                        return players
                    elif resp.status_code == 429:
                        logger.warning("FantasyPros rate limit exceeded (429).")
                        return []
                    else:
                        logger.error(
                            "FantasyPros ECR fetch failed: %d - %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        return []
            except Exception as e:
                logger.error("Error connecting to FantasyPros API for ECR: %s", e)
                return []

    async def fetch_top_100(
        self,
        season: int = 2026,
        week: int = 1,
        scoring: str = "PPR",
    ) -> list[dict[str, Any]]:
        """Fetch the official FantasyPros Top 100 overall consensus rankings with matchup grades."""
        return await self.fetch_consensus_rankings(
            season=season, week=week, position="TOP100", scoring=scoring
        )

    async def fetch_all_consensus_rankings(
        self,
        season: int = 2026,
        week: int = 1,
        scoring: str = "PPR",
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch consensus rankings across TOP100, QB, RB, WR, TE, FLX, K, and DST concurrently."""
        positions = ["TOP100", "QB", "RB", "WR", "TE", "FLX", "K", "DST"]
        results = await asyncio.gather(
            *(
                self.fetch_consensus_rankings(
                    season=season,
                    week=week,
                    position=pos,
                    scoring=scoring,
                )
                for pos in positions
            ),
            return_exceptions=True,
        )

        all_ecr: dict[str, list[dict[str, Any]]] = {}
        for pos, res in zip(positions, results):
            if isinstance(res, list):
                all_ecr[pos] = res
            else:
                logger.error("Error fetching ECR for %s: %s", pos, res)
                all_ecr[pos] = []

        return all_ecr

    async def fetch_projections(
        self,
        season: int = 2026,
        week: int = 1,
        position: str = "FLX",
        scoring: str = "PPR",
    ) -> list[dict[str, Any]]:
        """Fetch weekly statistical projections for a position with full PPR support and web table fallback."""
        pos_clean = position.upper().replace("D/ST", "DST")
        scoring_clean = scoring.upper()
        cache_key = f"proj_{season}_w{week}_{pos_clean}_{scoring_clean}"
        cached = self._get_cached(cache_key, ttl_seconds=1800)
        if cached is not None:
            return cached

        async with self._get_key_lock(cache_key):
            cached = self._get_cached(cache_key, ttl_seconds=1800)
            if cached is not None:
                return cached

            # 1. First attempt: Official REST API
            api_players: list[dict[str, Any]] = []
            if self.is_configured:
                url = f"{self.base_url}/nfl/{season}/projections"
                params = {
                    "position": pos_clean,
                    "week": str(week),
                }
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.get(url, params=params, headers=self._get_headers())
                        if resp.status_code == 200:
                            data = resp.json()
                            raw_list = data.get("players", [])
                            for p in raw_list:
                                stats = p.get("stats", {})
                                if scoring_clean == "PPR":
                                    pts = stats.get("points_ppr", stats.get("points", 0.0))
                                elif scoring_clean == "HALF":
                                    pts = stats.get("points_half", stats.get("points", 0.0))
                                else:
                                    pts = stats.get("points", 0.0)

                                norm_stats = normalize_fp_stats(stats)
                                if "points_ppr" not in norm_stats and pts is not None:
                                    norm_stats["points_ppr"] = float(pts)

                                api_players.append({
                                    "player_id": p.get("fpid"),
                                    "player_name": p.get("name"),
                                    "position": p.get("position_id", pos_clean),
                                    "team": normalize_team(p.get("team_id")),
                                    "projected_points": float(pts) if pts is not None else 0.0,
                                    "scoring": scoring_clean,
                                    "stats": norm_stats,
                                })
                except Exception as e:
                    logger.debug("FantasyPros REST API projections fetch failed: %s", e)

            # 2. Second attempt: Official Web Projections Table
            web_players = await self._fetch_web_projections(pos_clean, week=week, scoring=scoring_clean)

            # Merge: Start with API players, supplement or replace with web players if richer
            merged: list[dict[str, Any]] = []
            seen_names = set()
            for p in api_players:
                norm = normalize_player_name(p.get("player_name"))
                if norm:
                    seen_names.add(norm)
                    merged.append(p)

            for wp in web_players:
                norm = normalize_player_name(wp.get("player_name"))
                if norm and norm not in seen_names:
                    seen_names.add(norm)
                    merged.append(wp)
                elif norm in seen_names:
                    # Enrich existing API player with any extra web stats if needed
                    pass

            if merged:
                self._set_cached(cache_key, merged)
                return merged

            # 3. Third attempt: Derive projections from ECR consensus table r2p_pts
            ecr_list = await self.fetch_consensus_rankings(
                season=season, week=week, position=pos_clean, scoring=scoring_clean
            )
            derived = []
            for p in ecr_list:
                r2p = p.get("r2p_pts")
                if r2p is not None:
                    try:
                        pts = float(r2p)
                    except ValueError:
                        pts = 0.0
                    derived.append({
                        "player_id": p.get("player_id"),
                        "player_name": p.get("player_name") or p.get("name"),
                        "position": p.get("player_position_id") or pos_clean,
                        "team": normalize_team(p.get("player_team_id") or p.get("team_id")),
                        "projected_points": pts,
                        "scoring": scoring_clean,
                        "stats": {"points_ppr": pts, "r2p_pts": pts},
                    })

            if derived:
                self._set_cached(cache_key, derived)
                return derived

            return []

    async def fetch_all_projections(
        self,
        season: int = 2026,
        week: int = 1,
        scoring: str = "PPR",
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch weekly projections across QB, RB, WR, TE, K, and DST concurrently."""
        positions = ["QB", "RB", "WR", "TE", "K", "DST"]
        results = await asyncio.gather(
            *(
                self.fetch_projections(
                    season=season,
                    week=week,
                    position=pos,
                    scoring=scoring,
                )
                for pos in positions
            ),
            return_exceptions=True,
        )
        all_projs: dict[str, list[dict[str, Any]]] = {}
        for pos, res in zip(positions, results):
            if isinstance(res, list):
                all_projs[pos] = res
            else:
                logger.error("Error fetching projections for %s: %s", pos, res)
                all_projs[pos] = []
        return all_projs

    async def fetch_injuries(self, team_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch live injury reports, optionally filtered by team."""
        if not self.is_configured:
            return []

        cache_key = f"injuries_{team_id or 'ALL'}"
        cached = self._get_cached(cache_key, ttl_seconds=900)
        if cached is not None:
            return cached

        url = f"{self.base_url}/nfl/injuries"
        params: dict[str, str] = {}
        if team_id:
            params["team_id"] = normalize_team(team_id)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    injuries = data.get("injuries", [])
                    self._set_cached(cache_key, injuries)
                    return injuries
                return []
        except Exception as e:
            logger.error("Error fetching FantasyPros injuries: %s", e)
            return []

    async def get_player_intelligence(
        self,
        full_name: str,
        position: str,
        pro_team: str,
        season: int = 2026,
        week: int = 1,
    ) -> dict[str, Any] | None:
        """Look up consolidated FantasyPros intelligence for an individual player."""
        pos_clean = position.upper().replace("D/ST", "DST")
        norm_input_name = normalize_player_name(full_name)
        norm_input_team = normalize_team(pro_team)

        # Fetch position rankings and FLX rankings
        ecr_list = await self.fetch_consensus_rankings(
            season=season,
            week=week,
            position=pos_clean,
            scoring="PPR",
        )

        matched_p = None
        for p in ecr_list:
            p_name = p.get("player_name") or p.get("name") or ""
            p_team = normalize_team(p.get("player_team_id") or p.get("team_id"))

            if normalize_player_name(p_name) == norm_input_name:
                matched_p = p
                break
            # D/ST matching (e.g. "Jacksonville Jaguars" matches "Jaguars D/ST")
            if pos_clean == "DST":
                if norm_input_team and p_team == norm_input_team:
                    matched_p = p
                    break

        if not matched_p and pos_clean in ("RB", "WR", "TE"):
            # Check FLX consensus
            flx_list = await self.fetch_consensus_rankings(
                season=season,
                week=week,
                position="FLX",
                scoring="PPR",
            )
            for p in flx_list:
                p_name = p.get("player_name") or p.get("name") or ""
                if normalize_player_name(p_name) == norm_input_name:
                    matched_p = p
                    break

        if not matched_p:
            return None

        # Build intelligence package
        rank_ecr = matched_p.get("rank_ecr")
        rank_ave = matched_p.get("rank_ave")
        rank_std = matched_p.get("rank_std")
        rank_min = matched_p.get("rank_min")
        rank_max = matched_p.get("rank_max")
        tier = matched_p.get("tier")
        pos_rank = matched_p.get("pos_rank")
        grade = matched_p.get("start_sit_grade")
        r2p = matched_p.get("r2p_pts")

        return {
            "rank_ecr": int(rank_ecr) if rank_ecr is not None else None,
            "rank_ave": float(rank_ave) if rank_ave is not None else None,
            "rank_std": float(rank_std) if rank_std is not None else None,
            "rank_min": int(rank_min) if rank_min is not None else None,
            "rank_max": int(rank_max) if rank_max is not None else None,
            "tier": int(tier) if tier is not None else None,
            "pos_rank": pos_rank,
            "start_sit_grade": grade,
            "r2p_pts": float(r2p) if r2p is not None else None,
            "opponent": matched_p.get("player_opponent"),
            "bye_week": matched_p.get("player_bye_week"),
            "owned_espn": matched_p.get("player_owned_espn"),
        }


fantasypros_client = FantasyProsClient()
