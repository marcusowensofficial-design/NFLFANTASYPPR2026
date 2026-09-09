"""Central DFS Subsystem Engine (Facade).

Provides high-level, human-friendly functions to query rankings,
build tournament lineups, and audit rosters without any dependency
on the ESPN season-long website.
"""

import logging
from typing import Any
import pandas as pd

from src.adapters.weather.client import weather_client
from src.services.matchup.wrcb_matrix import wrcb_analyzer
from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.dfs.analyzer import dfs_analyzer
from src.dfs.loader import dfs_loader
from src.dfs.optimizer import dfs_optimizer

logger = logging.getLogger(__name__)


class DFSEngine:
    """Unified controller for Daily Fantasy Sports intelligence."""

    def __init__(self):
        self._cached_slates: dict[tuple[str | None, str], pd.DataFrame] = {}

    def clear_cache(self) -> None:
        """Clears cached slate dataframes so next retrieval reloads from disk."""
        self._cached_slates.clear()

    async def get_slate(
        self,
        csv_path: str | None = None,
        projection_source: str = "MODEL",
        force_reload: bool = False,
    ) -> pd.DataFrame:
        """Retrieves and caches the enriched FanDuel slate for the requested projection source."""
        key = (csv_path, (projection_source or "MODEL").upper().strip())
        if force_reload or key not in self._cached_slates:
            self._cached_slates[key] = await dfs_loader.load_slate(
                csv_path=csv_path,
                projection_source=projection_source,
            )
        return self._cached_slates[key]

    async def get_top_running_backs(self, csv_path: str | None = None, min_salary: int = 5000, top_n: int = 15) -> pd.DataFrame:
        """Retrieves top running backs ranked by projected points and value."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_analyzer.get_top_by_position(slate, position="RB", min_salary=min_salary, top_n=top_n)

    async def get_top_wide_receivers(self, csv_path: str | None = None, min_salary: int = 4500, top_n: int = 15) -> pd.DataFrame:
        """Retrieves top wide receivers ranked by projected points and value."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_analyzer.get_top_by_position(slate, position="WR", min_salary=min_salary, top_n=top_n)

    async def get_top_game_stacks(self, csv_path: str | None = None, top_n: int = 5) -> list[dict[str, Any]]:
        """Retrieves highest-upside QB + WR + Bring-Back tournament stacks."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_analyzer.get_top_game_stacks(slate, top_n=top_n)

    async def get_top_chalk(self, csv_path: str | None = None, top_n: int = 15) -> pd.DataFrame:
        """Retrieves highest-projected ownership plays across the slate."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_analyzer.get_top_ownership_plays(slate, top_n=top_n)

    async def get_top_leverage(self, csv_path: str | None = None, top_n: int = 15) -> pd.DataFrame:
        """Retrieves highest-leverage tournament targets across the slate."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_analyzer.get_top_leverage_plays(slate, top_n=top_n)

    async def build_single_entry_lineup(
        self,
        csv_path: str | None = None,
        stack_qb: str | None = None,
        stack_team: str | None = None,
        stack_opp: str | None = None,
        lock_players: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Generates the optimal single-entry championship GPP lineup."""
        slate = await self.get_slate(csv_path=csv_path)

        has_herbert = (slate["name"] == "Justin Herbert").any()
        if not stack_qb:
            if has_herbert:
                stack_qb = "Justin Herbert"
                stack_team = "LAC"
                stack_opp = "ARI"
                default_locks = lock_players or ["Omarion Hampton", "Saquon Barkley", "Ja'Marr Chase", "Ladd McConkey"]
            else:
                # Dynamic top game stack for sub-slates (e.g. early only)
                stacks = dfs_analyzer.get_top_game_stacks(slate, top_n=1)
                if stacks:
                    top_s = stacks[0]
                    stack_qb = top_s["qb"].split(" (")[0]
                    qb_row = slate[slate["name"] == stack_qb].iloc[0]
                    stack_team = qb_row["team"]
                    stack_opp = qb_row["opponent"]
                default_locks = lock_players
        else:
            default_locks = lock_players

        return dfs_optimizer.optimize(
            df_slate=slate,
            mode="SINGLE_ENTRY_GPP",
            stack_qb=stack_qb,
            stack_team=stack_team,
            stack_opp=stack_opp,
            lock_players=default_locks,
            max_salary=60000,
            min_salary=58500,
        )

    async def build_cash_lineup(self, csv_path: str | None = None) -> dict[str, Any] | None:
        """Generates the highest-floor cash game (50-50 / Double-Up) lineup."""
        slate = await self.get_slate(csv_path=csv_path)
        return dfs_optimizer.optimize(
            df_slate=slate,
            mode="CASH",
            max_salary=60000,
            min_salary=58500,
        )

    async def audit_roster(self, roster: list[dict[str, Any]]) -> dict[str, Any]:
        """Performs live forensic audit of stadium weather, WR-CB coverage, and injuries."""
        weather_results = []
        teams_checked = set()

        for player in roster:
            team = player["team"]
            if team not in teams_checked and player["position"] != "D":
                teams_checked.add(team)
                try:
                    w = await weather_client.get_stadium_weather(team)
                    weather_results.append({
                        "team": team,
                        "is_dome": w.is_dome,
                        "temp": round(w.temperature_f, 1),
                        "wind_mph": round(w.wind_speed_mph, 1),
                        "gusts_mph": round(w.wind_gusts_mph, 1),
                        "precip_in": round(w.precipitation_in, 2),
                        "concern": w.weather_concern,
                    })
                except Exception as e:
                    logger.warning(f"Failed weather check for {team}: {e}")

        # Check injuries
        injury_alerts = []
        try:
            live_injuries = await nfl_injuries_client.fetch_injuries()
            for player in roster:
                p_name = player["name"]
                matches = [r for r in live_injuries.values() if p_name.lower() in r.name.lower()]
                if matches:
                    rec = matches[0]
                    injury_alerts.append({
                        "player": p_name,
                        "status": rec.status,
                        "headline": rec.headline,
                        "practice": rec.practice_status,
                    })
        except Exception as e:
            logger.warning(f"Failed live injury audit: {e}")

        return {
            "weather": weather_results,
            "injury_alerts": injury_alerts,
        }


dfs_engine = DFSEngine()
