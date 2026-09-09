"""DraftEdge NFL Defense vs Position (DvP) scraper and normalization adapter.

Fetches real-time DraftKings and FanDuel Fantasy Points Allowed (FPA) data by position (QB, RB, WR, TE).
Extracts:
- DK FPA, FD FPA
- vs Positional League Average
- 2025-26 prior-season baseline per-game
- 2026-27 current-season per-game
- Last 4 games trend window
- Position-relevant supporting metrics (pass/rush yards, TDs, INTs, sacks, receptions, targets)
- Trend narrative ("Tightening up lately", "Allowing more lately", etc.)
"""

import json
import logging
from pathlib import Path
from typing import Any
import httpx
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore

logger = logging.getLogger(__name__)

# Full NFL franchise name mapping to standard 2-3 character abbreviations
FULL_TEAM_NAME_MAP: dict[str, str] = {
    "ARIZONA CARDINALS": "ARI",
    "ATLANTA FALCONS": "ATL",
    "BALTIMORE RAVENS": "BAL",
    "BUFFALO BILLS": "BUF",
    "CAROLINA PANTHERS": "CAR",
    "CHICAGO BEARS": "CHI",
    "CINCINNATI BENGALS": "CIN",
    "CLEVELAND BROWNS": "CLE",
    "DALLAS COWBOYS": "DAL",
    "DENVER BRONCOS": "DEN",
    "DETROIT LIONS": "DET",
    "GREEN BAY PACKERS": "GB",
    "HOUSTON TEXANS": "HOU",
    "INDIANAPOLIS COLTS": "IND",
    "JACKSONVILLE JAGUARS": "JAX",
    "KANSAS CITY CHIEFS": "KC",
    "LAS VEGAS RAIDERS": "LV",
    "LOS ANGELES CHARGERS": "LAC",
    "LOS ANGELES RAMS": "LAR",
    "MIAMI DOLPHINS": "MIA",
    "MINNESOTA VIKINGS": "MIN",
    "NEW ENGLAND PATRIOTS": "NE",
    "NEW ORLEANS SAINTS": "NO",
    "NEW YORK GIANTS": "NYG",
    "NEW YORK JETS": "NYJ",
    "PHILADELPHIA EAGLES": "PHI",
    "PITTSBURGH STEELERS": "PIT",
    "SAN FRANCISCO 49ERS": "SF",
    "SEATTLE SEAHAWKS": "SEA",
    "TAMPA BAY BUCCANEERS": "TB",
    "TENNESSEE TITANS": "TEN",
    "WASHINGTON COMMANDERS": "WAS",
}

SEED_FILE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "draftedge_dvp_seed.json"


def get_softness_tier(rank_softness: int) -> tuple[str, str]:
    """Classifies 1-32 DraftEdge softness rank (1 = most points allowed / softest, 32 = toughest).
    
    Returns:
        tuple[str, str]: (tier_code, human_label)
    """
    if rank_softness <= 6:
        return "SMASH", "Elite Smash Matchup"
    elif rank_softness <= 12:
        return "FAVORABLE", "Favorable Matchup"
    elif rank_softness <= 20:
        return "NEUTRAL", "Neutral Matchup"
    elif rank_softness <= 26:
        return "TOUGH", "Tough Defense"
    else:
        return "LOCKDOWN", "Brutal Lockdown"


def parse_clean_float(raw: str | None) -> float | None:
    """Parses numeric string handling +/- prefixes, commas, and em-dashes."""
    if not raw:
        return None
    cleaned = raw.strip().replace("+", "").replace(",", "")
    if cleaned in ("—", "-", "", "N/A", "none", "null"):
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


