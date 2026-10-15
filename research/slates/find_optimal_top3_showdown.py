"""Find the mathematically optimal top lineups across 10,000 Monte Carlo simulations.

Full combinatorial search across all valid rosters satisfying all rules in GEMINI.md.
"""

import sys
from pathlib import Path
from collections import Counter
from itertools import combinations
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from solve_det_buf_slate import build_calibrated_player_pool

df = build_calibrated_player_pool()

# Viable players for single entry (salary >= $3,500)
# We exclude backup QBs
viable = df[
    (df["salary"] >= 3500) & 
    (~df["name"].isin(["Kyle Allen", "Joshua Dobbs", "Shane Buechele", "Luke Altmyer"]))
].copy().reset_index(drop=True)

names = viable["name"].values
salaries = viable["salary"].values
teams = viable["team"].values
positions = viable["position"].values
base_proj = viable["proj"].values
n_players = len(viable)
name_to_idx = {name: i for i, name in enumerate(names)}

# Covariance Matrix
corr = np.eye(n_players)

def set_corr(p1, p2, val):
    if p1 in name_to_idx and p2 in name_to_idx:
        i, j = name_to_idx[p1], name_to_idx[p2]
        corr[i, j] = val
        corr[j, i] = val

set_corr("Josh Allen", "DJ Moore", 0.46)
set_corr("Josh Allen", "Dalton Kincaid", 0.42)
set_corr("Josh Allen", "Khalil Shakir", 0.35)
set_corr("Josh Allen", "Keon Coleman", 0.28)
set_corr("Josh Allen", "Tyler Bass", 0.15)
set_corr("Josh Allen", "James Cook III", -0.08)

set_corr("Jared Goff", "Amon-Ra St. Brown", 0.48)
set_corr("Jared Goff", "Sam LaPorta", 0.38)
set_corr("Jared Goff", "Jameson Williams", 0.35)
set_corr("Jared Goff", "Jake Bates", 0.15)
set_corr("Jared Goff", "Jahmyr Gibbs", 0.12)

set_corr("Josh Allen", "Jared Goff", 0.25)
set_corr("Josh Allen", "Amon-Ra St. Brown", 0.20)
set_corr("Josh Allen", "Jahmyr Gibbs", 0.22)
set_corr("Jared Goff", "DJ Moore", 0.18)
set_corr("Jared Goff", "Dalton Kincaid", 0.16)

set_corr("Buffalo Bills", "Jared Goff", -0.35)
set_corr("Buffalo Bills", "Jahmyr Gibbs", -0.28)
set_corr("Detroit Lions", "Josh Allen", -0.32)
set_corr("Detroit Lions", "James Cook III", -0.25)

std_pct = {"QB": 0.32, "RB": 0.40, "WR": 0.46, "TE": 0.50, "K": 0.32, "D": 0.55}
stds = np.array([base_proj[i] * std_pct.get(positions[i], 0.40) for i in range(n_players)])
cov = np.outer(stds, stds) * corr

min_eig = np.min(np.real(np.linalg.eigvals(cov)))
if min_eig < 0:
    cov -= 1.1 * min_eig * np.eye(n_players)

np.random.seed(42)
n_sims = 10000
raw_sims = np.random.multivariate_normal(base_proj, cov, size=n_sims)
sim_scores = np.maximum(0.0, raw_sims)

# Pass catchers definitions
buf_pass_catchers = set(["DJ Moore", "Dalton Kincaid", "Khalil Shakir", "Keon Coleman", "Dawson Knox"])
det_pass_catchers = set(["Amon-Ra St. Brown", "Sam LaPorta", "Jameson Williams"])

valid_lineups = []

print(f"Generating all valid rosters from pool of {n_players} players...")

