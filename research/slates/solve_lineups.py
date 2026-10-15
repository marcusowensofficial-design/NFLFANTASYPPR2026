import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint

def solve_fanduel_lineup(df_pool, stack_team=None, stack_opp=None, force_players=None, exclude_players=None):
    # Filter out players with zero or minimal projection
    df = df_pool[df_pool['proj'] >= 2.0].reset_index(drop=True).copy()
    n = len(df)
    
    # Variables: x_i in {0, 1} for each player
    # Objective: Maximize sum(proj_i * x_i) => Minimize sum(-proj_i * x_i)
    c = -df['proj'].values

    # Constraints:
    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n))
    b_l.append(9)
    b_u.append(9)

    # 2. Total Salary <= 60000
    A_rows.append(df['salary'].values)
    b_l.append(0)
    b_u.append(60000)

    # 3. Exactly 1 QB
    is_qb = (df['pos'] == 'QB').astype(float).values
    A_rows.append(is_qb)
    b_l.append(1)
    b_u.append(1)

    # 4. Exactly 1 D/ST
    is_dst = (df['pos'] == 'D').astype(float).values
    A_rows.append(is_dst)
    b_l.append(1)
    b_u.append(1)

    # 5. RBs: between 2 and 3 (2 RB + optional FLEX)
    is_rb = (df['pos'] == 'RB').astype(float).values
    A_rows.append(is_rb)
    b_l.append(2)
    b_u.append(3)

    # 6. WRs: between 3 and 4 (3 WR + optional FLEX)
    is_wr = (df['pos'] == 'WR').astype(float).values
    A_rows.append(is_wr)
    b_l.append(3)
    b_u.append(4)

    # 7. TEs: between 1 and 2 (1 TE + optional FLEX)
    is_te = (df['pos'] == 'TE').astype(float).values
    A_rows.append(is_te)
    b_l.append(1)
    b_u.append(2)

    # 8. Flex constraint: (RB - 2) + (WR - 3) + (TE - 1) == 1
    # => RB + WR + TE == 7
    is_flex_eligible = ((df['pos'] == 'RB') | (df['pos'] == 'WR') | (df['pos'] == 'TE')).astype(float).values
    A_rows.append(is_flex_eligible)
    b_l.append(7)
    b_u.append(7)

    # 9. Max 4 players from the same team (FanDuel rule)
    teams = df['team'].unique()
    for t in teams:
        is_t = (df['team'] == t).astype(float).values
        A_rows.append(is_t)
        b_l.append(0)
        b_u.append(4)

    # 10. Optional Stack constraints
    if stack_team:
        # Must have QB from stack_team
        is_stack_qb = ((df['team'] == stack_team) & (df['pos'] == 'QB')).astype(float).values
        A_rows.append(is_stack_qb)
        b_l.append(1)
        b_u.append(1)

        # Must have at least 1 WR/TE from stack_team
        is_stack_pass_catcher = ((df['team'] == stack_team) & (df['pos'].isin(['WR', 'TE']))).astype(float).values
        A_rows.append(is_stack_pass_catcher)
        b_l.append(1)
        b_u.append(3)

    if stack_opp:
        # Bring-back: at least 1 skill player from stack_opp
        is_bringback = ((df['team'] == stack_opp) & (df['pos'].isin(['WR', 'TE', 'RB']))).astype(float).values
        A_rows.append(is_bringback)
        b_l.append(1)
        b_u.append(2)

    # 11. Force / Exclude players
    if force_players:
        for p_name in force_players:
            is_p = (df['name'].str.lower() == p_name.lower()).astype(float).values
            if is_p.sum() > 0:
                A_rows.append(is_p)
                b_l.append(1)
                b_u.append(1)

    if exclude_players:
        for p_name in exclude_players:
            is_p = (df['name'].str.lower() == p_name.lower()).astype(float).values
            if is_p.sum() > 0:
                A_rows.append(is_p)
                b_l.append(0)
                b_u.append(0)

    # Solve MILP
    A = np.array(A_rows)
    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones(n) # all variables are binary (0 or 1)

    res = milp(c=c, constraints=constraints, integrality=integrality)

    if not res.success:
        return None, None

    # Selected lineup
    selected_idx = np.where(res.x > 0.5)[0]
    lineup = df.iloc[selected_idx].copy()
    total_salary = lineup['salary'].sum()
    total_proj = lineup['proj'].sum()

    return lineup, (total_salary, total_proj)

