#!/usr/bin/env python3
"""CLI runner for FanDuel Single-Game (Showdown) MILP Optimizer.

Usage:
  python scripts/run_showdown_optimizer.py --slate data/SINGLEGAMESLATE.csv
  python scripts/run_showdown_optimizer.py --slate data/SINGLEGAMESLATE.csv --mode GPP --min-buffer 200 --max-buffer 900
"""

import argparse
import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer


def run_optimizer(
    slate_path: str,
    mode: str = "GPP",
    vegas_total: float | None = None,
    min_buffer: int | None = None,
    max_buffer: int | None = None,
    min_punt_salary: int = 3000,
    allow_sub3500_punts: bool = True,
    lock_mvp: str | None = None,
    lock_players: list[str] | None = None,
    exclude_players: list[str] | None = None,
    portfolio_size: int | None = None,
    max_exposure: float = 0.50,
):
    path = Path(slate_path)
    if not path.exists():
        print(f"Error: Slate file not found at {slate_path}")
        sys.exit(1)

    df = pd.read_csv(path)
    print(f"Loaded {len(df)} players from {slate_path}")

    # Dynamic Vegas total calibration
    if vegas_total is not None:
        if vegas_total <= 42.0:
            calibrated_min_buf = 1500 if min_buffer is None else min_buffer
            calibrated_max_buf = 3500 if max_buffer is None else max_buffer
        elif vegas_total <= 46.5:
            calibrated_min_buf = 800 if min_buffer is None else min_buffer
            calibrated_max_buf = 2500 if max_buffer is None else max_buffer
        else:
            calibrated_min_buf = 200 if min_buffer is None else min_buffer
            calibrated_max_buf = 1000 if max_buffer is None else max_buffer
    else:
        calibrated_min_buf = 200 if min_buffer is None else min_buffer
        calibrated_max_buf = 2500 if max_buffer is None else max_buffer

    max_salary = 60000 - calibrated_min_buf
    min_salary = 60000 - calibrated_max_buf

    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=max_salary,
        min_salary=min_salary,
        min_punt_salary=min_punt_salary,
    )

    print("\n" + "=" * 80)
    print(f"FANDUEL SINGLE-GAME SOLVER | MODE: {mode}")
    if vegas_total is not None:
        print(f"Vegas Game Total: {vegas_total} O/U (Calibrated Buffer: ${calibrated_min_buf}-${calibrated_max_buf})")
    print(f"Salary Cap: $60,000 | Allowed Spend: ${min_salary:,} - ${max_salary:,} (${calibrated_min_buf}-${calibrated_max_buf} buffer)")
    print(f"Punt Floor: >= ${min_punt_salary:,} (Route/Role viability enforced)")
    if portfolio_size:
        print(f"Multi-Entry Portfolio: Generating {portfolio_size} Lineups (Max Flex Exposure: {int(max_exposure*100)}%)")
    print("=" * 80)

    # If portfolio generation is requested
    if portfolio_size:
        port = optimizer.generate_portfolio(
            df,
            num_lineups=portfolio_size,
            max_flex_exposure=max_exposure,
            game_total=vegas_total,
            mode=mode,
            allow_sub3500_punts=allow_sub3500_punts,
            exclude_players=exclude_players,
        )

        for sol in port["lineups"]:
            print(f"\n{'='*30} LINEUP {sol['lineup_num']} [{sol['script_id']}] {'='*30}")
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
        print("PORTFOLIO EXPOSURE DISTRIBUTION")
        print("=" * 80)
        print(port["exposures"].to_string(index=False))
        print("=" * 80 + "\n")
        return

    all_scripts = optimizer.generate_all_scripts(
        df,
        mode=mode,
        allow_sub3500_punts=allow_sub3500_punts,
        lock_mvp=lock_mvp,
        lock_players=lock_players,
        exclude_players=exclude_players,
    )

    if not all_scripts:
        print("No valid lineups could be generated with the given constraints.")
        return

    for script_id, sol in all_scripts.items():
        print(f"\n{'='*30} {sol['script_name'].upper()} {'='*30}")
        print(f"Script ID: {script_id}")
        print(f"Total Salary Spent: ${sol['total_salary']:,} / $60,000  (Buffer: ${sol['unspent_buffer']:,} unspent)")
        print(f"Projected Pts: {sol['total_projected_pts']} | Ceiling Pts: {sol['total_ceiling_pts']}")
        print(f"Team Breakdown: {sol['team_counts']}")
        print("-" * 80)
        
        # MVP Slot
        mvp = sol["mvp"]
        print(f"[MVP (1.5x)]  {mvp['name']:<22} | {mvp['team']:<4} {mvp['position']:<3} | Base: ${mvp['salary']:,} (Cost: ${mvp['effective_salary']:,}) | Proj: {mvp['effective_pts']:.1f}")
        
        # AnyFLEX Slots
        print("-" * 80)
        for i, f in enumerate(sol["flex"], 1):
            print(f"[FLEX {i}]     {f['name']:<22} | {f['team']:<4} {f['position']:<3} | Cost: ${f['salary']:,}              | Proj: {f['effective_pts']:.1f}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("STRESS-TEST COMPARISON SUMMARY")
    print("=" * 80)
    print(f"{'Script Name':<35} | {'MVP':<20} | {'Salary':<8} | {'Buffer':<8} | {'Ceiling':<8}")
    print("-" * 80)
    for script_id, sol in all_scripts.items():
        print(f"{sol['script_name']:<35} | {sol['mvp']['name']:<20} | ${sol['total_salary']:<7} | ${sol['unspent_buffer']:<7} | {sol['total_ceiling_pts']:<8}")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="FanDuel Showdown MILP Optimizer")
    parser.add_argument("--slate", type=str, default="data/SINGLEGAMESLATE.csv", help="Path to single-game slate CSV")
    parser.add_argument("--mode", type=str, default="GPP", choices=["GPP", "CASH"], help="Optimization mode")
    parser.add_argument("--vegas-total", type=float, default=None, help="Vegas Over/Under total for dynamic buffer calibration")
    parser.add_argument("--min-buffer", type=int, default=None, help="Minimum unspent salary buffer ($)")
    parser.add_argument("--max-buffer", type=int, default=None, help="Maximum unspent salary buffer ($)")
    parser.add_argument("--min-punt", type=int, default=3000, help="Minimum punt salary ($)")
    parser.add_argument("--allow-sub3500", action="store_true", default=True, help="Allow viable sub-$3,500 punts")
    parser.add_argument("--lock-mvp", type=str, default=None, help="Lock specific player at MVP")
    parser.add_argument("--lock", nargs="+", default=None, help="Lock players into roster")
    parser.add_argument("--exclude", nargs="+", default=None, help="Exclude players from roster")
    parser.add_argument("--portfolio", type=int, default=None, help="Generate a multi-lineup portfolio (e.g. 5 or 20 entries)")
    parser.add_argument("--max-exposure", type=float, default=0.50, help="Max exposure for non-QB players in portfolio (0.0 - 1.0)")

    args = parser.parse_args()
    run_optimizer(
        slate_path=args.slate,
        mode=args.mode,
        vegas_total=args.vegas_total,
        min_buffer=args.min_buffer,
        max_buffer=args.max_buffer,
        min_punt_salary=args.min_punt,
        allow_sub3500_punts=args.allow_sub3500,
        lock_mvp=args.lock_mvp,
        lock_players=args.lock,
        exclude_players=args.exclude,
        portfolio_size=args.portfolio,
        max_exposure=args.max_exposure,
    )


if __name__ == "__main__":
    main()

