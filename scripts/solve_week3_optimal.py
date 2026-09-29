import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

# Load enriched slate with actuals
import json
import re

csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
import sys
sys.path.insert(0, ".")
from scripts.solve_main_slate_matrix import load_and_enrich_slate

df, vegas = load_and_enrich_slate(csv_path)

with open("data/week3_sunday_actuals.json", "r") as f:
    act_data = json.load(f)

players_act = act_data["players"]

def clean_name(n):
    return re.sub(r"[^\w\s]", "", str(n)).lower().strip()

name_map = {clean_name(k): v for k, v in players_act.items()}
aliases = {
    clean_name("Kenneth Walker III"): clean_name("Kenneth Walker"),
    clean_name("James Cook III"): clean_name("James Cook"),
    clean_name("Travis Etienne Jr."): clean_name("Travis Etienne"),
    clean_name("Brian Robinson Jr."): clean_name("Brian Robinson"),
    clean_name("Marvin Harrison Jr."): clean_name("Marvin Harrison"),
    clean_name("Michael Pittman Jr."): clean_name("Michael Pittman"),
    clean_name("Tyrone Tracy Jr."): clean_name("Tyrone Tracy"),
}

# D/ST actual scores
dst_scores = {
    "WAS": 15.0, "NE": 9.0, "NYG": 6.0, "MIA": 6.0, "LAC": 5.0,
    "TEN": 4.0, "MIN": 4.0, "TB": 3.0, "HOU": 3.0, "BUF": 2.0,
    "KC": 2.0, "CIN": 2.0, "CLE": 2.0, "IND": 1.0, "CAR": 1.0,
    "NYJ": 0.0, "NO": 0.0, "JAX": 0.0, "PIT": -1.0, "DET": -1.0,
    "BAL": -1.0, "DAL": -1.0, "ARI": -1.0, "SEA": -1.0, "LV": -2.0, "SF": -4.0
}

acts = []
for idx, row in df.iterrows():
    c_name = row['norm_name']
    pos = row['pos']
    tm = row['team']
    if pos == 'D':
        acts.append(dst_scores.get(tm, 2.0))
    else:
        stat = name_map.get(c_name) or name_map.get(aliases.get(c_name))
        if not stat:
            for k in name_map:
                if c_name in k or k in c_name:
                    stat = name_map[k]
                    break
        acts.append(stat.get('half_ppr', 0.0) if stat else 0.0)

df['actual'] = acts

# Filter pool to valid actuals > 0
pool = df[df['actual'] > 0].copy().reset_index(drop=True)

n = len(pool)
c = -pool['actual'].values

A_rows = []
b_l = []
b_u = []

# 1. Exactly 9 players
A_rows.append(np.ones(n)); b_l.append(9); b_u.append(9)

# 2. Total Salary <= 60000
A_rows.append(pool['salary'].values); b_l.append(0); b_u.append(60000)

# 3. Exactly 1 QB
A_rows.append((pool['pos'] == 'QB').astype(float).values); b_l.append(1); b_u.append(1)

# 4. Exactly 1 D/ST
A_rows.append((pool['pos'] == 'D').astype(float).values); b_l.append(1); b_u.append(1)

# 5. RBs: 2 to 3
A_rows.append((pool['pos'] == 'RB').astype(float).values); b_l.append(2); b_u.append(3)

# 6. WRs: 3 to 4
A_rows.append((pool['pos'] == 'WR').astype(float).values); b_l.append(3); b_u.append(4)

# 7. TEs: 1 to 2
A_rows.append((pool['pos'] == 'TE').astype(float).values); b_l.append(1); b_u.append(2)

# 8. Flex total = 7
A_rows.append(pool['pos'].isin(['RB', 'WR', 'TE']).astype(float).values); b_l.append(7); b_u.append(7)

A = np.array(A_rows)
constraints = LinearConstraint(A, b_l, b_u)
integrality = np.ones(n)
bounds = Bounds(0, 1)

res = milp(c=c, integrality=integrality, constraints=constraints, bounds=bounds)

if res.success:
    best_idx = np.where(res.x > 0.5)[0]
    opt = pool.iloc[best_idx].copy()
    cols = ['pos', 'name', 'team', 'opp', 'salary', 'fppg', 'gpp_proj', 'actual']
    print("\n" + "="*70)
    print("TRUE OPTIMAL LINEUP FOR WEEK 3 SUNDAY MAIN SLATE")
    print("="*70)
    print(opt[cols].sort_values(by=['pos', 'salary'], ascending=[True, False]).to_string(index=False))
    print(f"\nTotal Salary Spent: ${opt['salary'].sum():,}")
    print(f"Remaining Cap: ${60000 - opt['salary'].sum():,}")
    print(f"Total Actual Score: {opt['actual'].sum():.2f} FP")
    print(f"Total Projected Score: {opt['gpp_proj'].sum():.2f} FP")
else:
    print("Could not solve optimal lineup.")
