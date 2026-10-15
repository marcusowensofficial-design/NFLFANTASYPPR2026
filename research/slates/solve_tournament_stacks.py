import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

def solve_tournament_lineup(
    df_pool,
    stack_team=None,
    stack_opp=None,
    stack_qb=None,
    stack_wr_te=None,
    stack_bringback=None,
    force_players=None,
    exclude_players=None,
    max_salary=60000,
    min_salary=59200
):
    df = df_pool[df_pool['proj'] >= 2.0].reset_index(drop=True).copy()
    n = len(df)
    c = -df['proj'].values

    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n))
    b_l.append(9); b_u.append(9)

    # 2. Total Salary <= 60000, >= min_salary
    A_rows.append(df['salary'].values)
    b_l.append(min_salary); b_u.append(max_salary)

    # 3. Exactly 1 QB
    A_rows.append((df['pos'] == 'QB').astype(float).values)
    b_l.append(1); b_u.append(1)

    # 4. Exactly 1 D/ST
    A_rows.append((df['pos'] == 'D').astype(float).values)
    b_l.append(1); b_u.append(1)

    # 5. RBs: 2 to 3
    A_rows.append((df['pos'] == 'RB').astype(float).values)
    b_l.append(2); b_u.append(3)

    # 6. WRs: 3 to 4
    A_rows.append((df['pos'] == 'WR').astype(float).values)
    b_l.append(3); b_u.append(4)

    # 7. TEs: 1 to 2
    A_rows.append((df['pos'] == 'TE').astype(float).values)
    b_l.append(1); b_u.append(2)

    # 8. Flex: RB + WR + TE == 7
    A_rows.append(df['pos'].isin(['RB', 'WR', 'TE']).astype(float).values)
    b_l.append(7); b_u.append(7)

    # 9. Max 4 players from the same team
    for t in df['team'].unique():
        A_rows.append((df['team'] == t).astype(float).values)
        b_l.append(0); b_u.append(4)

    # 10. Stack Constraints
    if stack_qb:
        is_qb = (df['name'].str.lower() == stack_qb.lower()).astype(float).values
        A_rows.append(is_qb); b_l.append(1); b_u.append(1)
    elif stack_team:
        is_team_qb = ((df['team'] == stack_team) & (df['pos'] == 'QB')).astype(float).values
        A_rows.append(is_team_qb); b_l.append(1); b_u.append(1)

    if stack_team:
        # At least 1 WR or TE from the QB's team
        is_pass_catcher = ((df['team'] == stack_team) & (df['pos'].isin(['WR', 'TE']))).astype(float).values
        A_rows.append(is_pass_catcher); b_l.append(1); b_u.append(3)

    if stack_opp:
        # At least 1 bring-back skill player from opposing team
        is_bringback = ((df['team'] == stack_opp) & (df['pos'].isin(['WR', 'TE', 'RB']))).astype(float).values
        A_rows.append(is_bringback); b_l.append(1); b_u.append(2)

    # 11. Force / Exclude players
    if force_players:
        for p in force_players:
            is_p = (df['name'].str.lower() == p.lower()).astype(float).values
            if is_p.sum() > 0:
                A_rows.append(is_p); b_l.append(1); b_u.append(1)

    if exclude_players:
        for p in exclude_players:
            is_p = (df['name'].str.lower() == p.lower()).astype(float).values
            if is_p.sum() > 0:
                A_rows.append(is_p); b_l.append(0); b_u.append(0)

    # D/ST cannot play against our QB or RB
    # We can enforce this iteratively or by adding constraints

    A = np.array(A_rows)
    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones(n)
    bounds = Bounds(0, 1)

    res = milp(c=c, constraints=constraints, integrality=integrality, bounds=bounds)

    if not res.success:
        return None, None

    selected_idx = np.where(res.x > 0.5)[0]
    lineup = df.iloc[selected_idx].copy()
    
    # Check D/ST conflict
    dst_row = lineup[lineup['pos'] == 'D'].iloc[0]
    opp_of_dst = dst_row['opp']
    offensive_opps = lineup[lineup['pos'] != 'D']['team'].tolist()
    if opp_of_dst in offensive_opps:
        # Add conflict constraint and re-solve
        exclude_dst = (df['pos'] == 'D') & (df['team'] == dst_row['team'])
        return solve_tournament_lineup(
            df_pool, stack_team, stack_opp, stack_qb, stack_wr_te, stack_bringback,
            force_players, (exclude_players or []) + [dst_row['name']],
            max_salary, min_salary
        )

    return lineup, (lineup['salary'].sum(), lineup['proj'].sum())

def display(title, lineup, stats):
    if lineup is None:
        print(f"\n{title}: No feasible solution found.")
        return
    tot_sal, tot_proj = stats
    print(f"\n{'#'*80}")
    print(f" {title.upper()} ")
    print(f"{'#'*80}")
    order_map = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'D': 5}
    lineup_sorted = lineup.sort_values(by=['pos', 'salary'], key=lambda x: x.map(order_map) if x.name == 'pos' else x, ascending=[True, False])
    
    for _, r in lineup_sorted.iterrows():
        pos_str = r['pos']
        print(f"  {pos_str:<4} | {r['name']:<22} | {r['team']:<4} vs {r['opp']:<4} | ${r['salary']:<5} | Proj: {r['proj']:<5.2f} pts | Implied: {r['team_implied']:<4.1f} | Softness: #{r['soft_rank']}")
    
    print(f"{'-'*80}")
    print(f"  TOTAL SALARY: ${tot_sal:,} / $60,000  (Remaining: ${60000 - tot_sal:,})")
    print(f"  TOTAL PROJECTED POINTS: {tot_proj:.2f} pts")
    print(f"  VALUE MULTIPLIER: {tot_proj / (tot_sal / 1000):.2f}x")
    print(f"{'#'*80}\n")

if __name__ == '__main__':
    df_pool = pd.read_csv('data/optimized_player_pool.csv')

    # A. The Cincinnati Shootout GPP Stack (Burrow + Chase + TB Bringback)
    l_cin, s_cin = solve_tournament_lineup(df_pool, stack_team='CIN', stack_opp='TB', stack_qb='Joe Burrow')
    display("Tournament Option A: Cincinnati Shootout Stack (Burrow + Chase + TB Bring-back)", l_cin, s_cin)

    # B. The Detroit Dome Juggernaut Stack (Goff + St. Brown + Olave Bringback)
    l_det, s_det = solve_tournament_lineup(df_pool, stack_team='DET', stack_opp='NO', stack_qb='Jared Goff')
    display("Tournament Option B: Detroit Dome Juggernaut Stack (Goff + St. Brown + Olave)", l_det, s_det)

    # C. The LA Chargers Game Script Monopoly Stack (Herbert + McConkey + Hampton + McBride)
    l_lac, s_lac = solve_tournament_lineup(df_pool, stack_team='LAC', stack_opp='ARI', stack_qb='Justin Herbert')
    display("Tournament Option C: Chargers #1 Total Smash Stack (Herbert + McConkey + Hampton + McBride)", l_lac, s_lac)

    # D. The Dual-Smash RB Juggernaut Stack (Hurts + Goedert + Saquon + Hampton)
    l_phi, s_phi = solve_tournament_lineup(df_pool, stack_team='PHI', stack_opp='WAS', stack_qb='Jalen Hurts', force_players=['Saquon Barkley', 'Omarion Hampton'])
    display("Tournament Option D: Philly Dual-Smash Ground & Pound (Hurts + Goedert + Saquon + Hampton)", l_phi, s_phi)
