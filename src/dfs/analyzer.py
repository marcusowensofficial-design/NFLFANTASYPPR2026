"""DFS Slate Analyzer & Game Theory Engine.

Ranks players, calculates value multipliers, identifies primary game stacks,
and filters out injury risks.
"""

import logging
from typing import Any
import pandas as pd

logger = logging.getLogger(__name__)


class DFSSlateAnalyzer:
    """Provides analytical tools for positional rankings, value plays, and game stacks."""

    def get_top_by_position(
        self,
        df_slate: pd.DataFrame,
        position: str,
        min_salary: int = 4000,
        top_n: int = 15,
        exclude_injuries: bool = True,
    ) -> pd.DataFrame:
        """Returns the top players for a specific position sorted by projected points or value."""
        sub = df_slate[df_slate["position"] == position.upper()].copy()

        if exclude_injuries:
            sub = sub[~sub["injury"].isin(["IR", "O", "OUT"]) & ~sub["db_status"].isin(["IR", "OUT", "DAY_TO_DAY"])]

        sub = sub[sub["salary"] >= min_salary]
        return sub.sort_values(by="proj", ascending=False).head(top_n)

    def get_top_values(
        self,
        df_slate: pd.DataFrame,
        position: str | None = None,
        min_proj: float = 9.0,
        top_n: int = 15,
    ) -> pd.DataFrame:
        """Returns the best point-per-dollar values across the slate."""
        sub = df_slate[df_slate["proj"] >= min_proj].copy()
        sub = sub[~sub["injury"].isin(["IR", "O", "OUT"])]

        if position:
            sub = sub[sub["position"] == position.upper()]

        return sub.sort_values(by="value_ratio", ascending=False).head(top_n)

    def get_top_game_environments(self, df_slate: pd.DataFrame) -> list[dict[str, Any]]:
        """Identifies top game environments on the slate based on Vegas totals and pace."""
        games: dict[str, dict[str, Any]] = {}
        for _, r in df_slate.iterrows():
            g = r["game"]
            if g and g not in games:
                games[g] = {
                    "game": g,
                    "game_ou": r["game_ou"],
                    "spread": abs(r["spread"]),
                    "is_dome": r["is_dome"],
                }

        sorted_games = sorted(games.values(), key=lambda x: (x["game_ou"], -x["spread"]), reverse=True)
        return sorted_games

    def get_top_game_stacks(self, df_slate: pd.DataFrame, top_n: int = 5) -> list[dict[str, Any]]:
        """Identifies top QB + WR + Opposing Bring-back tournament game stacks."""
        qbs = df_slate[df_slate["position"] == "QB"].sort_values(by="proj", ascending=False)
        stacks: list[dict[str, Any]] = []

        for _, qb in qbs.iterrows():
            team = qb["team"]
            opp = qb["opponent"]

            # Team WRs/TEs
            pass_catchers = df_slate[(df_slate["team"] == team) & (df_slate["position"].isin(["WR", "TE"])) & (~df_slate["injury"].isin(["IR", "O"]))]
            if pass_catchers.empty:
                continue
            primary_target = pass_catchers.sort_values(by="proj", ascending=False).iloc[0]

            # Opposing Bring-Back
            opp_weapons = df_slate[(df_slate["team"] == opp) & (df_slate["position"].isin(["WR", "TE", "RB"])) & (~df_slate["injury"].isin(["IR", "O"]))]
            if opp_weapons.empty:
                continue
            primary_bringback = opp_weapons.sort_values(by="proj", ascending=False).iloc[0]

            combined_sal = qb["salary"] + primary_target["salary"] + primary_bringback["salary"]
            combined_proj = qb["proj"] + primary_target["proj"] + primary_bringback["proj"]

            stacks.append({
                "game": qb["game"],
                "game_ou": qb["game_ou"],
                "qb": f"{qb['name']} (${qb['salary']:,})",
                "target": f"{primary_target['name']} ({primary_target['position']} - ${primary_target['salary']:,})",
                "bring_back": f"{primary_bringback['name']} ({primary_bringback['position']} - ${primary_bringback['salary']:,})",
                "total_salary": combined_sal,
                "total_proj": round(combined_proj, 2),
                "avg_value": round(combined_proj / (combined_sal / 1000), 2),
            })

        stacks.sort(key=lambda x: x["total_proj"], reverse=True)
        return stacks[:top_n]

    def get_top_ownership_plays(self, df_slate: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """Returns the highest-owned chalk plays across the slate."""
        sub = df_slate[~df_slate["injury"].isin(["IR", "O", "OUT"]) & (df_slate["proj"] >= 5.0)].copy()
        return sub.sort_values(by="proj_ownership", ascending=False).head(top_n)

    def get_top_leverage_plays(self, df_slate: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
        """Returns players with the highest leverage scores (high ceiling relative to low ownership)."""
        sub = df_slate[
            ~df_slate["injury"].isin(["IR", "O", "OUT"])
            & (df_slate["proj"] >= 10.0)
            & (df_slate["proj_ownership"] <= 14.0)
        ].copy()
        return sub.sort_values(by="leverage_score", ascending=False).head(top_n)


dfs_analyzer = DFSSlateAnalyzer()
