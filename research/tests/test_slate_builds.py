import os
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.solve_main_slate_matrix import load_and_enrich_slate, solve_tournament_matrix

def run_tests():
    csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
    df, vegas_games = load_and_enrich_slate(csv_path)

    print("\n" + "="*60)
    print("TESTING MATRIX COMBINATIONS FOR 9/27/2026 MAIN SLATE")
    print("="*60)

    # Scenarios to test:
    # 1. Primary: LAC @ BUF (Josh Allen rushing ceiling)
    # 2. Primary: BAL @ DAL (JerryWorld Lamar Jackson / Dak Prescott shootout)
    # 3. Primary: NYJ @ DET (Jared Goff / Amon-Ra St. Brown dome engine)

    scenarios = [
        {
            "name": "Scenario 1: LAC @ BUF Primary (Josh Allen Anchor)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "CLE"
        },
        {
            "name": "Scenario 1B: LAC @ BUF Primary (Josh Allen Anchor + TEN D/ST)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "TEN"
        },
        {
            "name": "Scenario 1C: LAC @ BUF Primary (Josh Allen Anchor + CIN D/ST)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN"
        },
        {
            "name": "Scenario 2: BAL @ DAL Primary (JerryWorld Shootout + CLE D/ST)",
            "primary": ("BAL", "DAL"),
            "mini1": ("LAC", "BUF"),
            "mini2": ("NYJ", "DET"),
            "dst": "CLE"
        },
        {
            "name": "Scenario 2B: BAL @ DAL Primary (JerryWorld Shootout + CIN D/ST)",
            "primary": ("BAL", "DAL"),
            "mini1": ("LAC", "BUF"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN"
        },
        {
            "name": "Scenario 3: NYJ @ DET Primary (Ford Field Dome Engine + CLE D/ST)",
            "primary": ("NYJ", "DET"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("LAC", "BUF"),
            "dst": "CLE"
        }
    ]

    for sc in scenarios:
        print(f"\n--- {sc['name']} ---")
        roster = solve_tournament_matrix(
            df,
            primary_game=sc["primary"],
            mini_game_1=sc["mini1"],
            mini_game_2=sc["mini2"],
            dst_team=sc.get("dst"),
            min_salary=58500,
            max_salary=59800
        )
        if roster is not None:
            cols = ['pos', 'name', 'team', 'opp', 'salary', 'fppg', 'gpp_proj']
            print(roster[cols].sort_values(by=['pos', 'salary'], ascending=[True, False]).to_string(index=False))
            tot_sal = roster['salary'].sum()
            tot_proj = roster['gpp_proj'].sum()
            print(f"Total Salary: ${tot_sal:,} | Projected: {tot_proj:.2f} pts | Remaining: ${60000 - tot_sal:,}")
        else:
            print("No solution found with current constraints.")

if __name__ == "__main__":
    run_tests()
