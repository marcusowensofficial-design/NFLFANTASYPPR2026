"""Sleeper REST API Client for NFL Player Projections.

Fetches weekly player projections powered by RotoWire from Sleeper's public API.
Provides PPR point totals, floor/ceiling indicators, and itemized box score stats.
"""

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Any
import httpx

from src.adapters.fantasypros.client import normalize_player_name, normalize_team

logger = logging.getLogger(__name__)

SLEEPER_BASE_URL = "https://api.sleeper.app/projections/nfl"

# Map defense team names to standard abbreviations
DEFENSE_NAME_TO_TEAM: dict[str, str] = {
    "arizona cardinals": "ARI",
    "atlanta falcons": "ATL",
    "baltimore ravens": "BAL",
    "buffalo bills": "BUF",
    "carolina panthers": "CAR",
    "chicago bears": "CHI",
    "cincinnati bengals": "CIN",
    "cleveland browns": "CLE",
    "dallas cowboys": "DAL",
    "denver broncos": "DEN",
    "detroit lions": "DET",
    "green bay packers": "GB",
    "houston texans": "HOU",
    "indianapolis colts": "IND",
    "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC",
    "las vegas raiders": "LV",
    "los angeles chargers": "LAC",
    "los angeles rams": "LAR",
    "miami dolphins": "MIA",
    "minnesota vikings": "MIN",
    "new england patriots": "NE",
    "new orleans saints": "NO",
    "new york giants": "NYG",
    "new york jets": "NYJ",
    "philadelphia eagles": "PHI",
    "pittsburgh steelers": "PIT",
    "san francisco 49ers": "SF",
    "seattle seahawks": "SEA",
    "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN",
    "washington commanders": "WAS",
}


def normalize_sleeper_stats(stats: dict[str, Any]) -> dict[str, float]:
    """Normalize Sleeper / RotoWire stats to unified itemized schema."""
    if not stats or not isinstance(stats, dict):
        return {}

    out: dict[str, float] = {}
    for k, v in stats.items():
        try:
            out[k] = float(v)
        except (ValueError, TypeError):
            continue

    # Map unified fields
    pass_att = out.get("pass_att", 0.0)
    pass_cmp = out.get("pass_cmp", 0.0)
    pass_yd = out.get("pass_yd", 0.0)
    pass_td = out.get("pass_td", 0.0)
    pass_int = out.get("pass_int", 0.0)

    rush_att = out.get("rush_att", 0.0)
    rush_yd = out.get("rush_yd", 0.0)
    rush_td = out.get("rush_td", 0.0)

    rec_tgt = out.get("rec_tgt", 0.0)
    rec = out.get("rec", 0.0)
    rec_yd = out.get("rec_yd", 0.0)
    rec_td = out.get("rec_td", 0.0)

    fgm = out.get("fgm", 0.0)
    fga = out.get("fga", fgm)
    xpm = out.get("xpm", 0.0)

    sack = out.get("sack", 0.0)
    pts_allow = out.get("pts_allow", 21.0)
    def_int = out.get("int", 0.0)
    fum_rec = out.get("fum_rec", 0.0)
    def_td = out.get("def_td", 0.0)

    pts_ppr = out.get("pts_ppr", 0.0)

    unified: dict[str, float] = {
        **out,
        "pass_att": pass_att,
        "pass_cmp": pass_cmp,
        "pass_yd": pass_yd,
        "pass_yds": pass_yd,
        "pass_td": pass_td,
        "pass_tds": pass_td,
        "pass_int": pass_int,
        "pass_ints": pass_int,
        "rush_att": rush_att,
        "rush_yd": rush_yd,
        "rush_yds": rush_yd,
        "rush_td": rush_td,
        "rush_tds": rush_td,
        "targets": rec_tgt,
        "rec_tgt": rec_tgt,
        "receptions": rec,
        "rec_rec": rec,
        "rec": rec,
        "rec_yd": rec_yd,
        "rec_yds": rec_yd,
        "rec_td": rec_td,
        "rec_tds": rec_td,
        "fg_made": fgm,
        "fg": fgm,
        "fgm": fgm,
        "fg_att": fga,
        "fga": fga,
        "pat_made": xpm,
        "xpt": xpm,
        "xpm": xpm,
        "sacks": sack,
        "def_sack": sack,
        "sack": sack,
        "turnovers": def_int + fum_rec,
        "def_int": def_int,
        "def_fr": fum_rec,
        "def_td": def_td,
        "pts_allowed": pts_allow,
        "def_pa": pts_allow,
        "calculated_ppr": pts_ppr,
        "points_ppr": pts_ppr,
    }
    return unified


class SleeperClient:
    """Async client for fetching Sleeper NFL projections."""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self._cache: dict[str, Any] = {}
        self._cache_time: float = 0.0
        self._cache_ttl: float = 1800.0  # 30 minute cache

    async def fetch_projections(
        self,
        season: int = 2024,
        week: int = 1,
        season_type: str = "regular",
    ) -> list[dict[str, Any]]:
        """Fetch weekly NFL player projections from Sleeper API.

        Returns raw projection objects with player metadata and RotoWire stats.
        """
        cache_key = f"{season}_{week}_{season_type}"
        now = datetime.now(timezone.utc).timestamp()
        if cache_key in self._cache and (now - self._cache_time) < self._cache_ttl:
            logger.info("Serving Sleeper projections from memory cache for %s", cache_key)
            return self._cache[cache_key]

        url = f"{SLEEPER_BASE_URL}/{season}/{week}?season_type={season_type}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        logger.info("Fetching Sleeper / RotoWire weekly projections from: %s", url)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                if isinstance(data, list):
                    logger.info("Successfully fetched %d Sleeper player projections", len(data))
                    self._cache[cache_key] = data
                    self._cache_time = now
                    return data
                logger.warning("Unexpected Sleeper response format: %s", type(data))
                return []
        except httpx.HTTPStatusError as e:
            logger.error("Sleeper API HTTP error %d: %s", e.response.status_code, e)
            return []
        except Exception as e:
            logger.error("Failed to fetch Sleeper projections: %s", e)
            return []


sleeper_client = SleeperClient()
