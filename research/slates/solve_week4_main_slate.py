"""
Dedicated Week 4 Main Slate 3-Game Matrix Solver & Multi-Architecture Optimizer
Ingests:
  - CSV: data/FanDuel-NFL-2026 MDT-10 MDT-04 MDT-134747-players-list.csv
  - Vegas: data/vegas_movement_2026.json
  - PFF: data/pff_scouting_2026.json
  - DvP: data/nfl_dvp_proprietary_2026.json
  - Injuries: data/injuries_live_2026.json
  - Micro-metrics: data/week_1_receiver_micro_metrics_2026.json, data/week_1_running_back_micro_metrics_2026.json
"""

import sys
import os
from pathlib import Path
import json
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

# Import loader from solve_main_slate_matrix
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.solve_main_slate_matrix import compute_bayesian_base_projection

CSV_PATH = "data/FanDuel-NFL-2026 MDT-10 MDT-04 MDT-134747-players-list.csv"
VEGAS_PATH = "data/vegas_movement_2026.json"
PFF_PATH = "data/pff_scouting_2026.json"
DVP_PATH = "data/nfl_dvp_proprietary_2026.json"
INJURIES_PATH = "data/injuries_live_2026.json"
DEPTH_CHART_PATH = "data/nfl_depth_charts_2026.json"

