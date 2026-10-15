#!/usr/bin/env python3
"""Dedicated Single-Game Solver for NYG @ LAR (Monday Night Football - Week 2, 2026).
Calibrated with official 90-minute inactives:
- LAR Inactives: Puka Nacua (WR), Jordan Whittington (WR), Kamren Kinchens (S), CJ Daniels, Bill Murray, Ty Simpson
- NYG Inactives: Deonte Banks (CB), Micah McFadden (LB), Jason Pinnock (S), Thomas Fidone II (TE), JC Davis, Bobby Jamison-Travis
- Returns: Aaron Donald (DT) active for LAR!
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer

def calibrate_projections(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # Official inactives
    out_players = [
        "Puka Nacua", "Jordan Whittington", "Kamren Kinchens",
        "C.J. Daniels", "CJ Daniels", "Bill Murray", "Ty Simpson",
        "Thomas Fidone II", "J.C. Davis", "Bobby Jamison-Travis", "Darius Alexander",
        "Paulson Adebo", "Calvin Austin III", "Gunner Olszewski",
        "Matthew Caldwell", "Najee Harris"
    ]
    df = df[~df["Nickname"].isin(out_players)].copy()
    
    # Calibrated half-ppr projections based on 47.5 O/U, LAR 27.25, NYG 20.25,
    # and post-injury target/touch redistribution:
    calibrated_proj = {
        # LAR
        "Matthew Stafford": 17.6,
        "Davante Adams": 17.2,     # Alpha WR1 with Puka & Whittington OUT (10-13 targets)
        "Kyren Williams": 16.5,    # Bellcow RB1, home favorite (18+ touches)
        "Tutu Atwell": 8.8,        # Primary WR2 in 11 personnel (85%+ routes)
        "Blake Corum": 6.2,        # Change-of-pace / 6-8 touches
        "Harrison Mevis": 8.4,     # Favored home kicker, high-scoring dome
        "Los Angeles Rams": 7.2,   # Donald returns vs 29th pass-blocking OL
        "Colby Parkinson": 6.5,    # Starting TE against depleted LB/S group
        "Tyler Higbee": 4.5,       # Rotational TE
        "Konata Mumpfield": 5.0,   # WR3 role in 11 personnel
        "Xavier Smith": 3.0,       # Rotational WR4 / return specialist
        "Ronnie Rivers": 2.0,
        "Terrance Ferguson": 1.5,
        "Davis Allen": 1.5,
        
        # NYG
        "Jaxson Dart": 18.5,       # Dual-threat QB trailing script (50+ rush yds ceiling)
        "Malik Nabers": 14.8,      # Alpha WR1 (9 targets in W1, 28% target share)
        "Isaiah Likely": 13.0,     # High-value TE red-zone weapon (8 tgts, 2 TDs in W1)
        "Cam Skattebo": 11.5,      # Starting bellcow RB (18 carries in W1)
        "Devin Singletary": 9.5,   # Passing-down / 2-minute drill back (4 tgts, 1 TD in W1)
        "Dominic Zvada": 6.5,      # Kicker
        "New York Giants": 5.0,    # Depleted defense
        "Malachi Fields": 5.8,     # WR2 (50 snaps in W1)
        "Darnell Mooney": 5.4,     # Primary slot WR (39 snaps in W1)
        "Theo Johnson": 3.0,       # TE2
        "Tyrone Tracy Jr.": 2.5,   # RB3
        "Phil Mafah": 1.5,
        "Odell Beckham Jr.": 1.5,
        "Patrick Ricard": 0.8,
    }
    
    # Assign projections and custom ceilings
    df["proj"] = df["Nickname"].map(calibrated_proj).fillna(df["FPPG"].astype(float))
    
    # Specific ceiling adjustments for high variance studs
    df["ceiling_proj"] = df["proj"] * 1.35 + 4.0
    df.loc[df["Nickname"] == "Davante Adams", "ceiling_proj"] = 29.5
    df.loc[df["Nickname"] == "Kyren Williams", "ceiling_proj"] = 27.5
    df.loc[df["Nickname"] == "Jaxson Dart", "ceiling_proj"] = 31.0
    df.loc[df["Nickname"] == "Malik Nabers", "ceiling_proj"] = 26.5
    df.loc[df["Nickname"] == "Isaiah Likely", "ceiling_proj"] = 24.0
    df.loc[df["Nickname"] == "Matthew Stafford", "ceiling_proj"] = 26.0
    df.loc[df["Nickname"] == "Cam Skattebo", "ceiling_proj"] = 21.0
    df.loc[df["Nickname"] == "Tutu Atwell", "ceiling_proj"] = 17.5
    df.loc[df["Nickname"] == "Harrison Mevis", "ceiling_proj"] = 14.0
    df.loc[df["Nickname"] == "Los Angeles Rams", "ceiling_proj"] = 15.0
    
    return df

def run_single_entry_showdown():
    csv_path = "data/NYGVSLAR9-21-26singlegameslate.csv"
    df_raw = pd.read_csv(csv_path)
    df = calibrate_projections(df_raw)
    
    # Strict Single-Entry: Minimum punt salary >= $4,000 (No ghost punts!)
    optimizer = FanDuelShowdownOptimizer(
        salary_cap=60000,
        max_salary=59800,  # >= $200 unspent buffer
        min_salary=57000,  # <= $3,000 unspent buffer
        min_punt_salary=4000,
    )
    
    print("\n" + "=" * 80)
    print("STRICT SINGLE-ENTRY SOLVER (MIN PUNT >= $4,000 | ZERO GHOST PUNTS)")
    print("=" * 80)
    
    scripts = optimizer.generate_all_scripts(
        df,
        mode="GPP",
        allow_sub3500_punts=False,
    )
    
    for script_id, sol in scripts.items():
        print(f"\n{'='*30} {sol['script_name'].upper()} {'='*30}")
        print(f"Script ID: {script_id}")
        print(f"Total Salary Spent: ${sol['total_salary']:,} / $60,000  (Buffer: ${sol['unspent_buffer']:,} unspent)")
        print(f"Projected Pts: {sol['total_projected_pts']:.2f} | Ceiling Pts: {sol['total_ceiling_pts']:.2f}")
        print(f"Team Breakdown: {sol['team_counts']}")
        print("-" * 80)
        mvp = sol["mvp"]
        print(f"[MVP (1.5x)]  {mvp['name']:<22} | {mvp['team']:<4} {mvp['position']:<3} | Base: ${mvp['salary']:,} (Cost: ${mvp['effective_salary']:,}) | Proj: {mvp['effective_pts']:.1f}")
        print("-" * 80)
        for i, f in enumerate(sol["flex"], 1):
            print(f"[FLEX {i}]     {f['name']:<22} | {f['team']:<4} {f['position']:<3} | Cost: ${f['salary']:,}              | Proj: {f['effective_pts']:.1f}")
        print("-" * 80)

if __name__ == "__main__":
    run_single_entry_showdown()