def print_lineup(title, lineup, stats):
    if lineup is None:
        print(f"\n{title}: Infeasible or failed to solve.")
        return
    tot_sal, tot_proj = stats
    print(f"\n{'='*75}")
    print(f" {title.upper()} ")
    print(f"{'='*75}")
    
    # Sort order: QB, RB, RB, WR, WR, WR, TE, FLEX, D
    order_map = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'D': 5}
    lineup_sorted = lineup.sort_values(by=['pos', 'salary'], key=lambda x: x.map(order_map) if x.name == 'pos' else x, ascending=[True, False])
    
    for _, r in lineup_sorted.iterrows():
        print(f"  {r['pos']:<4} | {r['name']:<22} | {r['team']:<4} vs {r['opp']:<4} | ${r['salary']:<5} | Proj: {r['proj']:<5.2f} pts | Implied: {r['team_implied']:<4.1f} | Softness: #{r['soft_rank']}")
    
    print(f"{'-'*75}")
    print(f"  TOTAL SALARY: ${tot_sal:,} / $60,000  (Remaining: ${60000 - tot_sal:,})")
    print(f"  TOTAL PROJECTED POINTS: {tot_proj:.2f} pts")
    print(f"  AVG SALARY / PLAYER: ${tot_sal // 9:,}")
    print(f"{'='*75}\n")

if __name__ == '__main__':
    df_pool = pd.read_csv('data/optimized_player_pool.csv')
    
    # 1. Pure Optimal (Unconstrained Max Projection)
    l1, s1 = solve_fanduel_lineup(df_pool)
    print_lineup("Build 1: Unconstrained Mathematical Maximum Projection", l1, s1)

    # 2. Cincinnati Bengals Game Stack (CIN @ TB - Slate Highest 50.5 Total)
    l2, s2 = solve_fanduel_lineup(df_pool, stack_team='CIN', stack_opp='TB', force_players=['Omarion Hampton'])
    print_lineup("Build 2: Tournament Stack — Cincinnati Shootout (Burrow + Chase/Higgins + TB Bring-back + Hampton)", l2, s2)

    # 3. Detroit Lions Game Stack (DET vs NO - 28.25 Implied Total in Dome)
    l3, s3 = solve_fanduel_lineup(df_pool, stack_team='DET', stack_opp='NO', force_players=['Omarion Hampton'])
    print_lineup("Build 3: Tournament Stack — Detroit Dome Assault (Goff + St. Brown + Olave + Hampton)", l3, s3)

    # 4. Los Angeles Chargers Core Stack (LAC vs ARI - 28.75 Implied Total, 10-pt Fav)
    l4, s4 = solve_fanduel_lineup(df_pool, stack_team='LAC', stack_opp='ARI')
    print_lineup("Build 4: Tournament Stack — Chargers Smash Spot (Herbert + Hampton + Pass Catcher + McBride)", l4, s4)

    # 5. Philadelphia Eagles Core Stack (PHI vs WAS - 25.0 Implied Total, Saquon Smash)
    l5, s5 = solve_fanduel_lineup(df_pool, stack_team='PHI', stack_opp='WAS', force_players=['Omarion Hampton', 'Saquon Barkley'])
    print_lineup("Build 5: Dual Smash RB Build (Hurts + Brown/Smith + Saquon + Hampton)", l5, s5)