class DraftEdgeClient:
    """Asynchronous client for fetching and parsing DraftEdge NFL Defense vs Position data."""

    BASE_URL = "https://draftedge.com/nfl/nfl-defense-vs-pos/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_position_dvp(self, position: str) -> list[dict[str, Any]]:
        """Scrapes and parses DvP table for a specific position ('QB', 'RB', 'WR', 'TE')."""
        pos_lower = position.lower().strip()
        url = f"{self.BASE_URL}?pos={pos_lower}"
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                records = self._parse_html_table(response.text, position.upper(), source_url=url)
                if len(records) >= 30:
                    return records
                logger.warning("Scraped fewer than 30 teams for %s from DraftEdge (%d); using seed fallback", position, len(records))
        except Exception as e:
            logger.error("Failed to scrape DraftEdge for %s: %s; using bundled seed fallback", position, e)

        return self._load_seed_for_position(position.upper())

    def _parse_html_table(self, html: str, position: str, source_url: str) -> list[dict[str, Any]]:
        """Parses HTML table into validated dictionaries."""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        tbody = table.find("tbody")
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        results: list[dict[str, Any]] = []

        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 13:
                continue

            td_texts = [td.get_text(strip=True) for td in tds]
            try:
                rank_softness = int(td_texts[0])
            except ValueError:
                continue

            team_name = td_texts[1]
            team_label = tds[1].find("span", class_="dvp-team-label")
            if team_label:
                team_name = team_label.get_text(strip=True)

            pro_team = FULL_TEAM_NAME_MAP.get(team_name.upper())
            if not pro_team:
                # Fallback: check logo image src filename, e.g. /images/logos/nfl/dal.png
                img = tds[1].find("img")
                if img and img.get("src"):
                    src = img["src"]
                    slug = src.split("/")[-1].replace(".png", "").replace(".svg", "").upper()
                    pro_team = FULL_TEAM_NAME_MAP.get(slug, slug)
            pro_team = pro_team or "UNK"

            dk_fpa = parse_clean_float(td_texts[2]) or 0.0
            fd_fpa = parse_clean_float(td_texts[3])
            vs_avg = parse_clean_float(td_texts[4]) or 0.0
            prior_season_fpa = parse_clean_float(td_texts[5]) or 0.0
            current_season_fpa = parse_clean_float(td_texts[6])
            last4_fpa = parse_clean_float(td_texts[7])
            trend = td_texts[-1] if len(td_texts) >= 14 else "Stable"

            # Position-specific supporting columns
            supporting_stats: dict[str, float] = {}
            if position == "QB":
                supporting_stats = {
                    "pass_yds": parse_clean_float(td_texts[8]) or 0.0,
                    "pass_td": parse_clean_float(td_texts[9]) or 0.0,
                    "int": parse_clean_float(td_texts[10]) or 0.0,
                    "sacks": parse_clean_float(td_texts[11]) or 0.0,
                    "qb_rush_yds": parse_clean_float(td_texts[12]) or 0.0,
                }
            elif position == "RB":
                supporting_stats = {
                    "rush_yds": parse_clean_float(td_texts[8]) or 0.0,
                    "rush_td": parse_clean_float(td_texts[9]) or 0.0,
                    "targets": parse_clean_float(td_texts[10]) or 0.0,
                    "rec": parse_clean_float(td_texts[11]) or 0.0,
                    "rec_yds": parse_clean_float(td_texts[12]) or 0.0,
                }
            elif position in ("WR", "TE"):
                supporting_stats = {
                    "targets": parse_clean_float(td_texts[8]) or 0.0,
                    "rec": parse_clean_float(td_texts[9]) or 0.0,
                    "rec_yds": parse_clean_float(td_texts[10]) or 0.0,
                    "rec_td": parse_clean_float(td_texts[11]) or 0.0,
                    "rec_20_plus": parse_clean_float(td_texts[12]) or 0.0,
                }

            tier, tier_label = get_softness_tier(rank_softness)
            rank_defense = 33 - rank_softness  # Invert so 1=toughest, 32=softest

            # Week 1 baseline logic: if current season per-game is not yet populated, flag as baseline
            is_baseline = current_season_fpa is None or current_season_fpa == 0.0

            results.append({
                "rank_softness": rank_softness,
                "rank_defense": rank_defense,
                "team_name": team_name,
                "pro_team": pro_team,
                "position": position,
                "dk_fpa": dk_fpa,
                "fd_fpa": fd_fpa,
                "vs_avg": vs_avg,
                "prior_season_fpa": prior_season_fpa,
                "current_season_fpa": current_season_fpa,
                "last4_fpa": last4_fpa,
                "trend": trend,
                "tier": tier,
                "tier_label": tier_label,
                "supporting_stats": supporting_stats,
                "is_baseline": is_baseline,
                "sample_games_current": 0 if is_baseline else 1,
                "source": "DraftEdge",
                "source_url": source_url,
            })

        return results

    def _load_seed_for_position(self, position: str) -> list[dict[str, Any]]:
        """Loads bundled snapshot data for offline operation or scraper failure fallback."""
        if not SEED_FILE_PATH.exists():
            logger.error("Seed file not found at %s", SEED_FILE_PATH)
            return []
        try:
            with open(SEED_FILE_PATH, "r", encoding="utf-8") as f:
                seed_data = json.load(f)
            raw_list = seed_data.get(position, [])
            out = []
            for item in raw_list:
                tier, tier_label = get_softness_tier(item["rank_softness"])
                rank_def = 33 - item["rank_softness"]
                out.append({
                    **item,
                    "position": position,
                    "rank_defense": rank_def,
                    "tier": tier,
                    "tier_label": tier_label,
                    "is_baseline": item.get("current_season_fpa") is None,
                    "sample_games_current": 0,
                    "source": "DraftEdge (Seed)",
                    "source_url": f"{self.BASE_URL}?pos={position.lower()}",
                })
            return out
        except Exception as e:
            logger.error("Error reading seed file: %s", e)
            return []

    async def fetch_all_positions(self) -> dict[str, list[dict[str, Any]]]:
        """Fetches all 4 positions concurrently."""
        positions = ["QB", "RB", "WR", "TE"]
        results: dict[str, list[dict[str, Any]]] = {}
        for pos in positions:
            results[pos] = await self.fetch_position_dvp(pos)
        return results


draftedge_client = DraftEdgeClient()
