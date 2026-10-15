import os
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

# Load slate data
csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
df = pd.read_csv(csv_path)

# McClure Exposure Weights
mcclure_exposures = {
    "Jahmyr Gibbs": 0.68,
    "Tennessee Titans": 0.58,
    "Rashod Bateman": 0.46,
    "Kenneth Walker III": 0.38,
    "Jaylen Warren": 0.32,
    "Garrett Wilson": 0.32,
    "Chuba Hubbard": 0.30,
    "Mark Andrews": 0.28,
    "Josh Allen": 0.26,
    "Dalton Kincaid": 0.26,
    "Jalen Coker": 0.20,
    "Cleveland Browns": 0.20,
    "Parker Washington": 0.20,
    "Travis Kelce": 0.18,
    "Ashton Jeanty": 0.18,
    "Derrick Henry": 0.16,
    "Ladd McConkey": 0.16,
    "Adonai Mitchell": 0.14,
    "James Cook III": 0.14,
    "Quinshon Judkins": 0.14,
    "Denzel Boston": 0.12,
    "Emeka Egbuka": 0.12,
    "Christian McCaffrey": 0.12,
    "Devaughn Vele": 0.12,
    "Tetairoa McMillan": 0.10,
    "Khalil Shakir": 0.10,
    "Brock Purdy": 0.08,
    "Trevor Lawrence": 0.06,
    "Lamar Jackson": 0.06,
    "Tyler Shough": 0.06,
    "Patrick Mahomes": 0.04,
    "Dak Prescott": 0.04,
    "Drake Maye": 0.04,
    "Deshaun Watson": 0.04,
    "Geno Smith": 0.04
}

mcclure_pool_names = list(mcclure_exposures.keys())
pool = df[df['Nickname'].isin(mcclure_pool_names)].copy().reset_index(drop=True)

# Add GPP projection using FPPG and exposure weighting
pool['exp_weight'] = pool['Nickname'].map(mcclure_exposures).fillna(0.05)
pool['mcclure_proj'] = pool['FPPG'] * (1.0 + pool['exp_weight'])

print(f"Total players in McClure pool: {len(pool)}")

def solve_pool(pool_df, max_salary=60000, min_salary=58500, force_players=None, force_qb=None):
    n = len(pool_df)
    c = -pool_df['mcclure_proj'].values

    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n)); b_l.append(9); b_u.append(9)

    # 2. Total Salary
    A_rows.append(pool_df['Salary'].values); b_l.append(min_salary); b_u.append(max_salary)

    # 3. Exactly 1 QB
    A_rows.append((pool_df['Position'] == 'QB').astype(float).values); b_l.append(1); b_u.append(1)

    if force_qb:
        qb_mask = ((pool_df['Position'] == 'QB') & (pool_df['Nickname'].str.lower() == force_qb.lower())).astype(float).values
        A_rows.append(qb_mask); b_l.append(1); b_u.append(1)

    # 4. Exactly 1 D/ST
    A_rows.append((pool_df['Position'] == 'D').astype(float).values); b_l.append(1); b_u.append(1)

    # 5. RBs: 2 to 3
    A_rows.append((pool_df['Position'] == 'RB').astype(float).values); b_l.append(2); b_u.append(3)

    # 6. WRs: 3 to 4
    A_rows.append((pool_df['Position'] == 'WR').astype(float).values); b_l.append(3); b_u.append(4)

    # 7. TEs: 1 to 2
    A_rows.append((pool_df['Position'] == 'TE').astype(float).values); b_l.append(1); b_u.append(2)

    # 8. Flex total = 7
    A_rows.append(pool_df['Position'].isin(['RB', 'WR', 'TE']).astype(float).values); b_l.append(7); b_u.append(7)

    # Force specific players
    if force_players:
        for fp in force_players:
            fp_mask = (pool_df['Nickname'].str.lower() == fp.lower()).astype(float).values
            A_rows.append(fp_mask); b_l.append(1); b_u.append(1)

    # QB correlation: If QB rostered, must have at least 1 WR/TE from same team
    for idx_qb, row_qb in pool_df[pool_df['Position'] == 'QB'].iterrows():
        qb_tm = row_qb['Team']
        pass_mask = ((pool_df['Team'] == qb_tm) & (pool_df['Position'].isin(['WR', 'TE']))).astype(float).values
        qb_ind = (np.arange(n) == idx_qb).astype(float)
        # pass_catchers - qb >= 0
        A_rows.append(pass_mask - qb_ind); b_l.append(0); b_u.append(9)

    # D/ST anti-cannibalization
    for idx_dst, row_dst in pool_df[pool_df['Position'] == 'D'].iterrows():
        dst_opp = row_dst['Opponent']
        opp_mask = ((pool_df['Team'] == dst_opp) & (pool_df['Position'] != 'D')).astype(float).values
        dst_ind = (np.arange(n) == idx_dst).astype(float)
        A_rows.append(opp_mask + 8.0 * dst_ind); b_l.append(-np.inf); b_u.append(8.0)

    A = np.array(A_rows)
    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones(n)
    bounds = Bounds(0, 1)

    res = milp(c=c, integrality=integrality, constraints=constraints, bounds=bounds)
    if res.success:
        selected_indices = np.where(res.x > 0.5)[0]
        return pool_df.iloc[selected_indices].copy()
    return None

print("\n" + "="*70)
print("OPTIMAL LINEUP SOLVED DIRECTLY FROM MIKE MCCLURE'S POOL")
print("="*70)

# 1. Pure Optimal on McClure's Model
opt1 = solve_pool(pool, max_salary=60000, min_salary=58500, force_qb="Josh Allen")
if opt1 is not None:
    cols = ['Position', 'Nickname', 'Team', 'Opponent', 'Salary', 'FPPG', 'exp_weight', 'mcclure_proj']
    print(opt1[cols].sort_values(by=['Position', 'Salary'], ascending=[True, False]).to_string(index=False))
    tot_sal = opt1['Salary'].sum()
    print(f"\nTotal Salary: ${tot_sal:,} | McClure Proj: {opt1['mcclure_proj'].sum():.2f} pts | Remaining: ${60000 - tot_sal:,}")

# 2. Optimal with Titans D/ST (McClure's 58% top D/ST) + Core 4 (Gibbs, Walker, Wilson, Bateman)
print("\n" + "="*70)
print("MCCLURE CORE 4 LOCK: Gibbs (68%) + Walker (38%) + Wilson (32%) + Bateman (46%)")
print("="*70)
opt2 = solve_pool(pool, max_salary=60000, min_salary=58500, force_qb="Josh Allen", force_players=["Jahmyr Gibbs", "Kenneth Walker III", "Garrett Wilson", "Rashod Bateman"])
if opt2 is not None:
    cols = ['Position', 'Nickname', 'Team', 'Opponent', 'Salary', 'FPPG', 'exp_weight', 'mcclure_proj']
    print(opt2[cols].sort_values(by=['Position', 'Salary'], ascending=[True, False]).to_string(index=False))
    tot_sal = opt2['Salary'].sum()
    print(f"\nTotal Salary: ${tot_sal:,} | McClure Proj: {opt2['mcclure_proj'].sum():.2f} pts | Remaining: ${60000 - tot_sal:,}")