# Loop over each player as MVP
for mvp_idx in range(n_players):
    mvp_name = names[mvp_idx]
    mvp_team = teams[mvp_idx]
    mvp_pos = positions[mvp_idx]
    mvp_sal = salaries[mvp_idx] * 1.5

    # Other players available for FLEX
    other_indices = [i for i in range(n_players) if i != mvp_idx]

    # Choose 5 FLEX from remaining
    for flex_comb in combinations(other_indices, 5):
        tot_sal = mvp_sal + sum(salaries[i] for i in flex_comb)
        # Cap check: $58,500 <= tot_sal <= $59,800 (Leaves $200-$1500 unspent buffer)
        if tot_sal > 59800 or tot_sal < 58500:
            continue

        all_indices = [mvp_idx] + list(flex_comb)
        all_names = [names[i] for i in all_indices]
        all_teams = [teams[i] for i in all_indices]
        all_positions = [positions[i] for i in all_indices]

        # Rule 1: Team representation (at least 1 from each team)
        team_counts = Counter(all_teams)
        if team_counts["BUF"] == 0 or team_counts["DET"] == 0:
            continue

        # Rule 2: QB Stacking (No naked QB)
        has_buf_qb = "Josh Allen" in all_names
        has_det_qb = "Jared Goff" in all_names

        buf_pc_count = sum(1 for p in all_names if p in buf_pass_catchers)
        det_pc_count = sum(1 for p in all_names if p in det_pass_catchers)

        if has_buf_qb and buf_pc_count == 0:
            continue
        if has_det_qb and det_pc_count == 0:
            continue

        # Rule 3: QB Rule of 3 (Max 2 pass catchers without QB; 3+ requires QB)
        if not has_buf_qb and buf_pc_count >= 3:
            continue
        if not has_det_qb and det_pc_count >= 3:
            continue

        # Rule 4: D/ST Anti-Cannibalization
        # No D/ST with opposing starting RB
        if "Buffalo Bills" in all_names and "Jahmyr Gibbs" in all_names:
            continue
        if "Detroit Lions" in all_names and "James Cook III" in all_names:
            continue
        # Max 2 opposing offensive players against D/ST
        if "Buffalo Bills" in all_names:
            det_offense = sum(1 for i in all_indices if teams[i] == "DET" and positions[i] != "D")
            if det_offense > 2:
                continue
        if "Detroit Lions" in all_names:
            buf_offense = sum(1 for i in all_indices if teams[i] == "BUF" and positions[i] != "D")
            if buf_offense > 2:
                continue

        # Calculate scores in simulation
        flex_idx = list(flex_comb)
        lu_sim_scores = 1.5 * sim_scores[:, mvp_idx] + np.sum(sim_scores[:, flex_idx], axis=1)

        mean_pts = np.mean(lu_sim_scores)
        p90_pts = np.percentile(lu_sim_scores, 90)
        p99_pts = np.percentile(lu_sim_scores, 99)
        p130 = np.mean(lu_sim_scores >= 130)
        p150 = np.mean(lu_sim_scores >= 150)

        valid_lineups.append({
            "mvp": mvp_name,
            "mvp_pos": mvp_pos,
            "mvp_team": mvp_team,
            "flex": [names[i] for i in flex_comb],
            "salary": tot_sal,
            "buffer": 60000 - tot_sal,
            "team_counts": dict(team_counts),
            "mean": mean_pts,
            "p90": p90_pts,
            "p99": p99_pts,
            "p130": p130 * 100,
            "p150": p150 * 100,
        })

print(f"Total valid lineups meeting all rules & salary thresholds: {len(valid_lineups):,}")

# Rank by GPP Tournament Equity: Composite of 90th percentile, 99th percentile, and p150
for lu in valid_lineups:
    # GPP index = 0.4 * p90 + 0.4 * p99 + 0.2 * mean + (lu['p150'] * 10)
    lu["gpp_score"] = 0.35 * lu["p90"] + 0.45 * lu["p99"] + 0.20 * lu["mean"] + (lu["p150"] * 5)

ranked = sorted(valid_lineups, key=lambda x: x["gpp_score"], reverse=True)

print("\n" + "=" * 90)
print("TOP 10 FANDUEL SINGLE-GAME TOURNAMENT LINEUPS (10,000 SIMULATIONS)")
print("=" * 90)
for idx, lu in enumerate(ranked[:10], 1):
    print(f"Rank {idx}: [MVP] {lu['mvp']} ({lu['mvp_team']} {lu['mvp_pos']}) | Salary: ${lu['salary']:,} (Buf: ${lu['buffer']:,}) | Teams: {lu['team_counts']}")
    print(f"         FLEX: {', '.join(lu['flex'])}")
    print(f"         Mean: {lu['mean']:.2f} | 90th%: {lu['p90']:.2f} | 99th%: {lu['p99']:.2f} | >=130pt: {lu['p130']:.1f}% | >=150pt: {lu['p150']:.1f}% | GPP Score: {lu['gpp_score']:.2f}")
    print("-" * 90)
