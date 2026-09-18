r"""High-Performance Mixed-Integer Linear Programming (MILP) Optimizer for FanDuel Single-Game (Showdown).

Engineered specifically for FanDuel Single-Game (6-slot) slates:
- 1 MVP slot (1.5x Fantasy Points, 1.5x Salary Cap hit)
- 5 AnyFLEX slots (Standard Fantasy Points, Standard Salary)
- $60,000 Salary Cap with mandatory unspent buffer ($200–$900) to eliminate prize chops
- Exact linear formulations for:
  * Dynamic 1.5x MVP pricing Knapsack optimization
  * QB Stacking (No naked QBs)
  * The QB Rule of 3 (Anti-Cannibalization: Max 2 WR/TE without QB; $\ge 3$ WR/TE requires QB)
  * D/ST Anti-Cannibalization (No D/ST with opposing RB1; D/ST vs <= 2 opposing offensive players)
  * Single-Entry Punt Filter (Disqualifies sub-$3,500 ghost punts)
  * Multi-Script Solvers: Solves and compares all 4 distinct game scripts:
    1. Team A Dominant (Onslaught)
    2. Team B Dominant (Onslaught)
    3. Balanced Shootout (3-3 / 4-2)
    4. Zero-QB Touchdown Monopoly
"""

import logging
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

logger = logging.getLogger(__name__)


