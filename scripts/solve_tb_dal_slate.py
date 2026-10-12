"""Dedicated Championship Solver and Single-Entry Optimizer for TB @ DAL Showdown Slate.

Week 5 - Thursday Night Football - October 8, 2026 - AT&T Stadium (Arlington, TX - Dome)
Vegas Line: DAL -8.5 | O/U 48.5 (Implied: DAL 28.5, TB 20.0)
Format: FanDuel Single Game (1 MVP at 1.5x salary/pts + 5 AnyFLEX, $60,000 cap)
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
    """Loads CSV and enriches with calibrated Half-PPR projections based on McClure pro exposures and quant models."""
    csv_path = Path("data/DallascowboysvsTampabaybucs10-8-26singlegameslatesalaries.csv")
    df = pd.read_csv(csv_path)

    df["name"] = df["Nickname"].str.strip()
    df["salary"] = df["Salary"].astype(int)
    df["position"] = df["Position"].str.strip()
    df["team"] = df["Team"].str.strip()
    df["opponent"] = df["Opponent"].str.strip()

    # Calibrated projections blending Mike McClure's high-priority exposures and internal NextGen Quant models:
    calibrated_stats = {
        "Dak Prescott": {
            "proj": 22.32, "quant": 20.52, "ceiling": 33.48, "floor": 16.50,
            "role": "Starting QB1 (Dome home favorite, DAL -8.5, 28.5 implied)",
            "route_pct": 1.00, "verified_starter": True, "mcclure_mvp": 0.36, "mcclure_flex": 0.58
        },
        "Jalon Daniels": {
            "proj": 18.50, "quant": 17.35, "ceiling": 27.75, "floor": 11.00,
            "role": "Starting QB1 (Rookie 2nd start, mobile scrambler, trailing script)",
            "route_pct": 1.00, "verified_starter": True, "mcclure_mvp": 0.28, "mcclure_flex": 0.56
        },
        "CeeDee Lamb": {
            "proj": 17.38, "quant": 15.49, "ceiling": 32.50, "floor": 10.00,
            "role": "Alpha WR1 (31% target share, 87% route win rate, 17 rec last game)",
            "route_pct": 0.88, "verified_starter": True, "mcclure_mvp": 0.06, "mcclure_flex": 0.46
        },
        "Javonte Williams": {
            "proj": 17.00, "quant": 15.08, "ceiling": 28.50, "floor": 9.50,
            "role": "Bellcow RB1 (70% inside-5 carry share, 5 rushing TDs, 19 car 3 TDs last game)",
            "route_pct": 0.46, "verified_starter": True, "mcclure_mvp": 0.16, "mcclure_flex": 0.50
        },
        "George Pickens": {
            "proj": 14.00, "quant": 12.30, "ceiling": 24.50, "floor": 7.00,
            "role": "Starting WR2 (26% target share, boundary separator vs single-high MOFC)",
            "route_pct": 0.82, "verified_starter": True, "mcclure_mvp": 0.04, "mcclure_flex": 0.44
        },
        "Bucky Irving": {
            "proj": 13.50, "quant": 14.19, "ceiling": 26.20, "floor": 7.50,
            "role": "Bellcow RB1 (72% inside-5 carry share, 70% snap share, 3.75 YAC/att)",
            "route_pct": 0.58, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.26
        },
        "Brandon Aubrey": {
            "proj": 11.00, "quant": 9.20, "ceiling": 17.00, "floor": 6.00,
            "role": "Starting K (Dome kicker, 10.25 FPPG, McCarthy 1.15 kicker multiplier)",
            "route_pct": 0.00, "verified_starter": True, "mcclure_mvp": 0.02, "mcclure_flex": 0.42
        },
        "Emeka Egbuka": {
            "proj": 8.50, "quant": 10.22, "ceiling": 20.20, "floor": 4.00,
            "role": "Starting WR1/Slot (26% target share, 83% route win rate)",
            "route_pct": 0.78, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.12
        },
        "Chase McLaughlin": {
            "proj": 8.22, "quant": 7.80, "ceiling": 14.00, "floor": 4.00,
            "role": "Starting K (10.25 FPPG, Bowles 1.18 kicker multiplier)",
            "route_pct": 0.00, "verified_starter": True, "mcclure_mvp": 0.04, "mcclure_flex": 0.22
        },
        "Jake Ferguson": {
            "proj": 8.20, "quant": 7.23, "ceiling": 15.00, "floor": 4.00,
            "role": "Starting TE1 (65% route participation)",
            "route_pct": 0.65, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.10
        },
        "Chris Godwin Jr.": {
            "proj": 8.00, "quant": 7.85, "ceiling": 16.00, "floor": 4.00,
            "role": "Starting WR2/Slot (25% target share, 72% route participation)",
            "route_pct": 0.72, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.02
        },
        "Dallas Cowboys": {
            "proj": 7.82, "quant": 7.60, "ceiling": 15.00, "floor": 2.00,
            "role": "Cowboys D/ST (Home favorite facing rookie QB in 2nd start)",
            "route_pct": 0.00, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.32
        },
        "Ryan Flournoy": {
            "proj": 7.70, "quant": 5.19, "ceiling": 14.00, "floor": 3.00,
            "role": "Starting WR3 (52% route participation, 24% first-read share, McClure Top Value)",
            "route_pct": 0.52, "verified_starter": True, "mcclure_mvp": 0.04, "mcclure_flex": 0.24
        },
        "Cade Otton": {
            "proj": 6.80, "quant": 7.04, "ceiling": 14.50, "floor": 3.50,
            "role": "Starting TE1 (75% route participation, Daniels safety blanket)",
            "route_pct": 0.75, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.12
        },
        "Ted Hurst III": {
            "proj": 6.00, "quant": 4.82, "ceiling": 11.00, "floor": 2.00,
            "role": "Starting WR3 (45% route participation, 14% target share)",
            "route_pct": 0.45, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.06
        },
        "Kenny Gainwell": {
            "proj": 5.50, "quant": 8.54, "ceiling": 12.00, "floor": 1.50,
            "role": "Backup RB2 (30% snap share)",
            "route_pct": 0.30, "verified_starter": False, "mcclure_mvp": 0.00, "mcclure_flex": 0.06
        },
        "Tampa Bay Buccaneers": {
            "proj": 5.00, "quant": 5.50, "ceiling": 11.00, "floor": 0.00,
            "role": "Bucs D/ST (Road dog vs top offense, Winfield/Dennis/Morrison OUT)",
            "route_pct": 0.00, "verified_starter": True, "mcclure_mvp": 0.00, "mcclure_flex": 0.04
        },
        "Sean Tucker": {
            "proj": 4.50, "quant": 6.13, "ceiling": 10.00, "floor": 0.50,
            "role": "Rotational RB3 (10% snap share)",
            "route_pct": 0.10, "verified_starter": False, "mcclure_mvp": 0.00, "mcclure_flex": 0.08
        },
        "Tyler Goodson": {
            "proj": 4.00, "quant": 4.50, "ceiling": 9.00, "floor": 1.00,
            "role": "Backup RB2 (30% snap share behind Javonte)",
            "route_pct": 0.30, "verified_starter": False, "mcclure_mvp": 0.00, "mcclure_flex": 0.10
        },
        "Tez Johnson": {
            "proj": 4.00, "quant": 4.00, "ceiling": 8.00, "floor": 1.00,
            "role": "Backup WR4 (25% route participation)",
            "route_pct": 0.25, "verified_starter": False, "mcclure_mvp": 0.00, "mcclure_flex": 0.06
        },
        "KaVontae Turpin": {
            "proj": 3.50, "quant": 7.69, "ceiling": 15.20, "floor": 0.50,
            "role": "Gadget/Returner WR4 (22% route participation)",
            "route_pct": 0.22, "verified_starter": False, "mcclure_mvp": 0.00, "mcclure_flex": 0.02
        },
    }

    # Map calibrated values
    df["proj"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("proj", 0.0))
    df["quant_proj"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("quant", 0.0))
    df["ceiling_proj"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("ceiling", df.loc[df["name"] == n, "proj"].values[0] * 1.35 if not df.loc[df["name"] == n, "proj"].empty else 0.0))
    df["floor_proj"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("floor", 0.5))
    df["route_pct"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("route_pct", 0.0))
    df["verified_starter"] = df["name"].map(lambda n: calibrated_stats.get(n, {}).get("verified_starter", False))

    # Hybrid consensus projection (50% McClure + 50% Quant)
    df["hybrid_proj"] = np.where(df["quant_proj"] > 0, 0.5 * df["proj"] + 0.5 * df["quant_proj"], df["proj"])

    return df


def solve_optimal_single_entry() -> dict:
    """Executes integer programming to find the exact #1 Single-Entry Tournament Lineup."""
    df = build_calibrated_player_pool()

    # Rule 2 / Rule 4: Disqualify non-viable rotational ghost punts
    # Only allow verified starters or skill players with >= 35% route participation
    viable_mask = (df["verified_starter"] == True) | (df["route_pct"] >= 0.35)
    df_viable = df[viable_mask].copy()

    # Salary cap $60k with $200-$1,000 unspent buffer for 48.5 O/U ($59,000 - $59,800 spent)
    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=59800,  # leaves >= $200
        min_salary=59000,  # leaves <= $1,000
        min_punt_salary=3000,
    )

    scripts = optimizer.generate_all_scripts(
        df_viable,
        mode="GPP",
        allow_sub3500_punts=False,
    )

    return scripts


