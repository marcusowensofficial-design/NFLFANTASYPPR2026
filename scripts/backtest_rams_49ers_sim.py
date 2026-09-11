"""Blind backtest of yesterday's Rams vs 49ers Showdown Slate using Market-Anchored Monte Carlo Simulation."""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.simulation import nfl_simulator
from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer


def main():
    csv_path = "data/SINGLEGAMESLATE.csv"
    print("=" * 85)
    print(f"RUNNING 10,000 MONTE CARLO SIMULATIONS ON {csv_path}")
    print("Market-Anchored Gaussian Copula & Cholesky Correlation Structure")
    print("=" * 85)

    df_slate = pd.read_csv(csv_path)
    print(f"Loaded {len(df_slate)} players from slate CSV.")

    # Run 10,000 full game simulations
    df_sim = nfl_simulator.simulate_slate(df_slate, num_sims=10000, random_seed=42)

    # Display Top 15 players by Simulated Ceiling and MVP Share
    print("\n--- SIMULATION DISTRIBUTION RESULTS (TOP 15 CEILINGS) ---")
    cols_to_show = [
        "name", "team", "position", "salary", 
        "sim_floor_fd", "sim_median_fd", "sim_ceiling_fd", 
        "sim_mvp_share_pct", "sim_ceiling_ppr"
    ]
    df_top = df_sim.sort_values(by="sim_ceiling_fd", ascending=False).head(15)
    print(f"{'Player Name':<22} | {'Tm':<3} {'Pos':<3} | {'Salary':<7} | {'Floor':<5} | {'Median':<6} | {'Ceiling':<7} | {'MVP Share %':<11} | {'ESPN PPR Ceil':<13}")
    print("-" * 95)
    for _, r in df_top.iterrows():
        print(f"{r['name']:<22} | {r['team']:<3} {r['position']:<3} | ${r['salary']:<6} | {r['sim_floor_fd']:<5.1f} | {r['sim_median_fd']:<6.1f} | {r['sim_ceiling_fd']:<7.1f} | {r['sim_mvp_share_pct']:<11.1f}% | {r['sim_ceiling_ppr']:<13.1f}")

    print("\n" + "=" * 85)
    print("FEEDING SIMULATED CEILINGS INTO KNAPSACK SHOWDOWN OPTIMIZER")
    print("Enforcing: Max Spend $59,800 ($200+ buffer) & Punt Floor >= $3,500")
    print("=" * 85)

    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=59800,  # leaves buffer
        min_salary=58500,
        min_punt_salary=3500,  # bans zero-point punts
    )

    all_scripts = optimizer.generate_all_scripts(df_sim, mode="GPP", allow_sub3500_punts=False)

    for script_id, sol in all_scripts.items():
        print(f"\n>>> {sol['script_name'].upper()} <<<")
        print(f"Total Salary: ${sol['total_salary']:,} / $60,000  (Buffer: ${sol['unspent_buffer']:,} unspent)")
        print(f"Sim Projected Pts: {sol['total_projected_pts']:.1f} | Sim 90th Ceiling: {sol['total_ceiling_pts']:.1f}")
        print(f"Team Breakdown: {sol['team_counts']}")
        mvp = sol["mvp"]
        print(f"  [MVP (1.5x)] {mvp['name']:<20} | {mvp['team']} {mvp['position']} | Cost: ${mvp['effective_salary']:,} (Base: ${mvp['salary']:,}) | Sim Ceiling: {mvp['effective_ceiling']:.1f}")
        for i, f in enumerate(sol["flex"], 1):
            print(f"  [FLEX {i}]    {f['name']:<20} | {f['team']} {f['position']} | Cost: ${f['salary']:,}              | Sim Ceiling: {f['effective_ceiling']:.1f}")

    print("\n" + "=" * 85)
    print("HISTORICAL VALIDATION: COMPARING AGAINST ACTUAL $7,500 1ST PLACE WINNER")
    print("=" * 85)
    winner_players = ["Brock Purdy", "Christian McCaffrey", "Kyren Williams", "Deebo Samuel Sr.", "Eddy Pineiro", "Demarcus Robinson"]
    winner_df = df_sim[df_sim["name"].isin(winner_players)]
    print("Winning Lineup Simulated Scores:")
    for _, r in winner_df.iterrows():
        print(f"  - {r['name']:<22} | Sim Median: {r['sim_median_fd']:<5.1f} | Sim Ceiling: {r['sim_ceiling_fd']:<5.1f} | MVP Share: {r['sim_mvp_share_pct']:.1f}%")


if __name__ == "__main__":
    main()