def load_and_enrich_week4():
    df = pd.read_csv(CSV_PATH)
    from src.core.nfl_rosters import normalize_roster_dataframe
    df = normalize_roster_dataframe(df)

    df['name'] = df['Nickname'].str.strip()
    df['pos'] = df['Position'].str.strip()
    df['team'] = df['Team'].str.strip().replace({'WSH': 'WAS', 'JAX': 'JAC'})
    df['opp'] = df['Opponent'].str.strip().replace({'WSH': 'WAS', 'JAX': 'JAC'})
    df['salary'] = df['Salary'].astype(int)
    df['fppg'] = df['FPPG'].fillna(0.0).astype(float)
    df['injury'] = df['Injury Indicator'].fillna('').str.strip()

    # Filter out confirmed inactive players
    import re
    live_out_names = set()
    if os.path.exists(INJURIES_PATH):
        with open(INJURIES_PATH, 'r', encoding='utf-8') as f:
            inj_data = json.load(f)
            for inj in inj_data.get('injuries', []):
                st = str(inj.get('status', '')).upper()
                if inj.get('is_out') or st in ('OUT', 'IR', 'INACTIVE', 'DOUBTFUL') or 'IR' in st:
                    clean_n = re.sub(r"[^\w\s]", "", str(inj.get('name', '')).lower()).strip()
                    if clean_n:
                        live_out_names.add(clean_n)

    df['norm_name'] = df['name'].str.lower().apply(lambda x: re.sub(r"[^\w\s]", "", str(x)).strip())
    # Exclude IR and O players
    df = df[~df['injury'].isin(['IR', 'O']) & ~df['norm_name'].isin(live_out_names)].copy()

    # Explicit injury exclusions based on verified Week 4 wire:
    # Justin Jefferson (O), DeVonta Smith (O), Caleb Williams (O), Baker Mayfield (O), Breece Hall (O), Dallas Goedert (O)
    df = df[~df['name'].isin(['Justin Jefferson', 'DeVonta Smith', 'Caleb Williams', 'Baker Mayfield', 'Breece Hall', 'Dallas Goedert', 'Hollywood Brown', 'Colbie Young', 'Adonai Mitchell'])].copy()

    # Load Vegas data with team alias normalization
    vegas_games = []
    vegas_team_map = {}
    if os.path.exists(VEGAS_PATH):
        with open(VEGAS_PATH, 'r') as f:
            v_data = json.load(f)
            for g in v_data.get('games', []):
                away = {'WSH': 'WAS', 'JAX': 'JAC'}.get(g.get('away_team'), g.get('away_team'))
                home = {'WSH': 'WAS', 'JAX': 'JAC'}.get(g.get('home_team'), g.get('home_team'))
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

    # Load DvP rankings
    dvp_dict = {}
    if os.path.exists(DVP_PATH):
        with open(DVP_PATH, 'r') as f:
            d_data = json.load(f)
            for pos in ['QB', 'RB', 'WR', 'TE']:
                dvp_dict[pos] = {}
                for item in d_data.get(pos, []):
                    tm = {'WSH': 'WAS', 'JAX': 'JAC'}.get(item['pro_team'], item['pro_team'])
                    dvp_dict[pos][tm] = item['rank_softness']

    # Load PFF trench
    pff_dict = {}
    if os.path.exists(PFF_PATH):
        with open(PFF_PATH, 'r') as f:
            pff_dict = json.load(f).get('teams', {})
            for t1, t2 in [('WAS', 'WSH'), ('WSH', 'WAS'), ('JAC', 'JAX'), ('JAX', 'JAC')]:
                if t1 in pff_dict and t2 not in pff_dict:
                    pff_dict[t2] = pff_dict[t1]

    # Verified Starters from Depth Charts
    active_starter_qbs = set()
    verified_starters = set()
    if os.path.exists(DEPTH_CHART_PATH):
        with open(DEPTH_CHART_PATH, "r", encoding="utf-8") as f:
            dc_teams = json.load(f).get("teams", {})
            for tm, tdata in dc_teams.items():
                tm_code = {'WSH': 'WAS', 'JAX': 'JAC'}.get(tm, tm)
                off = tdata.get("offense", {})
                for q_entry in off.get("qb", []):
                    q_n = re.sub(r"[^\w\s]", "", str(q_entry.get("name", "")).lower()).strip()
                    if q_n and q_n not in live_out_names:
                        active_starter_qbs.add((tm_code, q_n))
                        verified_starters.add((tm_code, q_n))
                        break
                for r_entry in off.get("rb", [])[:2]:
                    r_n = re.sub(r"[^\w\s]", "", str(r_entry.get("name", "")).lower()).strip()
                    if r_n:
                        verified_starters.add((tm_code, r_n))
                for wslot in ["wr1", "wr2", "wr3"]:
                    for w_entry in off.get(wslot, [])[:1]:
                        w_n = re.sub(r"[^\w\s]", "", str(w_entry.get("name", "")).lower()).strip()
                        if w_n:
                            verified_starters.add((tm_code, w_n))
                for t_entry in off.get("te", [])[:1]:
                    t_n = re.sub(r"[^\w\s]", "", str(t_entry.get("name", "")).lower()).strip()
                    if t_n:
                        verified_starters.add((tm_code, t_n))

    # Add verified injury replacements to starters
    verified_starters.add(('NYJ', 'braelon allen'))
    verified_starters.add(('CHI', 'case keenum'))
    verified_starters.add(('CHI', 'luther burden iii'))
    active_starter_qbs.add(('CHI', 'case keenum'))

    # Calculate GPP Projections with Bayesian shrinkage & micro-metrics
    gpp_projs = []
    ceiling_factors = []
    for idx, row in df.iterrows():
        pos = row['pos']
        team = row['team']
        opp = row['opp']
        name = row['name']
        norm_name = row['norm_name']
        salary = row['salary']
        raw_fppg = row['fppg']
        played = row.get('Played', 3)

        # QB Starting Check
        if pos == 'QB':
            is_starter = (team, norm_name) in active_starter_qbs
            if not is_starter:
                # Backup QB gets 0
                gpp_projs.append(0.0)
                ceiling_factors.append(0.0)
                continue
            elif is_starter and raw_fppg < 5.0:
                raw_fppg = max(14.0, (salary / 1000.0) * 2.25)

        is_starter = ((team, norm_name) in verified_starters) or (raw_fppg >= 9.0) or (salary >= 6400)
        # Apply Bayesian shrinkage (60% quant prior, 40% in-season FPPG)
        base = compute_bayesian_base_projection(pos, salary, raw_fppg, played, is_starter=is_starter)

        v_meta = vegas_team_map.get(team, {})
        g_info = v_meta.get('game', {})
        ou = g_info.get('ou', 44.0)
        dome = g_info.get('dome', False)
        implied = v_meta.get('implied', 21.0)

        net_boost = 0.0

        # 1. Game Total & Implied Total Boost
        if ou >= 50.0:
            net_boost += 0.10
        elif ou >= 47.0:
            net_boost += 0.06
        elif ou < 40.0 and pos != 'D':
            net_boost -= 0.10

        if implied >= 26.0:
            net_boost += 0.06
        elif implied <= 18.0 and pos != 'D':
            net_boost -= 0.08

        # 2. Dome Track Boost
        if dome and pos in ['QB', 'WR', 'TE']:
            net_boost += 0.06

        # 3. DvP Matchup Softness
        pos_dvp = dvp_dict.get(pos, {}).get(opp, 16)
        if pos_dvp <= 5:
            net_boost += 0.10
        elif pos_dvp <= 10:
            net_boost += 0.05
        elif pos_dvp >= 28:
            net_boost -= 0.08

        # 4. PFF Trench Mismatch
        team_trench = pff_dict.get(team, {})
        opp_trench = pff_dict.get(opp, {})
        if pos == 'RB':
            opp_run_def_rank = opp_trench.get('defensive_line_front', {}).get('rank', 16)
            team_run_blk_grade = team_trench.get('offensive_line', {}).get('run_block_grade', 70.0)
            if opp_run_def_rank >= 25:
                net_boost += 0.12
            if team_run_blk_grade >= 85.0:
                net_boost += 0.06

        # 5. Dual-threat QBs
        if pos == 'QB':
            opp_pass_rush_rank = opp_trench.get('defensive_line_front', {}).get('rank', 16)
            is_mobile_qb = name in ['Josh Allen', 'Lamar Jackson', 'Jalen Hurts', 'Kyler Murray']
            if is_mobile_qb and opp_pass_rush_rank <= 10:
                net_boost += 0.08

        # 6. Defense Disruption
        if pos == 'D':
            d_pass_rush = team_trench.get('defensive_line_front', {}).get('pass_rush_grade', 70.0)
            opp_pass_blk = opp_trench.get('offensive_line', {}).get('pass_block_grade', 70.0)
            opp_implied = g_info.get('away_imp' if v_meta.get('is_home') else 'home_imp', 21.0)
            if opp_implied <= 18.0:
                net_boost += 0.20
            elif ou <= 40.0:
                net_boost += 0.15

        # 7. Specific Quant Breakout & Usurper Boosts (Week 4 Radar)
        if name == 'Braelon Allen': # Breece Hall out
            base = max(base, 13.5)
            net_boost += 0.15
        elif name == 'Luther Burden III': # #1 ASS +0.26
            base = max(base, 12.0)
            net_boost += 0.15
        elif name == 'Kenyon Sadiq': # #1 Move TE
            base = max(base, 10.5)
            net_boost += 0.12
        elif name == 'Brock Bowers': # Alpha TE 25.6 FP
            base = max(base, 14.5)
            net_boost += 0.10
        elif name == 'George Kittle': # 13.8 FP
            base = max(base, 12.0)
            net_boost += 0.08
        elif name == 'Mike Gesicki': # Big slot in 51.5 O/U shootout
            base = max(base, 11.0)
            net_boost += 0.12
        elif name == 'Brian Thomas Jr.': # High-pace shootout vacuum
            base = max(base, 10.0)
            net_boost += 0.12
        elif name == 'Matthew Golden': # 12 targets on TNF
            base = max(base, 12.0)
            net_boost += 0.10

        mult = 1.0 + float(np.tanh(net_boost / 0.35) * 0.25)
        raw_proj = base * mult

        # Implied Team Total Reality Ceiling Caps
        if pos in ['WR', 'TE']:
            max_allowed = max(11.0, implied * 1.15)
            gpp_proj = round(min(raw_proj, max_allowed), 2)
        elif pos == 'RB':
            max_allowed = max(13.0, implied * 1.30)
            gpp_proj = round(min(raw_proj, max_allowed), 2)
        elif pos == 'QB':
            max_allowed = max(15.0, implied * 1.25)
            gpp_proj = round(min(raw_proj, max_allowed), 2)
        else:
            gpp_proj = round(raw_proj, 2)

        gpp_projs.append(gpp_proj)
        ceiling_factors.append(round(mult, 2))

    df['gpp_proj'] = gpp_projs
    df['ceiling_factor'] = ceiling_factors
    return df, vegas_games

