"""Comprehensive Championship Solver and Monte Carlo Simulator for DET @ BUF Showdown Slate.

Week 2 - September 17, 2026 - Highmark Stadium
Vegas Line: BUF -4.5 | O/U 54.5 (Implied: BUF 29.5, DET 25.0)
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import LinearConstraint, milp

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer


def build_calibrated_player_pool() -> pd.DataFrame:
    """Loads CSV and enriches with calibrated Half-PPR projections based on props and forensics."""
    csv_path = Path("data/detvsbuffalosinglegameslaterostersnsalaries.csv")
    df = pd.read_csv(csv_path)

    # Clean standardized column names
    df["name"] = df["Nickname"].str.strip()
    df["salary"] = df["Salary"].astype(int)
    df["position"] = df["Position"].str.strip()
    df["team"] = df["Team"].str.strip()
    df["opponent"] = df["Opponent"].str.strip()

    # Calibrated Median Projections (Half-PPR) grounded in sportsbook props & Week 1 utilization:
    # Vegas: 54.5 O/U, BUF 29.5, DET 25.0
    calibrated_stats = {
        "Josh Allen": {"proj": 23.50, "ceiling": 39.50, "floor": 16.50, "verified_starter": True},
        "Jahmyr Gibbs": {"proj": 23.20, "ceiling": 38.00, "floor": 16.00, "verified_starter": True},
        "Amon-Ra St. Brown": {"proj": 18.50, "ceiling": 30.00, "floor": 12.00, "verified_starter": True},
        "Jared Goff": {"proj": 17.20, "ceiling": 25.50, "floor": 11.50, "verified_starter": True},
        "James Cook III": {"proj": 14.80, "ceiling": 23.50, "floor": 8.50, "verified_starter": True},
        "DJ Moore": {"proj": 12.50, "ceiling": 24.00, "floor": 7.00, "verified_starter": True},
        "Jameson Williams": {"proj": 10.50, "ceiling": 20.00, "floor": 4.50, "verified_starter": True},
        "Sam LaPorta": {"proj": 10.20, "ceiling": 19.50, "floor": 5.50, "verified_starter": True},
        "Dalton Kincaid": {"proj": 10.00, "ceiling": 21.00, "floor": 5.00, "verified_starter": True},
        "Tyler Bass": {"proj": 9.20, "ceiling": 15.00, "floor": 4.00, "verified_starter": True},
        "Jake Bates": {"proj": 8.50, "ceiling": 14.00, "floor": 4.00, "verified_starter": True},
        "Khalil Shakir": {"proj": 8.50, "ceiling": 16.00, "floor": 4.50, "verified_starter": True},
        "Buffalo Bills": {"proj": 5.20, "ceiling": 12.00, "floor": 0.00, "verified_starter": True},
        "Detroit Lions": {"proj": 5.00, "ceiling": 12.00, "floor": 0.00, "verified_starter": True},
        "Keon Coleman": {"proj": 4.20, "ceiling": 11.00, "floor": 1.00, "verified_starter": True, "active_role": True},
        "Joshua Palmer": {"proj": 3.20, "ceiling": 12.00, "floor": 0.50, "verified_starter": True, "active_role": True},
        "Sione Vaki": {"proj": 2.80, "ceiling": 7.50, "floor": 0.50, "verified_starter": False, "active_role": False},
        "Isaac TeSlaa": {"proj": 1.80, "ceiling": 6.50, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Ray Davis": {"proj": 2.00, "ceiling": 6.00, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Dawson Knox": {"proj": 2.20, "ceiling": 7.00, "floor": 0.00, "verified_starter": False, "active_role": True},
        "Ty Johnson": {"proj": 2.00, "ceiling": 6.00, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Greg Dortch": {"proj": 0.50, "ceiling": 3.00, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Brock Wright": {"proj": 1.20, "ceiling": 5.00, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Frank Gore Jr.": {"proj": 1.00, "ceiling": 4.00, "floor": 0.00, "verified_starter": False, "active_role": False},
        "Tyler Conklin": {"proj": 1.20, "ceiling": 5.00, "floor": 0.00, "verified_starter": False, "active_role": False},
    }

    df["proj"] = df["name"].map(lambda x: calibrated_stats.get(x, {}).get("proj", 0.0))
    df["ceiling_proj"] = df["name"].map(lambda x: calibrated_stats.get(x, {}).get("ceiling", 0.0))
    df["floor_proj"] = df["name"].map(lambda x: calibrated_stats.get(x, {}).get("floor", 0.0))
    df["verified_starter"] = df["name"].map(lambda x: calibrated_stats.get(x, {}).get("verified_starter", False))
    df["active_role"] = df["name"].map(lambda x: calibrated_stats.get(x, {}).get("active_role", False))

    return df


def solve_all_slate_scripts():
    print("=" * 80)
    print("DETROIT LIONS @ BUFFALO BILLS | FANDUEL SINGLE-GAME CHAMPIONSHIP SOLVER")
    print("Week 2 (9/17/2026) | Vegas: BUF -4.5 | O/U 54.5 (Implied: BUF 29.5, DET 25.0)")
    print("Salary Cap: $60,000 | Dynamic High-Total Buffer: $200 - $1,000 Unspent")
    print("Verified Role Punt Floor: >= $3,000 or Active Rotational Asset")
    print("=" * 80)

    df_pool = build_calibrated_player_pool()

    # Filter out backup QBs & unverified zero-opportunity punts
    df_clean = df_pool[
        ((df_pool["salary"] >= 3000) | (df_pool["verified_starter"] == True) | (df_pool["active_role"] == True)) & 
        (~df_pool["name"].isin(["Kyle Allen", "Joshua Dobbs", "Shane Buechele", "Luke Altmyer"]))
    ].copy().reset_index(drop=True)

    print(f"\nViable Player Pool ({len(df_clean)} players):")
    print(df_clean[["name", "team", "position", "salary", "proj", "ceiling_proj"]].to_string(index=False))

    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=59800,  # leaves >= $200 unspent
        min_salary=59000,  # leaves <= $1,000 unspent for high total (54.5 O/U)
        min_punt_salary=3000,
    )

    scripts = {
        "OPTIMAL": "Pure MILP Optimal (GPP Ceiling)",
        "TEAM_A_DOMINANT": "Script 1: Buffalo Pass-Heavy Dominant (4-2 BUF)",
        "TEAM_B_DOMINANT": "Script 2: Detroit Gibbs Ground & Air Assault (4-2 DET)",
        "BALANCED": "Script 3: Shootout Balanced War (3-3 / 4-2)",
        "ZERO_QB": "Script 4: Zero-QB Touchdown Monopoly",
        "DUAL_QB": "Script 5: Dual-QB Shootout Baseline Floor",
    }

    results = {}
    for script_id, script_name in scripts.items():
        sol = optimizer.solve(
            df_clean,
            mode="GPP",
            script=script_id,
            allow_sub3500_punts=True,
            enforce_qb_rules=True,
            enforce_dst_rules=True,
        )
        if sol:
            results[script_id] = sol
            print(f"\n{'='*30} {script_name.upper()} {'='*30}")
            print(f"Total Spent: ${sol['total_salary']:,} / $60,000 | Unspent Buffer: ${sol['unspent_buffer']:,}")
            print(f"Projected Median: {sol['total_projected_pts']:.2f} | 90th Ceiling: {sol['total_ceiling_pts']:.2f}")
            print(f"Team Breakdown: {sol['team_counts']}")
            print("-" * 80)
            mvp = sol["mvp"]
            print(f"[MVP (1.5x)] {mvp['name']:<22} | {mvp['team']:<4} {mvp['position']:<3} | Base: ${mvp['salary']:,} (Cost: ${mvp['effective_salary']:,}) | Proj: {mvp['effective_pts']:.1f}")
            print("-" * 80)
            for i, f in enumerate(sol["flex"], 1):
                print(f"[FLEX {i}]    {f['name']:<22} | {f['team']:<4} {f['position']:<3} | Cost: ${f['salary']:,}              | Proj: {f['effective_pts']:.1f}")
            print("-" * 80)

    # Now generate the 5-lineup balanced tournament portfolio with exposure caps
    print("\n" + "=" * 80)
    print("AUTOMATED 5-LINEUP DIVERSIFIED TOURNAMENT PORTFOLIO (MAX 50% FLEX EXPOSURE)")
    print("=" * 80)
    port = optimizer.generate_portfolio(
        df_clean,
        num_lineups=5,
        max_flex_exposure=0.50,
        game_total=54.5,
        mode="GPP",
        allow_sub3500_punts=True,
    )

    for sol in port["lineups"]:
        print(f"\n{'='*25} PORTFOLIO LINEUP {sol['lineup_num']} [{sol['script_id']}] {'='*25}")
        print(f"Total Salary: ${sol['total_salary']:,} / $60,000 | Unspent Buffer: ${sol['unspent_buffer']:,}")
        print(f"Projected Median: {sol['total_projected_pts']:.2f} | 90th Ceiling: {sol['total_ceiling_pts']:.2f}")
        print(f"Team Breakdown: {sol['team_counts']}")
        print("-" * 80)
        mvp = sol["mvp"]
        print(f"[MVP (1.5x)] {mvp['name']:<22} | {mvp['team']:<4} {mvp['position']:<3} | Base: ${mvp['salary']:,} (Cost: ${mvp['effective_salary']:,}) | Proj: {mvp['effective_pts']:.1f}")
        print("-" * 80)
        for i, f in enumerate(sol["flex"], 1):
            print(f"[FLEX {i}]    {f['name']:<22} | {f['team']:<4} {f['position']:<3} | Cost: ${f['salary']:,}              | Proj: {f['effective_pts']:.1f}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("PORTFOLIO EXPOSURE REPORT")
    print("=" * 80)
    print(port["exposures"].to_string(index=False))
    print("=" * 80 + "\n")

    return results, port, df_clean


if __name__ == "__main__":
    solve_all_slate_scripts()