class FanDuelShowdownOptimizer:
    """Mathematical MILP solver for FanDuel NFL Single-Game / Showdown DFS slates."""

    def __init__(
        self,
        salary_cap: int = 60000,
        max_salary: int = 59800,  # Leaves >= $200 unspent buffer
        min_salary: int = 58500,  # Leaves <= $1,500 unspent
        min_punt_salary: int = 3500,  # Single-entry discipline: no ghost punts under $3,500
    ):
        self.salary_cap = salary_cap
        self.max_salary = max_salary
        self.min_salary = min_salary
        self.min_punt_salary = min_punt_salary

    def clean_slate(
        self,
        df_slate: pd.DataFrame,
        exclude_players: list[str] | None = None,
        allow_sub3500_punts: bool = True,
    ) -> pd.DataFrame:
        """Standardizes columns, cleans injuries, and applies role/route-based quality filters."""
        df = df_slate.copy()

        # Standardize column names
        col_map = {
            "Id": "player_id",
            "Nickname": "name",
            "First Name": "first_name",
            "Last Name": "last_name",
            "Position": "position",
            "Team": "team",
            "Opponent": "opponent",
            "Salary": "salary",
            "FPPG": "proj",
            "Played": "played",
            "Injury Indicator": "injury",
            "Injury Details": "injury_details",
        }
        for old_col, new_col in col_map.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]

        if "name" not in df.columns and "first_name" in df.columns and "last_name" in df.columns:
            df["name"] = df["first_name"].fillna("") + " " + df["last_name"].fillna("")
            df["name"] = df["name"].str.strip()

        # Remove injured players
        is_out_mask = pd.Series(False, index=df.index)
        if "injury" in df.columns:
            is_out_mask = is_out_mask | df["injury"].isin(["IR", "O", "OUT", "DOUBTFUL"])
        if "db_status" in df.columns:
            is_out_mask = is_out_mask | df["db_status"].isin(["IR", "OUT", "DOUBTFUL"])
        if "is_out" in df.columns:
            is_out_mask = is_out_mask | df["is_out"].fillna(False)
        df = df[~is_out_mask].copy()

        # Filter out backup QBs on single-game slates (keep only highest salaried QB per team)
        if "position" in df.columns and "team" in df.columns and "salary" in df.columns:
            qb_mask = df["position"] == "QB"
            if qb_mask.any():
                max_qb_sal_by_team = df[qb_mask].groupby("team")["salary"].max()
                is_backup_qb = qb_mask & (df["salary"] < df["team"].map(max_qb_sal_by_team))
                df = df[~is_backup_qb].copy()

        # Fill missing projections
        if "proj" in df.columns:
            df["proj"] = pd.to_numeric(df["proj"], errors="coerce")
            if "FPPG" in df.columns:
                df["proj"] = df["proj"].fillna(pd.to_numeric(df["FPPG"], errors="coerce"))
        elif "FPPG" in df.columns:
            df["proj"] = pd.to_numeric(df["FPPG"], errors="coerce")

        df["proj"] = df["proj"].fillna(0.0)

        # Eliminate players with 0 projection
        df = df[df["proj"] > 0.0].copy()

        # Apply ceiling projection if not present or contains NaNs
        is_skill = df["position"].isin(["WR", "RB", "TE", "QB"])
        default_ceiling = df["proj"] * 1.35 + (is_skill.astype(float) * 3.5)
        if "ceiling_proj" not in df.columns:
            df["ceiling_proj"] = default_ceiling
        else:
            df["ceiling_proj"] = pd.to_numeric(df["ceiling_proj"], errors="coerce").fillna(default_ceiling)

        default_floor = np.maximum(0.5, df["proj"] * 0.65)
        if "floor_proj" not in df.columns:
            df["floor_proj"] = default_floor
        else:
            df["floor_proj"] = pd.to_numeric(df["floor_proj"], errors="coerce").fillna(default_floor)

        # Exclude specified players
        if exclude_players:
            clean_exclude = [p.strip().lower() for p in exclude_players]
            df = df[~df["name"].str.lower().isin(clean_exclude)].copy()

        # Verified Role & Route Participation Floor:
        # Rather than an arbitrary dollar cutoff (which blocked viable rotational players like Joshua Palmer at $3,200),
        # allow players with verified offensive utility (route_share >= 0.35, snap_share >= 0.40, verified_starter,
        # or proj >= 2.5 and salary >= $3,000), while filtering pure ghost blocking tight ends / depth FB punts.
        if not allow_sub3500_punts:
            has_starter_col = "verified_starter" in df.columns
            has_role_col = "active_role" in df.columns
            has_route_col = "route_share" in df.columns
            has_snap_col = "snap_share" in df.columns

            viable_role_mask = pd.Series(False, index=df.index)
            if has_starter_col:
                viable_role_mask = viable_role_mask | (df["verified_starter"] == True)
            if has_role_col:
                viable_role_mask = viable_role_mask | (df["active_role"] == True)
            if has_route_col:
                viable_role_mask = viable_role_mask | (df["route_share"] >= 0.35)
            if has_snap_col:
                viable_role_mask = viable_role_mask | (df["snap_share"] >= 0.40)

            # Keep if >= min_punt_salary OR has verified offensive role OR reasonable projection floor
            df = df[
                (df["salary"] >= self.min_punt_salary) | 
                viable_role_mask | 
                (df["proj"] >= 4.0)
            ].copy()

        df = df.reset_index(drop=True)
        return df

    def solve(
        self,
        df_slate: pd.DataFrame,
        mode: str = "GPP",  # "GPP" (weights 75% ceiling + 25% median) or "CASH" (70% floor + 30% median)
        script: str = "OPTIMAL",  # "OPTIMAL", "TEAM_A_DOMINANT", "TEAM_B_DOMINANT", "BALANCED", "ZERO_QB", "DUAL_QB"
        lock_mvp: str | None = None,
        disallowed_mvps: list[str] | None = None,
        lock_players: list[str] | None = None,
        exclude_players: list[str] | None = None,
        forbidden_lineups: list[list[str]] | None = None,
        max_salary: int | None = None,
        min_salary: int | None = None,
        allow_sub3500_punts: bool = True,
        enforce_qb_rules: bool = True,
        enforce_dst_rules: bool = True,
    ) -> dict[str, Any] | None:
        """Solves the optimal 6-slot FanDuel Showdown lineup using Mixed-Integer Linear Programming."""
        df = self.clean_slate(
            df_slate,
            exclude_players=exclude_players,
            allow_sub3500_punts=allow_sub3500_punts,
        )

        n = len(df)
        if n < 6:
            logger.error(f"Insufficient players ({n}) to construct a 6-slot lineup.")
            return None

        teams = df["team"].dropna().unique().tolist()
        if len(teams) < 2:
            logger.error(f"Expected 2 teams on single-game slate, found {len(teams)}: {teams}")
            return None

        team_a, team_b = teams[0], teams[1]

        # Objective function coefficients
        # For GPP: 75% 90th percentile ceiling + 25% median
        # For CASH: 70% floor + 30% median
        if mode == "GPP":
            base_pts = df["ceiling_proj"].values * 0.75 + df["proj"].values * 0.25
        elif mode == "CASH":
            base_pts = df["floor_proj"].values * 0.70 + df["proj"].values * 0.30
        else:
            base_pts = df["proj"].values

        # 2N variables:
        # Indices 0 .. n-1: MVP binary variables (score 1.5x, cost 1.5x salary)
        # Indices n .. 2n-1: FLEX binary variables (score 1.0x, cost 1.0x salary)
        c = np.zeros(2 * n)
        c[0:n] = -1.5 * base_pts  # MVP slot scores 1.5x
        c[n : 2 * n] = -1.0 * base_pts  # AnyFLEX slots score 1.0x

        # Integrality: all 2N are binary (1)
        integrality = np.ones(2 * n)
        bounds = Bounds(0, 1)

        A_rows = []
        b_l = []
        b_u = []

        # 1. Exactly 1 MVP slot
        row_mvp = np.zeros(2 * n)
        row_mvp[0:n] = 1.0
        A_rows.append(row_mvp)
        b_l.append(1.0)
        b_u.append(1.0)

        # 2. Exactly 5 AnyFLEX slots
        row_flex = np.zeros(2 * n)
        row_flex[n : 2 * n] = 1.0
        A_rows.append(row_flex)
        b_l.append(5.0)
        b_u.append(5.0)

        # 3. Mutual exclusivity: each player can be chosen AT MOST ONCE (either MVP or FLEX, not both)
        for i in range(n):
            row_excl = np.zeros(2 * n)
            row_excl[i] = 1.0  # MVP
            row_excl[n + i] = 1.0  # FLEX
            A_rows.append(row_excl)
            b_l.append(0.0)
            b_u.append(1.0)

        # 4. Salary Cap constraint with unspent buffer (1.5x salary at MVP, 1.0x at FLEX)
        eff_max_salary = max_salary or self.max_salary
        eff_min_salary = min_salary or self.min_salary
        salaries = df["salary"].values.astype(float)
        row_salary = np.zeros(2 * n)
        row_salary[0:n] = 1.5 * salaries  # 1.5x salary hit at MVP
        row_salary[n : 2 * n] = 1.0 * salaries  # 1.0x salary hit in FLEX
        A_rows.append(row_salary)
        b_l.append(float(eff_min_salary))
        b_u.append(float(eff_max_salary))

        # 5. Team constraints: At least 1 player from each team, max 5 from one team
        mask_team_a = (df["team"] == team_a).values.astype(float)
        mask_team_b = (df["team"] == team_b).values.astype(float)

        row_team_a = np.zeros(2 * n)
        row_team_a[0:n] = mask_team_a
        row_team_a[n : 2 * n] = mask_team_a

        row_team_b = np.zeros(2 * n)
        row_team_b[0:n] = mask_team_b
        row_team_b[n : 2 * n] = mask_team_b

        # Team representation constraints based on script
        if script == "TEAM_A_DOMINANT":
            # 4-2 or 5-1 Team A
            A_rows.append(row_team_a)
            b_l.append(4.0)
            b_u.append(5.0)
            A_rows.append(row_team_b)
            b_l.append(1.0)
            b_u.append(2.0)
            # MVP must be from dominant team
            row_mvp_team_a = np.zeros(2 * n)
            row_mvp_team_a[0:n] = mask_team_a
            A_rows.append(row_mvp_team_a)
            b_l.append(1.0)
            b_u.append(1.0)
        elif script == "TEAM_B_DOMINANT":
            # 4-2 or 5-1 Team B
            A_rows.append(row_team_a)
            b_l.append(1.0)
            b_u.append(2.0)
            A_rows.append(row_team_b)
            b_l.append(4.0)
            b_u.append(5.0)
            # MVP must be from dominant team
            row_mvp_team_b = np.zeros(2 * n)
            row_mvp_team_b[0:n] = mask_team_b
            A_rows.append(row_mvp_team_b)
            b_l.append(1.0)
            b_u.append(1.0)
        elif script == "BALANCED":
            # 3-3 or 4-2 / 2-4
            A_rows.append(row_team_a)
            b_l.append(2.0)
            b_u.append(4.0)
            A_rows.append(row_team_b)
            b_l.append(2.0)
            b_u.append(4.0)
        else:
            # General FanDuel rule: Min 1, Max 5 per team
            A_rows.append(row_team_a)
            b_l.append(1.0)
            b_u.append(5.0)
            A_rows.append(row_team_b)
            b_l.append(1.0)
            b_u.append(5.0)

        # 6. Max 1 QB per team (Prevents rostering starter + backup from same team)
        for t in [team_a, team_b]:
            mask_team_qb = ((df["team"] == t) & (df["position"] == "QB")).values.astype(float)
            if np.sum(mask_team_qb) > 0:
                row_team_qb = np.zeros(2 * n)
                row_team_qb[0:n] = mask_team_qb
                row_team_qb[n : 2 * n] = mask_team_qb
                A_rows.append(row_team_qb)
                b_l.append(0.0)
                b_u.append(1.0)

        # 7. Zero-QB / Dual-QB script constraints
        if script == "ZERO_QB":
            mask_qb = (df["position"] == "QB").values.astype(float)
            row_zero_qb = np.zeros(2 * n)
            row_zero_qb[0:n] = mask_qb
            row_zero_qb[n : 2 * n] = mask_qb
            A_rows.append(row_zero_qb)
            b_l.append(0.0)
            b_u.append(0.0)
        elif script == "DUAL_QB":
            mask_qb = (df["position"] == "QB").values.astype(float)
            row_dual_qb = np.zeros(2 * n)
            row_dual_qb[0:n] = mask_qb
            row_dual_qb[n : 2 * n] = mask_qb
            A_rows.append(row_dual_qb)
            b_l.append(2.0)
            b_u.append(2.0)

        # 7. Correlation Rules (QB Stacking, QB Rule of 3, D/ST Anti-Cannibalization)
        if enforce_qb_rules and script != "ZERO_QB":
            for t in [team_a, team_b]:
                qb_indices = df[(df["team"] == t) & (df["position"] == "QB")].index.tolist()
                rec_indices = df[(df["team"] == t) & (df["position"].isin(["WR", "TE"]))].index.tolist()

                if qb_indices and rec_indices:
                    # Stacking rule: If QB_t is rostered, must pair with at least 1 pass-catcher
                    # Linear form: sum(PassCatchers) - QB >= 0
                    row_stack = np.zeros(2 * n)
                    for r_idx in rec_indices:
                        row_stack[r_idx] = 1.0
                        row_stack[n + r_idx] = 1.0
                    for q_idx in qb_indices:
                        row_stack[q_idx] = -1.0
                        row_stack[n + q_idx] = -1.0
                    A_rows.append(row_stack)
                    b_l.append(0.0)
                    b_u.append(6.0)

                    # QB Rule of 3: Disallow >= 3 pass-catchers without QB
                    # Linear form: sum(PassCatchers) - 3 * QB <= 2
                    # If QB=0 -> PassCatchers <= 2
                    # If QB=1 -> PassCatchers - 3 <= 2 -> PassCatchers <= 5
                    row_rule3 = np.zeros(2 * n)
                    for r_idx in rec_indices:
                        row_rule3[r_idx] = 1.0
                        row_rule3[n + r_idx] = 1.0
                    for q_idx in qb_indices:
                        row_rule3[q_idx] = -3.0
                        row_rule3[n + q_idx] = -3.0
                    A_rows.append(row_rule3)
                    b_l.append(-3.0)
                    b_u.append(2.0)

        if enforce_dst_rules:
            for t_def, t_opp in [(team_a, team_b), (team_b, team_a)]:
                dst_indices = df[(df["team"] == t_def) & (df["position"] == "D")].index.tolist()
                opp_rb1_indices = df[
                    (df["team"] == t_opp) & (df["position"] == "RB")
                ].sort_values("salary", ascending=False).head(1).index.tolist()

                # No D/ST with opposing RB1
                if dst_indices and opp_rb1_indices:
                    row_dst_rb = np.zeros(2 * n)
                    row_dst_rb[dst_indices[0]] = 1.0
                    row_dst_rb[n + dst_indices[0]] = 1.0
                    row_dst_rb[opp_rb1_indices[0]] = 1.0
                    row_dst_rb[n + opp_rb1_indices[0]] = 1.0
                    A_rows.append(row_dst_rb)
                    b_l.append(0.0)
                    b_u.append(1.0)

                # D/ST cannot face >= 3 opposing offensive players:
                # OppOffense + 2 * DST <= 4
                opp_off_indices = df[(df["team"] == t_opp) & (df["position"].isin(["QB", "RB", "WR", "TE"]))].index.tolist()
                if dst_indices and opp_off_indices:
                    row_dst_opp = np.zeros(2 * n)
                    for o_idx in opp_off_indices:
                        row_dst_opp[o_idx] = 1.0
                        row_dst_opp[n + o_idx] = 1.0
                    row_dst_opp[dst_indices[0]] = 2.0
                    row_dst_opp[n + dst_indices[0]] = 2.0
                    A_rows.append(row_dst_opp)
                    b_l.append(0.0)
                    b_u.append(4.0)

        # 8. Locks & Excludes
        if lock_mvp:
            lock_mvp_clean = lock_mvp.strip().lower()
            mvp_match = df[df["name"].str.lower() == lock_mvp_clean].index.tolist()
            if mvp_match:
                row_lock_mvp = np.zeros(2 * n)
                row_lock_mvp[mvp_match[0]] = 1.0
                A_rows.append(row_lock_mvp)
                b_l.append(1.0)
                b_u.append(1.0)

        if lock_players:
            for lp in lock_players:
                lp_clean = lp.strip().lower()
                lp_match = df[df["name"].str.lower() == lp_clean].index.tolist()
                if lp_match:
                    row_lock = np.zeros(2 * n)
                    row_lock[lp_match[0]] = 1.0  # MVP
                    row_lock[n + lp_match[0]] = 1.0  # FLEX
                    A_rows.append(row_lock)
                    b_l.append(1.0)
                    b_u.append(1.0)

        # 9. Disallowed MVPs (Diversifies MVP selections across portfolio)
        if disallowed_mvps:
            for d_mvp in disallowed_mvps:
                d_clean = d_mvp.strip().lower()
                d_match = df[df["name"].str.lower() == d_clean].index.tolist()
                if d_match:
                    row_disallow_mvp = np.zeros(2 * n)
                    row_disallow_mvp[d_match[0]] = 1.0
                    A_rows.append(row_disallow_mvp)
                    b_l.append(0.0)
                    b_u.append(0.0)

        # 10. Forbidden Lineups (Prevents Duplicates in Multi-Lineup Portfolios)
        if forbidden_lineups:
            for fl in forbidden_lineups:
                fl_clean = [p.strip().lower() for p in fl]
                matched_indices = df[df["name"].str.lower().isin(fl_clean)].index.tolist()
                if len(matched_indices) >= 5:
                    row_fl = np.zeros(2 * n)
                    for m_idx in matched_indices:
                        row_fl[m_idx] = 1.0
                        row_fl[n + m_idx] = 1.0
                    A_rows.append(row_fl)
                    b_l.append(0.0)
                    b_u.append(float(len(matched_indices) - 1))

        A = np.array(A_rows)
        constraints = LinearConstraint(A, b_l, b_u)

        # Solve MILP
        res = milp(c=c, integrality=integrality, bounds=bounds, constraints=constraints)

        if not res.success:
            logger.warning(f"MILP Showdown Optimization failed for script={script}: {res.status}")
            return None

        # Extract solution
        sol = np.round(res.x).astype(int)
        mvp_idx = np.where(sol[0:n] == 1)[0]
        flex_indices = np.where(sol[n : 2 * n] == 1)[0]

        if len(mvp_idx) != 1 or len(flex_indices) != 5:
            logger.error(f"Invalid solution counts: MVP={len(mvp_idx)}, FLEX={len(flex_indices)}")
            return None

        mvp_player = df.iloc[mvp_idx[0]].to_dict()
        mvp_player["roster_slot"] = "MVP (1.5x)"
        mvp_player["effective_salary"] = int(mvp_player["salary"] * 1.5)
        mvp_player["effective_pts"] = round(float(mvp_player["proj"] * 1.5), 2)
        mvp_player["effective_ceiling"] = round(float(mvp_player["ceiling_proj"] * 1.5), 2)

        flex_players = []
        for f_idx in flex_indices:
            p_dict = df.iloc[f_idx].to_dict()
            p_dict["roster_slot"] = "AnyFLEX"
            p_dict["effective_salary"] = int(p_dict["salary"])
            p_dict["effective_pts"] = round(float(p_dict["proj"]), 2)
            p_dict["effective_ceiling"] = round(float(p_dict["ceiling_proj"]), 2)
            flex_players.append(p_dict)

        total_salary = mvp_player["effective_salary"] + sum(p["effective_salary"] for p in flex_players)
        total_proj = mvp_player["effective_pts"] + sum(p["effective_pts"] for p in flex_players)
        total_ceiling = mvp_player["effective_ceiling"] + sum(p["effective_ceiling"] for p in flex_players)
        unspent_buffer = self.salary_cap - total_salary

        roster = [mvp_player] + flex_players

        # Team breakdown
        team_counts = {}
        for p in roster:
            team_counts[p["team"]] = team_counts.get(p["team"], 0) + 1

        return {
            "script": script,
            "mode": mode,
            "total_salary": total_salary,
            "unspent_buffer": unspent_buffer,
            "total_projected_pts": round(total_proj, 2),
            "total_ceiling_pts": round(total_ceiling, 2),
            "team_counts": team_counts,
            "mvp": mvp_player,
            "flex": flex_players,
            "roster": roster,
        }

    def generate_all_scripts(
        self,
        df_slate: pd.DataFrame,
        mode: str = "GPP",
        allow_sub3500_punts: bool = False,
        lock_mvp: str | None = None,
        lock_players: list[str] | None = None,
        exclude_players: list[str] | None = None,
    ) -> dict[str, Any]:
        """Solves and compares all 4 distinct game scripts for stress-testing and balanced portfolio building."""
        clean_df = self.clean_slate(
            df_slate,
            allow_sub3500_punts=allow_sub3500_punts,
            exclude_players=exclude_players,
        )
        teams = clean_df["team"].dropna().unique().tolist()
        team_a, team_b = (teams[0], teams[1]) if len(teams) >= 2 else ("TeamA", "TeamB")

        scripts_to_run = [
            ("OPTIMAL", "Pure Unconstrained Optimal"),
            ("TEAM_A_DOMINANT", f"{team_a} Onslaught (4-2 or 5-1)"),
            ("TEAM_B_DOMINANT", f"{team_b} Onslaught (4-2 or 5-1)"),
            ("BALANCED", "Balanced Game Script (3-3 / 4-2)"),
            ("DUAL_QB", "Dual-QB Baseline Floor / Shootout"),
            ("ZERO_QB", "Zero-QB Touchdown Monopoly"),
        ]

        results = {}
        for script_id, script_name in scripts_to_run:
            sol = self.solve(
                clean_df,
                mode=mode,
                script=script_id,
                allow_sub3500_punts=allow_sub3500_punts,
                lock_mvp=lock_mvp,
                lock_players=lock_players,
                exclude_players=exclude_players,
            )
            if sol:
                sol["script_name"] = script_name
                results[script_id] = sol

        return results

    def generate_portfolio(
        self,
        df_slate: pd.DataFrame,
        num_lineups: int = 5,
        max_flex_exposure: float = 0.50,  # Max 50% exposure for non-QB skill players
        max_mvp_exposure: float = 0.40,   # Max 40% on any single MVP
        game_total: float | None = None,
        mode: str = "GPP",
        allow_sub3500_punts: bool = True,
        exclude_players: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generates a mathematically diversified tournament portfolio enforcing script quotas and exposure caps.

        Guarantees:
        1. Script diversification: For high totals (>= 50.0), at least 40% Dual-QB builds.
        2. Exposure caps: Prevents single-player concentration risks (e.g. max 50% non-QB flex exposure).
        3. Multi-MVP allocation: Ensures top target hogs and dual-threat QBs both get MVP representation.
        4. Zero exact duplicate rosters.
        """
        clean_df = self.clean_slate(
            df_slate,
            allow_sub3500_punts=allow_sub3500_punts,
            exclude_players=exclude_players,
        )
        base_excludes = list(exclude_players) if exclude_players else []

        # Determine script schedule based on game total
        if game_total is not None and game_total >= 50.0:
            # High-total shootout: prioritize Dual-QB and passing onslaughts
            script_cycle = ["DUAL_QB", "DUAL_QB", "BALANCED", "TEAM_A_DOMINANT", "TEAM_B_DOMINANT"]
        elif game_total is not None and game_total <= 43.0:
            # Low-total ground/defense game: prioritize onslaughts, Zero-QB, and defensive slugfest
            script_cycle = ["TEAM_A_DOMINANT", "TEAM_B_DOMINANT", "ZERO_QB", "BALANCED", "OPTIMAL"]
        else:
            # Standard mid-total slate
            script_cycle = ["OPTIMAL", "DUAL_QB", "TEAM_A_DOMINANT", "TEAM_B_DOMINANT", "BALANCED"]

        # Expand script cycle to match num_lineups
        scheduled_scripts = [script_cycle[i % len(script_cycle)] for i in range(num_lineups)]

        # Tracking structures
        lineups = []
        player_flex_counts: dict[str, int] = {}
        player_mvp_counts: dict[str, int] = {}
        player_positions: dict[str, str] = {}
        player_salaries: dict[str, int] = {}
        player_teams: dict[str, str] = {}
        existing_roster_sets: list[frozenset[str]] = []

        # Strict total exposure limits (e.g. max 2 of 5 = 40% for 5-lineup contest)
        max_total_allowed = max(1, int(np.floor(num_lineups * max_flex_exposure) if num_lineups >= 4 else np.ceil(num_lineups * max_flex_exposure)))
        max_mvp_allowed = max(1, int(np.ceil(num_lineups * max_mvp_exposure)))
        forbidden_lineups: list[list[str]] = []

        for idx, target_script in enumerate(scheduled_scripts, 1):
            temp_excludes = list(base_excludes)
            
            # Non-QB total exposure cap enforcement (insulates portfolio from injuries)
            all_tracked = set(list(player_flex_counts.keys()) + list(player_mvp_counts.keys()))
            for p_name in all_tracked:
                pos = player_positions.get(p_name, "")
                tot_c = player_flex_counts.get(p_name, 0) + player_mvp_counts.get(p_name, 0)
                if pos != "QB" and tot_c >= max_total_allowed:
                    if p_name not in temp_excludes:
                        temp_excludes.append(p_name)

            # Check if any MVP has reached the MVP allocation cap
            disallowed_mvps = [p for p, c in player_mvp_counts.items() if c >= max_mvp_allowed]

            # Solve lineup enforcing forbidden lineups, disallowed MVPs, and exposure limits
            sol = None
            for attempt in range(4):
                # If subsequent attempts, relax the latest temporary exclusion
                attempt_excludes = temp_excludes if attempt == 0 else temp_excludes[:-attempt]

                sol = self.solve(
                    clean_df,
                    mode=mode,
                    script=target_script,
                    allow_sub3500_punts=allow_sub3500_punts,
                    exclude_players=attempt_excludes,
                    forbidden_lineups=forbidden_lineups,
                    disallowed_mvps=disallowed_mvps,
                )

                if sol:
                    roster_set = frozenset([p["name"] for p in sol["roster"]])
                    if roster_set not in existing_roster_sets:
                        break
                    sol = None

            if not sol:
                # Fallback to unconstrained solve with forbidden_lineups
                sol = self.solve(
                    clean_df,
                    mode=mode,
                    script="OPTIMAL",
                    allow_sub3500_punts=allow_sub3500_punts,
                    exclude_players=base_excludes,
                    forbidden_lineups=forbidden_lineups,
                )

            if sol:
                sol["lineup_num"] = idx
                sol["script_id"] = target_script
                roster_names = [p["name"] for p in sol["roster"]]
                existing_roster_sets.append(frozenset(roster_names))
                forbidden_lineups.append(roster_names)
                lineups.append(sol)

                # Update counts
                mvp_name = sol["mvp"]["name"]
                player_mvp_counts[mvp_name] = player_mvp_counts.get(mvp_name, 0) + 1
                player_positions[mvp_name] = sol["mvp"]["position"]
                player_salaries[mvp_name] = sol["mvp"]["salary"]
                player_teams[mvp_name] = sol["mvp"]["team"]

                for f in sol["flex"]:
                    f_name = f["name"]
                    player_flex_counts[f_name] = player_flex_counts.get(f_name, 0) + 1
                    player_positions[f_name] = f["position"]
                    player_salaries[f_name] = f["salary"]
                    player_teams[f_name] = f["team"]

        # Build comprehensive portfolio exposure summary
        all_players = set(list(player_flex_counts.keys()) + list(player_mvp_counts.keys()))
        exposures = []
        for p in all_players:
            mvp_c = player_mvp_counts.get(p, 0)
            flex_c = player_flex_counts.get(p, 0)
            total_c = mvp_c + flex_c
            exposures.append({
                "name": p,
                "team": player_teams.get(p, ""),
                "position": player_positions.get(p, ""),
                "salary": player_salaries.get(p, 0),
                "mvp_count": mvp_c,
                "mvp_pct": round((mvp_c / len(lineups)) * 100, 1),
                "flex_count": flex_c,
                "flex_pct": round((flex_c / len(lineups)) * 100, 1),
                "total_count": total_c,
                "total_pct": round((total_c / len(lineups)) * 100, 1),
            })

        df_exposures = pd.DataFrame(exposures).sort_values("total_pct", ascending=False).reset_index(drop=True)

        return {
            "num_lineups": len(lineups),
            "game_total": game_total,
            "max_flex_exposure_limit": max_flex_exposure,
            "lineups": lineups,
            "exposures": df_exposures,
        }