if __name__ == "__main__":
    print("\n" + "=" * 90)
    print("FANDUEL SINGLE-GAME CHAMPIONSHIP SOLVER: TB @ DAL (OCTOBER 8, 2026)")
    print("Vegas: DAL -8.5 | O/U 48.5 | Implied: DAL 28.5, TB 20.0 | Dome: AT&T Stadium")
    print("=" * 90)

    scripts = solve_optimal_single_entry()

    for script_id, sol in scripts.items():
        mvp = sol["mvp"]
        flex_players = sol["flex"]
        print(f"\n[{sol['script_name']}]")
        print(f"Total Salary: ${sol['total_salary']:,} / $60,000 | Unspent Buffer: ${sol['unspent_buffer']:,}")
        print(f"Projected Median: {sol['total_projected_pts']:.2f} FP | Ceiling: {sol['total_ceiling_pts']:.2f} FP")
        print(f"Roster Stacking: {sol['team_counts']}")
        print("-" * 90)
        print(f"  [MVP (1.5x)] {mvp['name']:<20} | {mvp['team']} {mvp['position']:<3} | Base: ${mvp['salary']:,} (${mvp['effective_salary']:,}) | Proj: {mvp['effective_pts']:.2f} FP")
        print("-" * 90)
        for i, f in enumerate(flex_players, 1):
            print(f"  [FLEX {i}]   {f['name']:<20} | {f['team']} {f['position']:<3} | Base: ${f['salary']:,}            | Proj: {f['effective_pts']:.2f} FP")
        print("-" * 90)
