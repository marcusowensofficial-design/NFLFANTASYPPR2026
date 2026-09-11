"""Official Live 2026-2027 NFL Depth Charts Client using ESPN Operations API.

Provides real-time access to official post-preseason 53-man depth charts across all 32
NFL franchises, tracking designated starters (Rank 1), slot receivers, secondary cornerbacks,
and backfield hierarchies for year-long PPR strategy.
"""

import asyncio
import logging
import re
import time
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ESPN_DEPTHCHART_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team}/depthcharts"

ALL_NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH"
]


class DepthChartAthlete(BaseModel):
    athlete_id: int
    display_name: str
    short_name: str
    rank: int  # 1 = Starter, 2 = Backup, etc.
    position_slot: str  # e.g., "qb", "rb", "wr1", "wr2", "wr3", "te", "lcb", "rcb", "nb"
    injuries: list[dict[str, Any]] = Field(default_factory=list)


class TeamDepthChart(BaseModel):
    pro_team: str
    last_updated: float
    offense: dict[str, list[DepthChartAthlete]] = Field(default_factory=dict)
    defense: dict[str, list[DepthChartAthlete]] = Field(default_factory=dict)
    special_teams: dict[str, list[DepthChartAthlete]] = Field(default_factory=dict)

    def get_starter(self, slot: str) -> DepthChartAthlete | None:
        """Returns the Rank 1 starter for a specific depth chart slot."""
        slot_clean = slot.lower().strip()
        athletes = self.offense.get(slot_clean) or self.defense.get(slot_clean) or self.special_teams.get(slot_clean)
        if athletes:
            return next((a for a in athletes if a.rank == 1), athletes[0])
        return None

    def get_player_status(self, player_name: str, position: str) -> dict[str, Any]:
        """Finds where a player sits in the team's depth chart."""
        norm_target = re.sub(r"[^\w\s]", "", player_name.lower()).strip()
        pos_clean = position.upper().strip()

        # Search relevant position pools
        search_pools = []
        if pos_clean in ("QB", "RB", "FB", "WR", "TE"):
            search_pools.append(self.offense)
        elif pos_clean in ("D/ST", "DST", "CB", "S", "LB", "DE", "DT"):
            search_pools.append(self.defense)
        elif pos_clean in ("K", "PK", "P"):
            search_pools.append(self.special_teams)
        else:
            search_pools.extend([self.offense, self.defense, self.special_teams])

        for pool in search_pools:
            for slot, athletes in pool.items():
                for ath in athletes:
                    norm_ath = re.sub(r"[^\w\s]", "", ath.display_name.lower()).strip()
                    if norm_target in norm_ath or norm_ath in norm_target:
                        return {
                            "found": True,
                            "display_name": ath.display_name,
                            "slot": slot.upper(),
                            "rank": ath.rank,
                            "is_starter": ath.rank == 1,
                            "athlete_id": ath.athlete_id,
                        }

        return {
            "found": False,
            "display_name": player_name,
            "slot": pos_clean,
            "rank": 1,  # Default assumption if not found
            "is_starter": True,
            "athlete_id": 0,
        }

    def get_next_man_up(
        self,
        player_name: str,
        position: str,
        excluded_names: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Finds the direct backup / next-man-up beneficiary on the depth chart, skipping inactive assets."""
        norm_target = re.sub(r"[^\w\s]", "", player_name.lower()).strip()
        pos_clean = position.upper().strip()
        excluded_norm = {
            re.sub(r"[^\w\s]", "", ex.lower()).strip()
            for ex in (excluded_names or set())
        }

        search_pools = []
        if pos_clean in ("QB", "RB", "FB", "WR", "TE"):
            search_pools.append(self.offense)
        elif pos_clean in ("D/ST", "DST", "CB", "S", "LB", "DE", "DT"):
            search_pools.append(self.defense)
        elif pos_clean in ("K", "PK", "P"):
            search_pools.append(self.special_teams)
        else:
            search_pools.extend([self.offense, self.defense, self.special_teams])

        target_pool = self.offense if pos_clean in ("QB", "RB", "FB", "WR", "TE") else self.defense

        for pool in search_pools:
            for slot, athletes in pool.items():
                for idx, ath in enumerate(athletes):
                    norm_ath = re.sub(r"[^\w\s]", "", ath.display_name.lower()).strip()
                    if norm_target in norm_ath or norm_ath in norm_target:
                        # Direct backup in same slot (checking subsequent ranks if backup is also sidelined)
                        for next_idx in range(idx + 1, len(athletes)):
                            backup = athletes[next_idx]
                            norm_bk = re.sub(r"[^\w\s]", "", backup.display_name.lower()).strip()
                            if norm_bk in excluded_norm or any(ex in norm_bk for ex in excluded_norm if len(ex) > 3):
                                continue
                            return {
                                "athlete_id": backup.athlete_id,
                                "display_name": backup.display_name,
                                "rank": backup.rank,
                                "slot": slot.upper(),
                            }
                        # If no direct athlete in same slot and pos is WR, check other WR slots
                        if pos_clean == "WR":
                            for other_slot in ("wr2", "wr3", "slot_wr", "wr1"):
                                if other_slot != slot.lower() and other_slot in target_pool:
                                    other_athletes = target_pool[other_slot]
                                    for cand in other_athletes:
                                        norm_cand = re.sub(r"[^\w\s]", "", cand.display_name.lower()).strip()
                                        if norm_cand in excluded_norm:
                                            continue
                                        return {
                                            "athlete_id": cand.athlete_id,
                                            "display_name": cand.display_name,
                                            "rank": cand.rank,
                                            "slot": other_slot.upper(),
                                        }
                        return None
        return None


class NFLDepthChartClient:
    """Async client managing real-time post-preseason official NFL depth charts."""

    def __init__(self, timeout: float = 10.0, cache_ttl_seconds: float = 3600.0):
        self.timeout = timeout
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, TeamDepthChart] = {}
        self._lock = asyncio.Lock()

    async def fetch_team_depth_chart(self, team: str, force: bool = False) -> TeamDepthChart | None:
        """Fetches and parses the official depth chart for a single NFL team."""
        team_clean = team.upper().strip()
        now = time.time()

        if not force and team_clean in self._cache:
            chart = self._cache[team_clean]
            if (now - chart.last_updated) < self.cache_ttl:
                return chart

        url = ESPN_DEPTHCHART_BASE_URL.format(team=team_clean.lower())
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"ESPN depth chart API returned HTTP {resp.status_code} for team {team_clean}")
                    return self._cache.get(team_clean)
                data = resp.json()
            except Exception as e:
                logger.warning(f"Failed to fetch depth chart for {team_clean}: {e}")
                return self._cache.get(team_clean)

        offense: dict[str, list[DepthChartAthlete]] = {}
        defense: dict[str, list[DepthChartAthlete]] = {}
        special_teams: dict[str, list[DepthChartAthlete]] = {}

        for group in data.get("depthchart", []):
            group_name = group.get("name", "").lower()
            positions = group.get("positions", {})

            target_dict = offense
            if "defense" in group_name or "3-4" in group_name or "4-3" in group_name:
                target_dict = defense
            elif "special" in group_name:
                target_dict = special_teams

            for pos_key, pos_val in positions.items():
                athletes_list: list[DepthChartAthlete] = []
                for idx, ath_data in enumerate(pos_val.get("athletes", [])):
                    try:
                        ath_id = int(ath_data.get("id", 0) or 0)
                        disp_name = ath_data.get("displayName", "Unknown")
                        short_name = ath_data.get("shortName", disp_name)
                        rank = int(ath_data.get("rank", idx + 1) or (idx + 1))
                        injuries = ath_data.get("injuries", [])

                        athletes_list.append(
                            DepthChartAthlete(
                                athlete_id=ath_id,
                                display_name=disp_name,
                                short_name=short_name,
                                rank=rank,
                                position_slot=pos_key,
                                injuries=injuries,
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Error parsing athlete {ath_data}: {e}")

                if athletes_list:
                    target_dict[pos_key.lower()] = athletes_list

        chart = TeamDepthChart(
            pro_team=team_clean,
            last_updated=now,
            offense=offense,
            defense=defense,
            special_teams=special_teams,
        )

        self._cache[team_clean] = chart
        return chart

    async def fetch_all_depth_charts(self, force: bool = False) -> dict[str, TeamDepthChart]:
        """Fetches official depth charts for all 32 NFL franchises concurrently."""
        tasks = [self.fetch_team_depth_chart(team, force=force) for team in ALL_NFL_TEAMS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        out: dict[str, TeamDepthChart] = {}
        for team, res in zip(ALL_NFL_TEAMS, results):
            if isinstance(res, TeamDepthChart):
                out[team] = res
        return out

    async def get_player_depth_role(self, pro_team: str, player_name: str, position: str) -> dict[str, Any]:
        """Returns official depth chart designation (is_starter, rank, slot)."""
        chart = await self.fetch_team_depth_chart(pro_team)
        if not chart:
            return {
                "found": False,
                "display_name": player_name,
                "slot": position.upper(),
                "rank": 1,
                "is_starter": True,
                "athlete_id": 0,
            }
        return chart.get_player_status(player_name, position)


nfl_depthchart_client = NFLDepthChartClient()
