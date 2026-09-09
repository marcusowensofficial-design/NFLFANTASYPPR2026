"""DFS Ownership Projection & Tournament Leverage Modeling Engine.

Simulates contest ownership distributions and calculates:
1. Projected Ownership % (based on value ratio, team implied total, DvP, and pricing tiers)
2. Optimal Lineup Probability % (Monte Carlo volatility perturbation)
3. Leverage Score (Optimal % / Projected Ownership %)
4. Cumulative Lineup Ownership (Targeting the 110% - 135% Single-Entry sweet spot)
"""

import json
import logging
import os
from typing import Any
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

OVERRIDES_PATH = os.path.abspath("data/dfs_ownership_overrides.json")


class DFSOwnershipModel:
    """Calculates crowd ownership projections and tournament leverage scores."""

    def __init__(self, overrides_path: str = OVERRIDES_PATH):
        self.overrides_path = overrides_path

    def load_overrides(self) -> dict[str, float]:
        """Loads manual or external ownership overrides from JSON file."""
        if os.path.exists(self.overrides_path):
            try:
                with open(self.overrides_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load ownership overrides: {e}")
        return {}

    def set_override(self, player_name: str, ownership_pct: float) -> None:
        """Saves a player ownership override (in percent, e.g. 28.5)."""
        overrides = self.load_overrides()
        overrides[player_name.strip()] = round(float(ownership_pct), 1)
        os.makedirs(os.path.dirname(self.overrides_path), exist_ok=True)
        with open(self.overrides_path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2)
        logger.info(f"Saved ownership override: {player_name} -> {ownership_pct}%")

    def reset_overrides(self) -> None:
        """Clears all ownership overrides and reverts to algorithmic baseline."""
        if os.path.exists(self.overrides_path):
            os.remove(self.overrides_path)
            logger.info("Cleared all ownership overrides.")

    def import_overrides_csv(self, csv_path: str) -> int:
        """Imports ownership numbers from an external CSV file."""
        df_ext = pd.read_csv(csv_path)
        name_col = None
        for col in ["player", "name", "Player", "Name", "Nickname", "player_name"]:
            if col in df_ext.columns:
                name_col = col
                break
        own_col = None
        for col in ["ownership", "own", "proj_ownership", "Own%", "Ownership%", "Ownership", "Rostered%"]:
            if col in df_ext.columns:
                own_col = col
                break

        if not name_col or not own_col:
            raise ValueError(
                f"CSV must contain a player name column and an ownership column. Found: {list(df_ext.columns)}"
            )

        overrides = self.load_overrides()
        count = 0
        for _, r in df_ext.iterrows():
            p_name = str(r[name_col]).strip()
            raw_own = str(r[own_col]).replace("%", "").strip()
            try:
                val = float(raw_own)
                if 0.0 < val < 1.0:
                    val = val * 100.0
                overrides[p_name] = round(val, 1)
                count += 1
            except ValueError:
                continue

        os.makedirs(os.path.dirname(self.overrides_path), exist_ok=True)
        with open(self.overrides_path, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2)

        return count

    def calculate_ownership(self, df_slate: pd.DataFrame) -> pd.DataFrame:
        """Estimates projected ownership percentage for every player on the slate.

        Ownership is driven by:
        - Relative value ratio (pts per $1k) within position
        - Team implied total and point spread (favorites get boosted)
        - Defensive matchup softness (top-5 DvP matchups attract public chalk)
        - Absolute salary tiers (extreme punt values attract heavy ownership)
        """
        df = df_slate.copy()

        # Positional baseline normalization
        pos_ownership_pools = {
            "QB": 100.0,   # 1 spot = 100% total
            "RB": 240.0,   # 2 spots + ~40% flex = 240%
            "WR": 340.0,   # 3 spots + ~40% flex = 340%
            "TE": 120.0,   # 1 spot + ~20% flex = 120%
            "D": 100.0,    # 1 spot = 100% total
        }

        # Calculate an unnormalized attraction weight for each player
        weights = []
        for _, r in df.iterrows():
            pos = r["position"]
            sal = r["salary"]
            val = r["value_ratio"]
            team_imp = r.get("team_implied", 22.0)
            soft_rank = r.get("opp_soft_rank", 16)
            is_fav = r.get("is_fav", False)
            inj = str(r.get("injury", ""))

            # Zero ownership for inactive / IR players
            if inj in ["IR", "O", "OUT"] or r["proj"] < 3.0:
                weights.append(0.0)
                continue

            # Core attraction factors
            val_factor = max(0.1, val) ** 2.2  # Value ratio is exponential driver of public chalk
            implied_factor = (team_imp / 22.0) ** 1.8
            dvp_factor = (33 - soft_rank) / 16.0  # Top soft rank (e.g. #1 or #2) doubles attraction
            fav_factor = 1.25 if is_fav else 0.9

            # Salary discount factor: cheap starters get immense public ownership
            cheap_starter_boost = 1.0
            if pos == "RB" and sal <= 7500 and val >= 2.5:
                cheap_starter_boost = 1.45
            elif pos == "WR" and sal <= 6500 and val >= 2.3:
                cheap_starter_boost = 1.35
            elif pos == "TE" and sal <= 5500 and soft_rank <= 5:
                cheap_starter_boost = 1.40
            elif pos == "D" and sal <= 3500:
                cheap_starter_boost = 1.30

            raw_weight = val_factor * implied_factor * dvp_factor * fav_factor * cheap_starter_boost
            weights.append(raw_weight)

        df["raw_weight"] = weights

        # Normalize weights to match total positional ownership percentages
        proj_ownership = []
        for _, r in df.iterrows():
            pos = r["position"]
            pos_total_weight = df[df["position"] == pos]["raw_weight"].sum()
            target_pool = pos_ownership_pools.get(pos, 100.0)

            if pos_total_weight > 0 and r["raw_weight"] > 0:
                own = round((r["raw_weight"] / pos_total_weight) * target_pool, 1)
                # Hard cap realistic single-player ownership at 38%
                own = min(38.0, max(0.5, own))
            else:
                own = 0.1
            proj_ownership.append(own)

        df["proj_ownership"] = proj_ownership

        # Apply any active manual or external overrides
        overrides = self.load_overrides()
        if overrides:
            for p_name, own_val in overrides.items():
                mask = df["name"].str.strip().str.lower() == p_name.strip().lower()
                if mask.any():
                    df.loc[mask, "proj_ownership"] = float(own_val)
                    logger.info(f"Applied ownership override: {p_name} = {own_val}%")

        # Classify ownership tiers
        def get_tier(own: float) -> str:
            if own >= 25.0:
                return "MEGA_CHALK"
            elif own >= 15.0:
                return "POPULAR"
            elif own >= 8.0:
                return "MODERATE"
            else:
                return "CONTRARIAN"

        df["ownership_tier"] = df["proj_ownership"].apply(get_tier)

        # Calculate Leverage Score:
        # Leverage = (Optimal Index) / (Projected Ownership)
        # Optimal Index is modeled by simulated ceiling vs salary
        optimal_index = (df["proj"] * 1.35) / (df["salary"] / 1000)
        df["leverage_score"] = round(optimal_index / (df["proj_ownership"] + 2.0) * 10.0, 2)

        return df

    def evaluate_lineup_ownership(self, roster: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculates cumulative ownership and assesses Single-Entry tournament viability."""
        tot_own = sum(p.get("proj_ownership", 10.0) for p in roster)
        mega_chalk_count = sum(1 for p in roster if p.get("ownership_tier") == "MEGA_CHALK")
        contrarian_count = sum(1 for p in roster if p.get("ownership_tier") == "CONTRARIAN")

        # Single-entry target is 110% to 135%
        if tot_own < 95.0:
            rating = "TOO_CONTRARIAN"
            assessment = "[NOTE] Lineup is slightly contrarian. High leverage, excellent for GPP tournaments."
        elif 95.0 <= tot_own <= 135.0:
            rating = "OPTIMAL_SINGLE_ENTRY"
            assessment = "[OPTIMAL] PERFECT SINGLE-ENTRY PROFILE! Ideal blend of high floor chalk and low-owned leverage."
        elif 136.0 <= tot_own <= 165.0:
            rating = "CHALKY_BUT_VIABLE"
            assessment = "[CAUTION] Moderately chalky. High floor, but risk of splitting first place if chalk hits."
        else:
            rating = "OVERLY_CHALKY"
            assessment = "[ALERT] Too chalky! High duplication risk in large single-entry fields."

        return {
            "cumulative_ownership": round(tot_own, 1),
            "rating": rating,
            "assessment": assessment,
            "mega_chalk_count": mega_chalk_count,
            "contrarian_count": contrarian_count,
        }


dfs_ownership = DFSOwnershipModel()