def solve_week4_matrix(df, primary_game, mini_game_1, mini_game_2, dst_team=None, min_salary=59100, max_salary=59800, late_swap_flex=True):
    # Late window kickoff teams on this slate (4:05 PM / 4:25 PM ET / 2:05 / 2:25 PM MT):
    # MIA, MIN, KC, LV, DEN, SF, LAC, SEA
    late_window_teams = {'MIA', 'MIN', 'KC', 'LV', 'DEN', 'SF', 'LAC', 'SEA'}

    df_pool = df[(df['gpp_proj'] >= 4.0) | (df['pos'] == 'D')].reset_index(drop=True).copy()
    n = len(df_pool)
    c = -df_pool['gpp_proj'].values

    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n)); b_l.append(9); b_u.append(9)

    # 2. Total Salary ($59,100 to $59,800, leaving $200 - $900 unspent)
    A_rows.append(df_pool['salary'].values); b_l.append(min_salary); b_u.append(max_salary)

    # 3. Exactly 1 QB
    A_rows.append((df_pool['pos'] == 'QB').astype(float).values); b_l.append(1); b_u.append(1)

    # 4. Exactly 1 D/ST
    A_rows.append((df_pool['pos'] == 'D').astype(float).values); b_l.append(1); b_u.append(1)

    # 5. RBs: 2 to 3
    A_rows.append((df_pool['pos'] == 'RB').astype(float).values); b_l.append(2); b_u.append(3)

    # 6. WRs: 3 to 4
    A_rows.append((df_pool['pos'] == 'WR').astype(float).values); b_l.append(3); b_u.append(4)

    # 7. TEs: 1 to 2 (allow 2-TE build!)
    A_rows.append((df_pool['pos'] == 'TE').astype(float).values); b_l.append(1); b_u.append(2)

    # 8. Flex total = 7
    A_rows.append(df_pool['pos'].isin(['RB', 'WR', 'TE']).astype(float).values); b_l.append(7); b_u.append(7)

    # 9. Primary Game Constraints (3 to 4 players)
    p_t1, p_t2 = primary_game
    primary_mask = df_pool['team'].isin([p_t1, p_t2]).astype(float).values
    A_rows.append(primary_mask); b_l.append(3); b_u.append(4)

    # QB MUST come from primary game
    qb_primary_mask = ((df_pool['pos'] == 'QB') & (df_pool['team'].isin([p_t1, p_t2]))).astype(float).values
    A_rows.append(qb_primary_mask); b_l.append(1); b_u.append(1)

    # QB paired with at least one WR/TE from same team
    t1_pass = ((df_pool['team'] == p_t1) & (df_pool['pos'].isin(['WR', 'TE']))).astype(float).values
    t1_qb = ((df_pool['team'] == p_t1) & (df_pool['pos'] == 'QB')).astype(float).values
    A_rows.append(t1_pass - t1_qb); b_l.append(0); b_u.append(9)

    t2_pass = ((df_pool['team'] == p_t2) & (df_pool['pos'].isin(['WR', 'TE']))).astype(float).values
    t2_qb = ((df_pool['team'] == p_t2) & (df_pool['pos'] == 'QB')).astype(float).values
    A_rows.append(t2_pass - t2_qb); b_l.append(0); b_u.append(9)

    # Bring-back: at least 1 player from each side of primary game
    A_rows.append((df_pool['team'] == p_t1).astype(float).values); b_l.append(1); b_u.append(3)
    A_rows.append((df_pool['team'] == p_t2).astype(float).values); b_l.append(1); b_u.append(3)

    # 10. Secondary Mini-Game 1 (2 players: 1 from each team)
    m1_t1, m1_t2 = mini_game_1
    A_rows.append((df_pool['team'] == m1_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m1_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 11. Secondary Mini-Game 2 (2 players: 1 from each team)
    m2_t1, m2_t2 = mini_game_2
    A_rows.append((df_pool['team'] == m2_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m2_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 12. D/ST selection
    if dst_team:
        A_rows.append(((df_pool['pos'] == 'D') & (df_pool['team'] == dst_team)).astype(float).values)
        b_l.append(1); b_u.append(1)

    # Anti-Cannibalization: D/ST cannot play against any offensive player
    for idx_dst, row_dst in df_pool[df_pool['pos'] == 'D'].iterrows():
        dst_tm = row_dst['team']
        dst_opp = row_dst['opp']
        opp_offense = ((df_pool['team'] == dst_opp) & (df_pool['pos'] != 'D')).astype(float).values
        dst_ind = (np.arange(n) == idx_dst).astype(float)
        A_rows.append(opp_offense + 8.0 * dst_ind)
        b_l.append(-np.inf)
        b_u.append(8.0)

    # Late Swap Discipline: at least 1 offensive player must be from late window
    if late_swap_flex:
        late_offense = (df_pool['team'].isin(late_window_teams) & (df_pool['pos'] != 'D')).astype(float).values
        A_rows.append(late_offense); b_l.append(1); b_u.append(7)

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

if __name__ == '__main__':
    df, vegas_games = load_and_enrich_week4()
    
    architectures = [
        ("Architecture 1: JAC @ CIN (O/U 51.5 Shootout) + NYJ @ CHI (Value Engine) + KC @ LV (Dome Mini)",
         ('JAC', 'CIN'), ('NYJ', 'CHI'), ('KC', 'LV'), 'CHI'),
        ("Architecture 2: JAC @ CIN (O/U 51.5 Shootout) + DAL @ HOU (Dome Track) + KC @ LV (Dome Mini)",
         ('JAC', 'CIN'), ('DAL', 'HOU'), ('KC', 'LV'), 'CHI'),
        ("Architecture 3: DAL @ HOU (O/U 48.5 Dome Primary) + JAC @ CIN (Shootout Mini) + NYJ @ CHI (Value Mini)",
         ('DAL', 'HOU'), ('JAC', 'CIN'), ('NYJ', 'CHI'), 'CHI'),
        ("Architecture 4: NE @ BUF (O/U 49.5 Rushing QB Primary) + JAC @ CIN (Shootout Mini) + NYJ @ CHI (Value Mini)",
         ('NE', 'BUF'), ('JAC', 'CIN'), ('NYJ', 'CHI'), 'CHI'),
    ]

    for title, prim, m1, m2, dst in architectures:
        print(f"\n=======================================================")
        print(title)
        print(f"=======================================================")
        roster = solve_week4_matrix(df, prim, m1, m2, dst_team=dst, min_salary=58500, max_salary=59800)
        if roster is None:
            # Try without forcing dst
            roster = solve_week4_matrix(df, prim, m1, m2, dst_team=None, min_salary=58000, max_salary=59800)
        
        if roster is not None:
            cols = ['pos', 'name', 'team', 'opp', 'salary', 'fppg', 'gpp_proj']
            print(roster[cols].sort_values(by=['pos', 'salary'], ascending=[True, False]).to_string(index=False))
            spent = roster['salary'].sum()
            print(f"\nTotal Spent: ${spent:,} | Remaining: ${60000 - spent:,} | Projected: {roster['gpp_proj'].sum():.2f} FP")
        else:
            print("Could not solve with current constraints.")
