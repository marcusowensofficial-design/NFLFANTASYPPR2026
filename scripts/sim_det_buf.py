"""10,000-Trial Monte Carlo Simulation for DET @ BUF Single-Game Slate."""

import numpy as np
import pandas as pd
from collections import Counter

# Load pool
import sys
from pathlib import Path

# Add project root and scripts directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from solve_det_buf_slate import build_calibrated_player_pool


df = build_calibrated_player_pool()
# Filter only players >= $3,500 plus key rotational pieces
viable = df[df["salary"] >= 2000].copy().reset_index(drop=True)

names = viable["name"].values
salaries = viable["salary"].values
teams = viable["team"].values
positions = viable["position"].values
base_proj = viable["proj"].values
ceil_proj = viable["ceiling_proj"].values
n_players = len(viable)

name_to_idx = {name: i for i, name in enumerate(names)}

# Covariance matrix construction
corr = np.eye(n_players)

def set_corr(p1, p2, val):
    if p1 in name_to_idx and p2 in name_to_idx:
        i, j = name_to_idx[p1], name_to_idx[p2]
        corr[i, j] = val
        corr[j, i] = val

# Passing Stacks & Covariances
set_corr("Josh Allen", "DJ Moore", 0.46)
set_corr("Josh Allen", "Dalton Kincaid", 0.42)
set_corr("Josh Allen", "Khalil Shakir", 0.35)
set_corr("Josh Allen", "Keon Coleman", 0.28)
set_corr("Josh Allen", "Tyler Bass", 0.15)
set_corr("Josh Allen", "James Cook III", -0.08)  # Goal line rushing cannibalization

set_corr("Jared Goff", "Amon-Ra St. Brown", 0.48)
set_corr("Jared Goff", "Sam LaPorta", 0.38)
set_corr("Jared Goff", "Jameson Williams", 0.35)
set_corr("Jared Goff", "Jake Bates", 0.15)
set_corr("Jared Goff", "Jahmyr Gibbs", 0.12)  # Gibbs catches passes

# Shootout Bring-Backs (Pace correlation in 54.5 O/U)
set_corr("Josh Allen", "Jared Goff", 0.25)
set_corr("Josh Allen", "Amon-Ra St. Brown", 0.20)
set_corr("Josh Allen", "Jahmyr Gibbs", 0.22)
set_corr("Jared Goff", "DJ Moore", 0.18)
set_corr("Jared Goff", "Dalton Kincaid", 0.16)

# D/ST Negative Correlations
set_corr("Buffalo Bills", "Jared Goff", -0.35)
set_corr("Buffalo Bills", "Jahmyr Gibbs", -0.28)
set_corr("Detroit Lions", "Josh Allen", -0.32)
set_corr("Detroit Lions", "James Cook III", -0.25)

# Standard deviations
std_pct = {
    "QB": 0.32,
    "RB": 0.40,
    "WR": 0.46,
    "TE": 0.50,
    "K": 0.32,
    "D": 0.55,
}
stds = np.array([base_proj[i] * std_pct.get(positions[i], 0.40) for i in range(n_players)])
cov = np.outer(stds, stds) * corr

# Ensure positive semi-definite
min_eig = np.min(np.real(np.linalg.eigvals(cov)))
if min_eig < 0:
    cov -= 1.1 * min_eig * np.eye(n_players)

# Generate 10,000 simulations
np.random.seed(42)
n_sims = 10000
raw_sims = np.random.multivariate_normal(base_proj, cov, size=n_sims)
sim_scores = np.maximum(0.0, raw_sims)

