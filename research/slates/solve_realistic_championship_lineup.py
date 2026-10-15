import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

def find_championship_lineup():
    df_raw = pd.read_csv('data/optimized_player_pool.csv')
    
    # Filter only legitimate starters / key contributors
    # Minimum projection:
    # QB >= 14.0, RB >= 9.0, WR >= 7.5, TE >= 6.5, D >= 5.0
    valid_cond = (
        ((df_raw['pos'] == 'QB') & (df_raw['proj'] >= 14.0)) |
        ((df_raw['pos'] == 'RB') & (df_raw['proj'] >= 8.5) & (df_raw['salary'] >= 4500)) |
        ((df_raw['pos'] == 'WR') & (df_raw['proj'] >= 8.0) & (df_raw['salary'] >= 4500)) |
        ((df_raw['pos'] == 'TE') & (df_raw['proj'] >= 6.5) & (df_raw['salary'] >= 4500)) |
        ((df_raw['pos'] == 'D'))
    )
    df = df_raw[valid_cond].reset_index(drop=True).copy()
    n = len(df)
    print(f"Filtered pool size: {n} players")

    # Let's inspect options by testing 3 distinct, high-leverage tournament architectures:
    # 1. The Cincinnati High-Total Shootout Stack: Burrow + Chase + TB Bringback (Egbuka, Godwin, or Otton) + Hampton + Jeanty
    # 2. The LA Chargers #1 Total Leverage Stack: Herbert + McConkey + Hampton + Arizona Bringback (Harrison Jr. or McBride) + Chase
    # 3. The Philadelphia High-Floor Juggernaut: Hurts + Goedert + Saquon + Hampton + Chase
    
    architectures = [
        {
            'name': 'Cincinnati 50.5 Shootout Championship Build (Burrow + Chase + Godwin/Egbuka + Hampton + Jeanty)',
            'qb': 'Joe Burrow',
            'team': 'CIN',
            'opp': 'TB',
            'force': ['Ja\'Marr Chase', 'Omarion Hampton', 'Ashton Jeanty']
        },
        {
            'name': 'Chargers 28.75 Implied Total Domination (Herbert + McConkey + Hampton + Harrison Jr. + Chase)',
            'qb': 'Justin Herbert',
            'team': 'LAC',
            'opp': 'ARI',
            'force': ['Ladd McConkey', 'Omarion Hampton', 'Ja\'Marr Chase']
        },
        {
            'name': 'Detroit Ford Field Dome Juggernaut (Goff + St. Brown + Olave + Hampton + Jeanty)',
            'qb': 'Jared Goff',
            'team': 'DET',
            'opp': 'NO',
            'force': ['Amon-Ra St. Brown', 'Chris Olave', 'Omarion Hampton']
        },
        {
            'name': 'Philly Ground & Air Dominance (Hurts + Goedert + Saquon + Hampton + Chase)',
            'qb': 'Jalen Hurts',
            'team': 'PHI',
            'opp': 'WAS',
            'force': ['Saquon Barkley', 'Dallas Goedert', 'Omarion Hampton', 'Ja\'Marr Chase']
        }
    ]

    for arch in architectures:
        c = -df['proj'].values
        A_rows = []
        b_l = []
        b_u = []

        # 1. Total players = 9
        A_rows.append(np.ones(n))
        b_l.append(9); b_u.append(9)

        # 2. Total Salary <= 60000, >= 59000
        A_rows.append(df['salary'].values)
        b_l.append(59000); b_u.append(60000)

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

        # 9. Max 4 per NFL team
        for t in df['team'].unique():
            A_rows.append((df['team'] == t).astype(float).values)
            b_l.append(0); b_u.append(4)

        # QB constraint
        if 'qb' in arch:
            is_qb = (df['name'].str.lower() == arch['qb'].lower()).astype(float).values
            A_rows.append(is_qb); b_l.append(1); b_u.append(1)

        # Stack team pass-catcher constraint
        if 'team' in arch:
            is_pc = ((df['team'] == arch['team']) & (df['pos'].isin(['WR', 'TE']))).astype(float).values
            A_rows.append(is_pc); b_l.append(1); b_u.append(3)

        # Opponent bring-back
        if 'opp' in arch:
            is_bb = ((df['team'] == arch['opp']) & (df['pos'].isin(['WR', 'TE', 'RB']))).astype(float).values
            A_rows.append(is_bb); b_l.append(1); b_u.append(2)

        # Forced players
        if 'force' in arch:
            for p in arch['force']:
                is_p = (df['name'].str.lower() == p.lower()).astype(float).values
                if is_p.sum() > 0:
                    A_rows.append(is_p); b_l.append(1); b_u.append(1)

        # D/ST cannot oppose QB or RB
        # Solve
        A = np.array(A_rows)
        constraints = LinearConstraint(A, b_l, b_u)
        integrality = np.ones(n)
        bounds = Bounds(0, 1)

        res = milp(c=c, constraints=constraints, integrality=integrality, bounds=bounds)
        if res.success:
            lineup = df.iloc[np.where(res.x > 0.5)[0]].copy()
            # Verify D/ST conflict
            dst = lineup[lineup['pos'] == 'D'].iloc[0]
            off_teams = lineup[lineup['pos'] != 'D']['team'].unique().tolist()
            if dst['opp'] in off_teams:
                # Exclude conflicting D/ST
                is_bad_dst = (df['pos'] == 'D') & (df['team'] == dst['team'])
                A_rows.append(is_bad_dst.astype(float).values)
                b_l.append(0); b_u.append(0)
                A = np.array(A_rows)
                constraints = LinearConstraint(A, b_l, b_u)
                res = milp(c=c, constraints=constraints, integrality=integrality, bounds=bounds)
                if res.success:
                    lineup = df.iloc[np.where(res.x > 0.5)[0]].copy()

            tot_sal = lineup['salary'].sum()
            tot_proj = lineup['proj'].sum()
            print(f"\n{'='*80}")
            print(f" {arch['name'].upper()} ")
            print(f"{'='*80}")
            order = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'D': 5}
            lineup_s = lineup.sort_values(by=['pos', 'salary'], key=lambda x: x.map(order) if x.name == 'pos' else x, ascending=[True, False])
            
            # Determine Flex
            counts = {'RB': 0, 'WR': 0, 'TE': 0}
            for _, row in lineup_s.iterrows():
                p = row['pos']
                slot = p
                if p in counts:
                    counts[p] += 1
                    if (p == 'RB' and counts[p] > 2) or (p == 'WR' and counts[p] > 3) or (p == 'TE' and counts[p] > 1):
                        slot = f"FLEX ({p})"
                print(f"  {slot:<9} | {row['name']:<22} | {row['team']:<4} vs {row['opp']:<4} | ${row['salary']:<5} | Proj: {row['proj']:<5.2f} pts | Implied: {row['team_implied']:<4.1f} | Softness: #{row['soft_rank']}")
            print(f"{'-'*80}")
            print(f"  TOTAL SALARY: ${tot_sal:,} / $60,000  (Remaining: ${60000 - tot_sal:,})")
            print(f"  TOTAL PROJECTED POINTS: {tot_proj:.2f} pts")
            print(f"  VALUE RATIO: {tot_proj / (tot_sal / 1000):.2f}x")
            print(f"{'='*80}\n")
        else:
            print(f"Failed to solve for {arch['name']}")

if __name__ == '__main__':
    find_championship_lineup()
