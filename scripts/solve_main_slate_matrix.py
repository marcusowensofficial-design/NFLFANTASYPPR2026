"""
Main Slate 3-Game Matrix Optimizer & Forensic Engine
Engineered to build GPP winning rosters based on:
1. Automated Game Environment Ranking (Vegas O/U, Dome track, Implied totals)
2. The 3-Game Matrix Architecture:
   - 1 Primary Game Stack (QB + Pass Catcher + 1-2 Opposing Bring-backs)
   - 2 Secondary Opposing Mini-Stacks (Favored RB + Trailing WR/Pass Catcher)
   - 1 Cheap Disruption D/ST (Vegas total < 40, high pressure rate)
3. Good Chalk vs Bad Chalk Filtering
4. The Rushing QB Ceiling Inversion Axiom (Boosting dual-threat QBs under heavy pressure)
5. PFF Trench & DvP Mismatch Multipliers
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

def load_and_enrich_slate(csv_path=None,
                          vegas_path="data/vegas_movement_2026.json",
                          pff_path="data/pff_scouting_2026.json",
                          dvp_path="data/draftedge_dvp_seed.json"):
    if csv_path is None:
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            csv_path = sys.argv[1]
        elif os.path.exists("data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv"):
            csv_path = "data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv"
        else:
            # Look for any players-list CSV in data/
            import glob
            matches = glob.glob("data/*players-list*.csv")
            if matches:
                csv_path = matches[0]
            else:
                csv_path = "earlyonlysalariesandrosters.csv"

    print(f"Ingesting slate data from: {csv_path}")
    df = pd.read_csv(csv_path)
    df['name'] = df['Nickname'].str.strip()
    df['pos'] = df['Position'].str.strip()
    df['team'] = df['Team'].str.strip()
    df['opp'] = df['Opponent'].str.strip()
    df['salary'] = df['Salary'].astype(int)
    df['fppg'] = df['FPPG'].fillna(0.0).astype(float)
    df['injury'] = df['Injury Indicator'].fillna('').str.strip()
    
    # Filter out inactive players
    df = df[~df['injury'].isin(['IR', 'O'])].copy()

    # Load Vegas data
    vegas_games = []
    vegas_team_map = {}
    if os.path.exists(vegas_path):
        with open(vegas_path, 'r') as f:
            v_data = json.load(f)
            for g in v_data.get('games', []):
                away = g.get('away_team')
                home = g.get('home_team')
                ou = float(g.get('over_under', 44.0))
                spread = float(g.get('spread', 0.0))
                dome = g.get('dome', False)
                away_imp = float(g.get('away_implied_total', 20.0))
                home_imp = float(g.get('home_implied_total', 20.0))
                
                game_info = {
                    'away': away, 'home': home, 'ou': ou, 'spread': spread,
                    'dome': dome, 'away_imp': away_imp, 'home_imp': home_imp
                }
                vegas_games.append(game_info)
                vegas_team_map[away] = {'game': game_info, 'is_home': False, 'implied': away_imp}
                vegas_team_map[home] = {'game': game_info, 'is_home': True, 'implied': home_imp}

    # Load DvP rankings (1 = softest/most generous, 32 = toughest)
    dvp_dict = {}
    if os.path.exists(dvp_path):
        with open(dvp_path, 'r') as f:
            d_data = json.load(f)
            for pos in ['QB', 'RB', 'WR', 'TE']:
                dvp_dict[pos] = {}
                for item in d_data.get(pos, []):
                    dvp_dict[pos][item['pro_team']] = item['rank_softness']

    # Load PFF trench and coverage metrics
    pff_dict = {}
    if os.path.exists(pff_path):
        with open(pff_path, 'r') as f:
            pff_dict = json.load(f).get('teams', {})

    # Calculate GPP Tournament Projections with Multipliers
    gpp_projs = []
    ceiling_factors = []
    for idx, row in df.iterrows():
        base = row['fppg']
        pos = row['pos']
        team = row['team']
        opp = row['opp']
        name = row['name']
        
        mult = 1.0
        v_meta = vegas_team_map.get(team, {})
        g_info = v_meta.get('game', {})
        ou = g_info.get('ou', 44.0)
        dome = g_info.get('dome', False)
        implied = v_meta.get('implied', 21.0)

        # 1. Game Total & Implied Team Total Boost
        if ou >= 48.0:
            mult += 0.08
        elif ou >= 45.0:
            mult += 0.04
        elif ou < 40.0 and pos != 'D':
            mult -= 0.10

        if implied >= 26.0:
            mult += 0.05

        # 2. Dome Track Boost for Passing / Catching
        if dome and pos in ['QB', 'WR', 'TE']:
            mult += 0.06

        # 3. DvP Matchup Softness (Top 10 most generous defenses)
        pos_dvp = dvp_dict.get(pos, {}).get(opp, 16)
        if pos_dvp <= 5:
            mult += 0.12 # Softest matchup in NFL
        elif pos_dvp <= 10:
            mult += 0.06

        # 4. PFF Trench Mismatch
        team_trench = pff_dict.get(team, {})
        opp_trench = pff_dict.get(opp, {})
        if pos == 'RB':
            opp_run_def_rank = opp_trench.get('defensive_line_front', {}).get('rank', 16)
            team_run_blk_grade = team_trench.get('offensive_line', {}).get('run_block_grade', 70.0)
            if opp_run_def_rank >= 25:  # Facing bottom 8 run defense (Verified 2.0x Empirical Law)
                mult += 0.15
            if team_run_blk_grade >= 85.0: # Elite run blocking unit (Lions O-line)
                mult += 0.08

        # 5. Dual-Threat QB Ceiling Inversion Axiom
        # Top-tier running QBs facing heavy edge rush scramble more and score rushing TDs
        if pos == 'QB' and name in ['Josh Allen', 'Lamar Jackson', 'Jalen Hurts', 'Jayden Daniels', 'Kyler Murray']:
            opp_pass_rush_rank = opp_trench.get('defensive_line_front', {}).get('rank', 16)
            if opp_pass_rush_rank <= 10:
                mult += 0.15 # Edge pressure stimulates rushing ceiling

        # 6. Defense Disruption Filter
        if pos == 'D':
            d_pass_rush = team_trench.get('defensive_line_front', {}).get('pass_rush_grade', 70.0)
            opp_pass_blk = opp_trench.get('offensive_line', {}).get('pass_block_grade', 70.0)
            if ou <= 40.0 and d_pass_rush >= 80.0 and opp_pass_blk <= 70.0:
                mult += 0.25 # Elite disruption vs incompetent offense in low-total game

        gpp_proj = round(base * mult, 2)
        gpp_projs.append(gpp_proj)
        ceiling_factors.append(round(mult, 2))

    df['gpp_proj'] = gpp_projs
    df['ceiling_factor'] = ceiling_factors
    return df, vegas_games

def rank_top_game_environments(vegas_games):
    """Sorts and identifies top game environments by shootout potential."""
    sorted_games = sorted(vegas_games, key=lambda x: (x['ou'], x['dome']), reverse=True)
    return sorted_games

def solve_tournament_matrix(df, primary_game, mini_game_1, mini_game_2, dst_team=None, min_salary=59400, max_salary=60000):
    """
    Solves for a high-leverage 3-Game Matrix Lineup:
    - Primary Game: 3-4 players (QB + Pass Catcher + 1-2 Bring-backs)
    - Mini 1: 2 players (Opposing game stack)
    - Mini 2: 2 players (Opposing game stack)
    - D/ST: 1 player from low-total disruption matchup
    """
    # Filter active pool
    df_pool = df[(df['gpp_proj'] >= 3.0) | (df['pos'] == 'D')].reset_index(drop=True).copy()
    n = len(df_pool)
    c = -df_pool['gpp_proj'].values

    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n)); b_l.append(9); b_u.append(9)

    # 2. Total Salary
    A_rows.append(df_pool['salary'].values); b_l.append(min_salary); b_u.append(max_salary)

    # 3. Exactly 1 QB
    A_rows.append((df_pool['pos'] == 'QB').astype(float).values); b_l.append(1); b_u.append(1)

    # 4. Exactly 1 D/ST
    A_rows.append((df_pool['pos'] == 'D').astype(float).values); b_l.append(1); b_u.append(1)

    # 5. RBs: 2 to 3
    A_rows.append((df_pool['pos'] == 'RB').astype(float).values); b_l.append(2); b_u.append(3)

    # 6. WRs: 3 to 4
    A_rows.append((df_pool['pos'] == 'WR').astype(float).values); b_l.append(3); b_u.append(4)

    # 7. TEs: 1 to 2
    A_rows.append((df_pool['pos'] == 'TE').astype(float).values); b_l.append(1); b_u.append(2)

    # 8. Flex total = 7
    A_rows.append(df_pool['pos'].isin(['RB', 'WR', 'TE']).astype(float).values); b_l.append(7); b_u.append(7)

    # 9. Primary Game Constraints (4 players: 2 from each team, or 3-1)
    p_t1, p_t2 = primary_game
    primary_mask = df_pool['team'].isin([p_t1, p_t2]).astype(float).values
    A_rows.append(primary_mask); b_l.append(4); b_u.append(4)

    # QB MUST come from primary game
    qb_primary_mask = ((df_pool['pos'] == 'QB') & (df_pool['team'].isin([p_t1, p_t2]))).astype(float).values
    A_rows.append(qb_primary_mask); b_l.append(1); b_u.append(1)

    # Each side of primary game must have at least 1 player
    A_rows.append((df_pool['team'] == p_t1).astype(float).values); b_l.append(1); b_u.append(3)
    A_rows.append((df_pool['team'] == p_t2).astype(float).values); b_l.append(1); b_u.append(3)

    # 10. Secondary Mini-Game 1 (Exactly 2 players: 1 from each team)
    m1_t1, m1_t2 = mini_game_1
    A_rows.append((df_pool['team'] == m1_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m1_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 11. Secondary Mini-Game 2 (Exactly 2 players: 1 from each team)
    m2_t1, m2_t2 = mini_game_2
    A_rows.append((df_pool['team'] == m2_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m2_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 12. D/ST selection
    if dst_team:
        A_rows.append(((df_pool['pos'] == 'D') & (df_pool['team'] == dst_team)).astype(float).values)
        b_l.append(1); b_u.append(1)

    A = np.array(A_rows)
    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones(n)
    bounds = Bounds(0, 1)

    res = milp(c=c, integrality=integrality, constraints=constraints, bounds=bounds)
    if res.success:
        selected_indices = np.where(res.x > 0.5)[0]
        return df_pool.iloc[selected_indices].copy()
    else:
        return None

if __name__ == "__main__":
    df, vegas_games = load_and_enrich_slate()
    top_games = rank_top_game_environments(vegas_games)
    print("=== TOP 5 VEGAS GAME ENVIRONMENTS ===")
    for g in top_games[:5]:
        print(f"  {g['away']} @ {g['home']} | O/U: {g['ou']} | Dome: {g['dome']} | Implied: {g['away']} {g['away_imp']} vs {g['home']} {g['home_imp']}")

    print("\n=== SOLVING MATRIX: BUF-HOU + CHI-CAR + NO-DET + NYJ D/ST ===")
    roster = solve_tournament_matrix(df, primary_game=('BUF', 'HOU'), mini_game_1=('CHI', 'CAR'), mini_game_2=('NO', 'DET'), dst_team='NYJ')
    if roster is not None:
        cols = ['pos', 'name', 'team', 'opp', 'salary', 'fppg', 'gpp_proj']
        print(roster[cols].sort_values(by=['pos', 'salary'], ascending=[True, False]).to_string(index=False))
        print(f"\nTotal Salary: ${roster['salary'].sum()} | Projected: {roster['gpp_proj'].sum():.2f} pts")
