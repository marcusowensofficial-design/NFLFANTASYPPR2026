"""Test and verify the FanDuelShowdownOptimizer against SINGLEGAMESLATE.csv."""

import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer


def main():
    csv_path = Path("data/SINGLEGAMESLATE.csv")
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} players from {csv_path}")

    # Set realistic projections based on FPPG
    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=59800,  # leaves >= $200 unspent buffer
        min_salary=58500,
        min_punt_salary=3500,
    )

    print("\n==========================================")
    print("RUNNING ALL SCRIPTS MULTI-SCENARIO SOLVER")
    print("==========================================")
    all_scripts = optimizer.generate_all_scripts(df, mode="GPP", allow_sub3500_punts=False)

    for script_id, sol in all_scripts.items():
        print(f"\n--- {sol['script_name']} ({script_id}) ---")
        print(f"Total Salary: ${sol['total_salary']:,} | Buffer: ${sol['unspent_buffer']:,} unspent")
        print(f"Projected Pts: {sol['total_projected_pts']} | Ceiling Pts: {sol['total_ceiling_pts']}")
        print(f"Team Breakdown: {sol['team_counts']}")
        print(f"MVP (1.5x): {sol['mvp']['name']} ({sol['mvp']['team']} {sol['mvp']['position']}) - Base ${sol['mvp']['salary']:,} (Cost ${sol['mvp']['effective_salary']:,})")
        print("AnyFLEX:")
        for p in sol["flex"]:
            print(f"  - {p['name']} ({p['team']} {p['position']}) - ${p['salary']:,} (Proj: {p['proj']})")

    print("\n==========================================")
    print("TESTING BACKTEST: WHAT IF BROCK PURDY 3-TD CEILING IS APPLIED?")
    print("==========================================")
    # Give Purdy a 3-TD ceiling simulation (24.0 ceiling)
    df_sim = df.copy()
    purdy_mask = df_sim["Nickname"] == "Brock Purdy"
    df_sim.loc[purdy_mask, "ceiling_proj"] = 28.0
    df_sim.loc[purdy_mask, "proj"] = 22.0

    sol_purdy = optimizer.solve(
        df_sim,
        mode="GPP",
        script="TEAM_A_DOMINANT",  # Team A is SF
        allow_sub3500_punts=False,
    )
    if sol_purdy:
        print(f"Simulation Solution with Purdy Ceiling Boost:")
        print(f"MVP: {sol_purdy['mvp']['name']} (Effective Cost: ${sol_purdy['mvp']['effective_salary']:,})")
        print(f"FLEX: {[p['name'] + ' ($' + str(p['salary']) + ')' for p in sol_purdy['flex']]}")
        print(f"Total Salary: ${sol_purdy['total_salary']:,} | Unspent: ${sol_purdy['unspent_buffer']:,}")


if __name__ == "__main__":
    main()