# Candidate Lineups to stress-test
candidate_lineups = [
    {
        "id": "LU1_Kincaid_MVP_6Starters",
        "name": "Lineup 1: Kincaid MVP Knapsack Hegemony (4-2 BUF, 6 Full-Time Starters)",
        "mvp": "Dalton Kincaid",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "DJ Moore", "Sam LaPorta", "Tyler Bass"],
        "salary": 7600 * 1.5 + 13200 + 12400 + 8600 + 7400 + 6800,  # 59,800
        "buffer": 200,
    },
    {
        "id": "LU2_Allen_MVP_Alpha",
        "name": "Lineup 2: Josh Allen MVP Alpha Outlier (3-3 Shootout)",
        "mvp": "Josh Allen",
        "flex": ["Jahmyr Gibbs", "DJ Moore", "Dalton Kincaid", "Sam LaPorta", "Sione Vaki"],
        "salary": 13200 * 1.5 + 12400 + 8600 + 7600 + 7400 + 3600,  # 59,400
        "buffer": 600,
    },
    {
        "id": "LU3_Gibbs_MVP_Monopoly",
        "name": "Lineup 3: Jahmyr Gibbs MVP Touchdown Monopoly (4-2 DET)",
        "mvp": "Jahmyr Gibbs",
        "flex": ["Josh Allen", "Amon-Ra St. Brown", "Dalton Kincaid", "Jake Bates", "Sione Vaki"],
        "salary": 12400 * 1.5 + 13200 + 11600 + 7600 + 6600 + 3600,  # 60,600 -> OVER CAP!
        "buffer": -600,
    },
    {
        "id": "LU3B_Gibbs_MVP_Viable",
        "name": "Lineup 3B: Jahmyr Gibbs MVP Lions Assault (4-2 DET, Under Cap)",
        "mvp": "Jahmyr Gibbs",
        "flex": ["Josh Allen", "Amon-Ra St. Brown", "Jake Bates", "Detroit Lions", "Joshua Palmer"],
        "salary": 12400 * 1.5 + 13200 + 11600 + 6600 + 6200 + 3200,  # 59,400
        "buffer": 600,
    },
    {
        "id": "LU3C_Gibbs_MVP_ZeroQB",
        "name": "Lineup 3C: Jahmyr Gibbs MVP Zero-QB Monopoly (3-3 Balanced)",
        "mvp": "Jahmyr Gibbs",
        "flex": ["Amon-Ra St. Brown", "DJ Moore", "Dalton Kincaid", "Sam LaPorta", "Keon Coleman"],
        "salary": 12400 * 1.5 + 11600 + 8600 + 7600 + 7400 + 5600,  # 59,400
        "buffer": 600,
    },
    {
        "id": "LU4_DJMoore_MVP_Leverage",
        "name": "Lineup 4: DJ Moore MVP Perimeter Leverage (4-2 BUF)",
        "mvp": "DJ Moore",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "Amon-Ra St. Brown", "Tyler Bass", "Sione Vaki"],
        "salary": 8600 * 1.5 + 13200 + 12400 + 11600 + 6800 + 3600,  # 60,500 -> OVER CAP!
        "buffer": -500,
    },
    {
        "id": "LU4B_DJMoore_MVP_Legal",
        "name": "Lineup 4B: DJ Moore MVP Perimeter Leverage (4-2 BUF Legal)",
        "mvp": "DJ Moore",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "Sam LaPorta", "Dalton Kincaid", "Tyler Bass"],
        "salary": 8600 * 1.5 + 13200 + 12400 + 7400 + 7600 + 6800,  # 60,300 -> OVER CAP!
        "buffer": -300,
    },
    {
        "id": "LU4C_DJMoore_MVP_Legal2",
        "name": "Lineup 4C: DJ Moore MVP Knapsack (4-2 BUF Legal)",
        "mvp": "DJ Moore",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "Dalton Kincaid", "Tyler Bass", "Sione Vaki"],
        "salary": 8600 * 1.5 + 13200 + 12400 + 7600 + 6800 + 3600,  # 56,500
        "buffer": 3500,
    },
    {
        "id": "LU5_LaPorta_MVP_DualTE",
        "name": "Lineup 5: Sam LaPorta MVP Dual-TE Knapsack (4-2 DET)",
        "mvp": "Sam LaPorta",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "Amon-Ra St. Brown", "Dalton Kincaid", "Sione Vaki"],
        "salary": 7400 * 1.5 + 13200 + 12400 + 11600 + 7600 + 3600,  # 59,500
        "buffer": 500,
    },
    {
        "id": "LU6_DualQB_Shootout",
        "name": "Lineup 6: Dual-QB Shootout (Allen + Goff + Kincaid + DJ Moore)",
        "mvp": "Dalton Kincaid",
        "flex": ["Josh Allen", "Jared Goff", "Jahmyr Gibbs", "DJ Moore", "Tyler Bass"],
        "salary": 7600 * 1.5 + 13200 + 10600 + 12400 + 8600 + 6800,  # 63,000 -> OVER CAP!
        "buffer": -3000,
    }
]

# Filter strictly legal lineups (salary <= 60,000 and salary >= 56,500)
legal_lineups = [lu for lu in candidate_lineups if lu["salary"] <= 60000]

print("=" * 85)
print(f"MONTE CARLO TOURNAMENT SIMULATION RESULTS ({n_sims:,} Iterations)")
print("=" * 85)
print(f"{'Lineup ID':<26} | {'Salary':<7} | {'Buf':<5} | {'Mean':<6} | {'90th%':<6} | {'99th%':<6} | {'>=130pt':<7} | {'>=150pt':<7}")
print("-" * 85)

sim_results = []
for lu in legal_lineups:
    mvp_idx = name_to_idx[lu["mvp"]]
    flex_indices = [name_to_idx[p] for p in lu["flex"]]
    
    # Calculate lineup score for each sim: 1.5 * MVP + sum(FLEX)
    lu_scores = 1.5 * sim_scores[:, mvp_idx] + np.sum(sim_scores[:, flex_indices], axis=1)
    
    mean_val = np.mean(lu_scores)
    p90 = np.percentile(lu_scores, 90)
    p99 = np.percentile(lu_scores, 99)
    p_130 = np.mean(lu_scores >= 130) * 100
    p_150 = np.mean(lu_scores >= 150) * 100
    
    sim_results.append({
        "id": lu["id"],
        "name": lu["name"],
        "mvp": lu["mvp"],
        "flex": lu["flex"],
        "salary": lu["salary"],
        "buffer": lu["buffer"],
        "mean": mean_val,
        "p90": p90,
        "p99": p99,
        "p_130": p_130,
        "p_150": p_150,
        "scores": lu_scores,
    })
    
    print(f"{lu['id']:<26} | ${lu['salary']:<6} | ${lu['buffer']:<4} | {mean_val:<6.2f} | {p90:<6.2f} | {p99:<6.2f} | {p_130:<6.1f}% | {p_150:<6.1f}%")

print("=" * 85)
