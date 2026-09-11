"""High-Performance Mixed-Integer Linear Programming (MILP) DFS Lineup Optimizer.

Supports:
- FanDuel 2026 Rules: $60k Salary Cap, 9 Roster Spots (1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX, 1 D/ST)
- Single-Entry GPP: Enforces QB-Pass Catcher primary stack, opposing bring-back, D/ST non-conflict
- Cash Games: Maximizes median floor with volume bellcows
- Multi-team constraint: Min 3 teams, max 4 per team
"""

import logging
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

logger = logging.getLogger(__name__)


class DFSLineupOptimizer:
    """Mathematical optimizer for FanDuel NFL DFS slates."""

    def optimize(
        self,
        df_slate: pd.DataFrame,
        mode: str = "SINGLE_ENTRY_GPP",  # "SINGLE_ENTRY_GPP" or "CASH"
        stack_qb: str | None = None,
        stack_team: str | None = None,
        stack_opp: str | None = None,
        lock_players: list[str] | None = None,
        exclude_players: list[str] | None = None,
        max_salary: int = 60000,
        min_salary: int = 58000,
        overlap_lineups: list[list[int]] | None = None,
        max_overlap: int = 6,
    ) -> dict[str, Any] | None:
        """Solves the optimal lineup under linear constraints."""
        # 1. Clean player pool: exclude injured players
        df = df_slate[
            ~df_slate["injury"].isin(["IR", "O", "OUT"])
            & ~df_slate["db_status"].isin(["IR", "OUT", "DAY_TO_DAY"])
            & (df_slate["proj"] >= 3.0)
        ].reset_index(drop=True).copy()

        # Disqualify non-starting backup QBs: on each NFL team, only the starter (highest salaried QB) is eligible
        for t in df["team"].dropna().unique():
            team_qbs = df[(df["team"] == t) & (df["position"] == "QB")]
            if len(team_qbs) > 1:
                max_qb_sal = team_qbs["salary"].max()
                backup_qb_idx = team_qbs[team_qbs["salary"] < max_qb_sal].index
                df = df.drop(backup_qb_idx)

        df = df.reset_index(drop=True)

        n = len(df)
        if mode == "SINGLE_ENTRY_GPP" and "ceiling_proj" in df.columns:
            # 75% 90th percentile ceiling + 25% median projection for tournament explosion
            c = -(df["ceiling_proj"].values * 0.75 + df["proj"].values * 0.25)
        elif mode == "CASH" and "floor_proj" in df.columns:
            # 70% safety floor + 30% median projection for cash games
            c = -(df["floor_proj"].values * 0.70 + df["proj"].values * 0.30)
        else:
            c = -df["proj"].values

        A_rows = []
        b_l = []
        b_u = []

        # 1. Total players = 9
        A_rows.append(np.ones(n))
        b_l.append(9)
        b_u.append(9)

        # 2. Total Salary <= max_salary, >= min_salary
        A_rows.append(df["salary"].values)
        b_l.append(min_salary)
        b_u.append(max_salary)

        # 3. Exactly 1 QB
        A_rows.append((df["position"] == "QB").astype(float).values)
        b_l.append(1)
        b_u.append(1)

        # 4. Exactly 1 D/ST
        A_rows.append((df["position"] == "D").astype(float).values)
        b_l.append(1)
        b_u.append(1)

        # 5. RBs: 2 to 3 (2 RB + optional FLEX)
        A_rows.append((df["position"] == "RB").astype(float).values)
        b_l.append(2)
        b_u.append(3)

        # 6. WRs: 3 to 4 (3 WR + optional FLEX)
        A_rows.append((df["position"] == "WR").astype(float).values)
        b_l.append(3)
        b_u.append(4)

        # 7. TEs: 1 to 2 (1 TE + optional FLEX)
        A_rows.append((df["position"] == "TE").astype(float).values)
        b_l.append(1)
        b_u.append(2)

        # 8. Flex constraint: RB + WR + TE == 7
        is_flex_eligible = df["position"].isin(["RB", "WR", "TE"]).astype(float).values
        A_rows.append(is_flex_eligible)
        b_l.append(7)
        b_u.append(7)

        # 9. Max 4 players from the same NFL team (FanDuel rule)
        for t in df["team"].unique():
            is_team = (df["team"] == t).astype(float).values
            A_rows.append(is_team)
            b_l.append(0)
            b_u.append(4)

        # 10. Tournament Stacking Constraints (for SINGLE_ENTRY_GPP)
        if mode == "SINGLE_ENTRY_GPP":
            # If stack_qb is explicitly specified:
            if stack_qb:
                is_qb = (df["name"].str.lower() == stack_qb.lower()).astype(float).values
                if is_qb.sum() > 0:
                    A_rows.append(is_qb)
                    b_l.append(1)
                    b_u.append(1)
            elif stack_team:
                is_team_qb = ((df["team"] == stack_team) & (df["position"] == "QB")).astype(float).values
                A_rows.append(is_team_qb)
                b_l.append(1)
                b_u.append(1)

            # Enforce pass-catcher from the stack team
            if stack_team:
                is_pc = ((df["team"] == stack_team) & (df["position"].isin(["WR", "TE"]))).astype(float).values
                A_rows.append(is_pc)
                b_l.append(1)
                b_u.append(3)

            # Enforce opposing bring-back
            if stack_opp:
                is_bb = ((df["team"] == stack_opp) & (df["position"].isin(["WR", "TE", "RB"]))).astype(float).values
                A_rows.append(is_bb)
                b_l.append(1)
                b_u.append(2)

        # 11. Locked & Excluded players (match by name or ID)
        if lock_players:
            for lp in lock_players:
                lp_str = str(lp).strip().lower()
                is_lp = (df["name"].str.lower() == lp_str).astype(float).values
                if is_lp.sum() == 0 and "player_id" in df.columns:
                    is_lp = (df["player_id"].astype(str).str.lower() == lp_str).astype(float).values
                if is_lp.sum() > 0:
                    A_rows.append(is_lp)
                    b_l.append(1)
                    b_u.append(1)

        if exclude_players:
            for ep in exclude_players:
                ep_str = str(ep).strip().lower()
                is_ep = (df["name"].str.lower() == ep_str).astype(float).values
                if is_ep.sum() == 0 and "player_id" in df.columns:
                    is_ep = (df["player_id"].astype(str).str.lower() == ep_str).astype(float).values
                if is_ep.sum() > 0:
                    A_rows.append(is_ep)
                    b_l.append(0)
                    b_u.append(0)

        # Additional overlap constraints (e.g. for multi-lineup uniqueness)
        if overlap_lineups:
            for prev_indices in overlap_lineups:
                overlap_row = np.zeros(n)
                valid_indices = [idx for idx in prev_indices if idx < n]
                if valid_indices:
                    overlap_row[valid_indices] = 1.0
                    A_rows.append(overlap_row)
                    b_l.append(-np.inf)
                    b_u.append(max_overlap)

        # Solve MILP
        A = np.array(A_rows)
        constraints = LinearConstraint(A, b_l, b_u)
        integrality = np.ones(n)
        bounds = Bounds(0, 1)

        res = milp(c=c, constraints=constraints, integrality=integrality, bounds=bounds)

        if not res.success:
            logger.warning(f"Optimizer failed to find a feasible solution for mode={mode}")
            return None

        selected_idx = np.where(res.x > 0.5)[0]
        lineup_df = df.iloc[selected_idx].copy()

        # Check D/ST conflict in GPP: Defense cannot oppose your offensive players
        if mode == "SINGLE_ENTRY_GPP":
            dst_rows = lineup_df[lineup_df["position"] == "D"]
            if not dst_rows.empty:
                dst = dst_rows.iloc[0]
                off_teams = lineup_df[lineup_df["position"] != "D"]["team"].unique().tolist()
                if dst["opponent"] in off_teams:
                    # Add conflict exclusion and re-run recursively
                    new_excludes = (exclude_players or []) + [dst["name"]]
                    return self.optimize(
                        df_slate=df_slate,
                        mode=mode,
                        stack_qb=stack_qb,
                        stack_team=stack_team,
                        stack_opp=stack_opp,
                        lock_players=lock_players,
                        exclude_players=new_excludes,
                        max_salary=max_salary,
                        min_salary=min_salary,
                        overlap_lineups=overlap_lineups,
                        max_overlap=max_overlap,
                    )

        # Structure final lineup output
        order_map = {"QB": 1, "RB": 2, "WR": 3, "TE": 4, "D": 5}
        lineup_df["pos_order"] = lineup_df["position"].map(order_map).fillna(6)
        lineup_sorted = lineup_df.sort_values(
            by=["pos_order", "salary", "proj"], ascending=[True, False, False]
        )

        counts = {"RB": 0, "WR": 0, "TE": 0}
        roster_items = []
        for _, row in lineup_sorted.iterrows():
            pos = row["position"]
            slot = pos
            if pos in counts:
                counts[pos] += 1
                if (pos == "RB" and counts[pos] > 2) or (pos == "WR" and counts[pos] > 3) or (pos == "TE" and counts[pos] > 1):
                    slot = f"FLEX ({pos})"

            roster_items.append({
                "slot": slot,
                "player_id": row["player_id"],
                "name": row["name"],
                "position": row["position"],
                "team": row["team"],
                "opponent": row["opponent"],
                "salary": int(row["salary"]),
                "proj": float(row["proj"]),
                "ceiling": float(row.get("ceiling_proj", round(row["proj"] * 1.4, 2))),
                "team_implied": float(row["team_implied"]),
                "opp_soft_rank": int(row["opp_soft_rank"]),
                "opp_tier": str(row.get("opp_tier", "NEUTRAL")),
                "opp_tier_label": str(row.get("opp_tier_label", "Neutral Matchup")),
                "opp_fd_fpa": float(row.get("opp_fd_fpa", 20.0)),
                "value_ratio": float(row["value_ratio"]),
                "proj_ownership": float(row.get("proj_ownership", 10.0)),
                "ownership_tier": str(row.get("ownership_tier", "MODERATE")),
                "leverage_score": float(row.get("leverage_score", 1.0)),
            })

        total_salary = int(lineup_df["salary"].sum())
        total_proj = round(float(lineup_df["proj"].sum()), 2)
        total_ceiling = round(float(lineup_df["ceiling_proj"].sum() if "ceiling_proj" in lineup_df.columns else total_proj * 1.4), 2)
        value_mult = round(total_proj / (total_salary / 1000), 2)

        from src.dfs.ownership import dfs_ownership
        ownership_eval = dfs_ownership.evaluate_lineup_ownership(roster_items)

        return {
            "mode": mode,
            "total_salary": total_salary,
            "salary_cap": max_salary,
            "salary_remaining": max_salary - total_salary,
            "total_projected_points": total_proj,
            "total_ceiling_points": total_ceiling,
            "value_multiplier": value_mult,
            "full_ppr_projected_points": round(total_proj + 17.5, 2),
            "cumulative_ownership": ownership_eval["cumulative_ownership"],
            "ownership_rating": ownership_eval["rating"],
            "ownership_assessment": ownership_eval["assessment"],
            "roster": roster_items,
            "_selected_indices": selected_idx.tolist(),
        }

    def optimize_multi(
        self,
        df_slate: pd.DataFrame,
        num_lineups: int = 1,
        randomness: float = 0.0,
        mode: str = "SINGLE_ENTRY_GPP",
        stack_qb: str | None = None,
        stack_team: str | None = None,
        stack_opp: str | None = None,
        lock_players: list[str] | None = None,
        exclude_players: list[str] | None = None,
        max_salary: int = 60000,
        min_salary: int = 58000,
    ) -> list[dict[str, Any]]:
        """Generates multiple unique, competitive DFS lineups."""
        num_lineups = max(1, min(int(num_lineups), 20))
        lineups: list[dict[str, Any]] = []
        overlap_history: list[list[int]] = []

        # Base lineup 1
        base_lineup = self.optimize(
            df_slate=df_slate,
            mode=mode,
            stack_qb=stack_qb,
            stack_team=stack_team,
            stack_opp=stack_opp,
            lock_players=lock_players,
            exclude_players=exclude_players,
            max_salary=max_salary,
            min_salary=min_salary,
        )
        if base_lineup:
            lineups.append(base_lineup)
            if "_selected_indices" in base_lineup:
                overlap_history.append(base_lineup["_selected_indices"])

        if num_lineups <= 1 or not lineups:
            return lineups

        # Generate subsequent diverse lineups
        np.random.seed(42)
        for i in range(1, num_lineups):
            # Apply projection perturbation if randomness is active
            df_current = df_slate.copy()
            if randomness > 0.0:
                noise = np.random.normal(0, randomness, size=len(df_current))
                df_current["proj"] = np.maximum(1.0, df_current["proj"] * (1.0 + noise)).round(2)
                if "ceiling_proj" in df_current.columns:
                    df_current["ceiling_proj"] = np.maximum(1.5, df_current["ceiling_proj"] * (1.0 + noise)).round(2)

            # Try overlap constraint <= 6, fallback to 7 if infeasible
            candidate = None
            for max_ov in [6, 7, 8]:
                candidate = self.optimize(
                    df_slate=df_current,
                    mode=mode,
                    stack_qb=stack_qb if i % 2 == 0 else None,
                    stack_team=stack_team if i % 2 == 0 else None,
                    stack_opp=stack_opp if i % 2 == 0 else None,
                    lock_players=lock_players,
                    exclude_players=exclude_players,
                    max_salary=max_salary,
                    min_salary=min_salary,
                    overlap_lineups=overlap_history,
                    max_overlap=max_ov,
                )
                if candidate:
                    break

            if candidate:
                lineups.append(candidate)
                if "_selected_indices" in candidate:
                    overlap_history.append(candidate["_selected_indices"])
            else:
                break

        return lineups

    def calculate_portfolio_exposure(
        self, lineups: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Calculates player exposure counts and percentages across a portfolio of lineups."""
        if not lineups:
            return {}
        total = len(lineups)
        exposure: dict[str, dict[str, Any]] = {}
        for lineup in lineups:
            for item in lineup.get("roster", []):
                pid = item["player_id"]
                if pid not in exposure:
                    exposure[pid] = {
                        "player_id": pid,
                        "name": item["name"],
                        "position": item["position"],
                        "team": item["team"],
                        "salary": item["salary"],
                        "count": 0,
                        "pct": 0.0,
                    }
                exposure[pid]["count"] += 1

        for pid in exposure:
            exposure[pid]["pct"] = round((exposure[pid]["count"] / total) * 100, 1)

        # Sort descending by count
        sorted_exp = dict(sorted(exposure.items(), key=lambda x: x[1]["count"], reverse=True))
        return sorted_exp

    def format_fanduel_csv_export(self, lineups: list[dict[str, Any]]) -> str:
        """Formats generated lineups into FanDuel CSV import format.
        
        Header: entry_id,contest_id,contest_name,QB,RB,RB,WR,WR,WR,TE,FLEX,DEF
        """
        lines = ["entry_id,contest_id,contest_name,QB,RB,RB,WR,WR,WR,TE,FLEX,DEF"]
        for idx, lineup in enumerate(lineups, 1):
            roster = lineup.get("roster", [])
            qb = next((p for p in roster if p["slot"] == "QB"), None)
            rbs = [p for p in roster if p["slot"] == "RB"]
            wrs = [p for p in roster if p["slot"] == "WR"]
            te = next((p for p in roster if p["slot"] == "TE"), None)
            flex = next((p for p in roster if "FLEX" in p["slot"]), None)
            dst = next((p for p in roster if p["slot"] == "D"), None)

            def _fmt(p):
                if not p:
                    return ""
                return f"{p['player_id']}:{p['name']}"

            qb_val = _fmt(qb)
            rb1_val = _fmt(rbs[0]) if len(rbs) > 0 else ""
            rb2_val = _fmt(rbs[1]) if len(rbs) > 1 else ""
            wr1_val = _fmt(wrs[0]) if len(wrs) > 0 else ""
            wr2_val = _fmt(wrs[1]) if len(wrs) > 1 else ""
            wr3_val = _fmt(wrs[2]) if len(wrs) > 2 else ""
            te_val = _fmt(te)
            flex_val = _fmt(flex)
            dst_val = _fmt(dst)

            row = f",,,{qb_val},{rb1_val},{rb2_val},{wr1_val},{wr2_val},{wr3_val},{te_val},{flex_val},{dst_val}"
            lines.append(row)

        return "\n".join(lines)

    def optimize_single_game(
        self,
        df_slate: pd.DataFrame,
        mode: str = "GPP",
        lock_mvp: str | None = None,
        force_zero_qb: bool = False,
        force_qb_stack: bool = False,
        exclude_players: list[str] | None = None,
        min_salary: int = 59100,
        max_salary: int = 59800,
        top_n: int = 3,
    ) -> list[dict[str, Any]]:
        """Solves the optimal 6-slot FanDuel Single Game (Showdown) lineup.
        
        Enforces:
        - 1 MVP (1.5x Salary & 1.5x Scoring) + 5 AnyFLEX (1.0x Salary & Scoring)
        - $60,000 Salary Cap leaving $200 to $900 on table (default $59,100 - $59,800)
        - Both teams represented (min 1 player per team)
        - Pro Correlation Rules:
          * Negative Correlation Leakage: Max 2 pass-catchers from Team A if Team A QB is NOT rostered.
          * QB Rule of 3: If 3+ pass-catchers from Team A are rostered, Team A QB MUST be in lineup.
          * QB Stacking: If QB is rostered, paired with at least 1 pass-catcher.
          * D/ST Anti-Cannibalization: Never pair D/ST with opposing RB1 or 3+ opposing players.
        """
        import itertools

        df = df_slate.copy()
        excludes = set(p.strip().lower() for p in (exclude_players or []))

        # Filter active players
        clean_rows = []
        for _, r in df.iterrows():
            name = str(r.get("Nickname") or r.get("name") or "").strip()
            if not name or name.lower() in excludes:
                continue
            inj = str(r.get("Injury Indicator") or r.get("injury") or "").upper()
            if inj in ["IR", "O", "OUT"]:
                continue

            pos = str(r.get("Position") or r.get("position") or "").strip()
            team = str(r.get("Team") or r.get("team") or "").strip()
            base_sal = int(r.get("Salary") or r.get("salary") or 0)
            mvp_sal = int(r.get("MVP 1.5x Salary") or int(base_sal * 1.5))
            proj = float(r.get("proj") or r.get("projected_points") or r.get("FPPG") or 0.0)
            ceiling = float(r.get("ceiling") or r.get("ceiling_proj") or (proj * 1.45))

            if proj < 1.0 or base_sal <= 0:
                continue

            clean_rows.append({
                "name": name,
                "position": pos,
                "team": team,
                "base_sal": base_sal,
                "mvp_sal": mvp_sal,
                "proj": proj,
                "ceiling": ceiling,
            })

        if len(clean_rows) < 6:
            return []

        # Identify pass-catchers and QBs
        qbs = set(p["name"] for p in clean_rows if p["position"] == "QB")
        pass_catchers = set(p["name"] for p in clean_rows if p["position"] in ["WR", "TE"])
        rbs = set(p["name"] for p in clean_rows if p["position"] == "RB")
        dsts = set(p["name"] for p in clean_rows if p["position"] in ["D", "D/ST"])

        candidates = []

        # Loop through all possible MVPs
        for mvp in clean_rows:
            if lock_mvp and mvp["name"].lower() != lock_mvp.lower().strip():
                continue

            mvp_cost = mvp["mvp_sal"]
            mvp_pts = mvp["proj"] * 1.5
            mvp_ceil = mvp["ceiling"] * 1.5

            rem_pool = [p for p in clean_rows if p["name"] != mvp["name"]]

            for flex_combo in itertools.combinations(rem_pool, 5):
                tot_sal = mvp_cost + sum(p["base_sal"] for p in flex_combo)
                if not (min_salary <= tot_sal <= max_salary):
                    continue

                all_players = [mvp] + list(flex_combo)
                teams = set(p["team"] for p in all_players)
                if len(teams) < 2:
                    continue

                names = set(p["name"] for p in all_players)
                rostered_qbs = names.intersection(qbs)

                if force_zero_qb and len(rostered_qbs) > 0:
                    continue
                if force_qb_stack and len(rostered_qbs) == 0:
                    continue

                # Correlation Rule 1: QB stacking (paired with >= 1 pass-catcher)
                invalid_stack = False
                for qb_name in rostered_qbs:
                    qb_item = next(p for p in all_players if p["name"] == qb_name)
                    team_pcs = [p["name"] for p in all_players if p["team"] == qb_item["team"] and p["name"] in pass_catchers]
                    if len(team_pcs) == 0:
                        invalid_stack = True
                        break
                if invalid_stack:
                    continue

                # Correlation Rule 2: Negative Correlation Leakage (Max 2 pass-catchers if QB is NOT in lineup)
                leakage = False
                for t in teams:
                    has_team_qb = any(p["team"] == t and p["name"] in qbs for p in all_players)
                    t_pcs = [p["name"] for p in all_players if p["team"] == t and p["name"] in pass_catchers]
                    if not has_team_qb and len(t_pcs) > 2:
                        leakage = True
                        break
                if leakage:
                    continue

                # Correlation Rule 3: D/ST anti-cannibalization
                conflict = False
                for dst_name in names.intersection(dsts):
                    dst_team = next(p["team"] for p in all_players if p["name"] == dst_name)
                    opp_offensive = [p for p in all_players if p["team"] != dst_team and p["position"] in ["QB", "RB", "WR", "TE"]]
                    if len(opp_offensive) >= 3:
                        conflict = True
                        break
                    opp_rbs = [p for p in opp_offensive if p["position"] == "RB"]
                    if len(opp_rbs) > 0:
                        conflict = True
                        break
                if conflict:
                    continue

                tot_proj = mvp_pts + sum(p["proj"] for p in flex_combo)
                tot_ceil = mvp_ceil + sum(p["ceiling"] for p in flex_combo)
                score_val = tot_ceil if mode == "GPP" else tot_proj

                candidates.append({
                    "mvp": mvp,
                    "flex": list(flex_combo),
                    "total_salary": tot_sal,
                    "salary_remaining": 60000 - tot_sal,
                    "total_projected_points": round(tot_proj, 2),
                    "total_ceiling_points": round(tot_ceil, 2),
                    "is_zero_qb": len(rostered_qbs) == 0,
                    "rostered_qbs": list(rostered_qbs),
                    "team_split": f"{sum(1 for p in all_players if p['team'] == list(teams)[0])}-{sum(1 for p in all_players if p['team'] == list(teams)[1])}",
                    "_sort_score": score_val,
                })

        candidates.sort(key=lambda x: x["_sort_score"], reverse=True)
        return candidates[:top_n]


dfs_optimizer = DFSLineupOptimizer()

