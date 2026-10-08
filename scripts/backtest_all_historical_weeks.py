"""
Comprehensive Historical Backtesting & Calibration Engine (Weeks 1 to 4, 2026)
Evaluates model accuracy, score progression, and systematic failure modes across all 4 weeks
using ONLY pre-lock FanDuel CSVs and realized ESPN box scores.
"""

import os
import sys
import json
import urllib.request
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

sys.stdout.reconfigure(encoding='utf-8')
np.random.seed(42)

WEEKS_CONFIG = [
    {
        'week': 1,
        'date': '20260913',
        'csv': 'data/mainslate9-13-2026.csv',
        'cache': 'data/actuals_week1.json'
    },
    {
        'week': 2,
        'date': '20260920',
        'csv': 'data/9-20-26-main-slate-rosters-salaries-fd-week2.csv',
        'cache': 'data/actuals_week2.json'
    },
    {
        'week': 3,
        'date': '20260927',
        'csv': 'data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv',
        'cache': 'data/actuals_week3.json'
    },
    {
        'week': 4,
        'date': '20261004',
        'csv': 'data/FanDuel-NFL-2026 MDT-10 MDT-04 MDT-134747-players-list.csv',
        'cache': 'data/actuals_2026_10_04.json'
    }
]

# Load official NFL depth charts for verified starter and role filtering
depth_chart_starters = set()
depth_chart_alphas = set()
dc_path = "data/nfl_depth_charts_2026.json"
if os.path.exists(dc_path):
    with open(dc_path, 'r', encoding='utf-8') as f:
        dc_raw = json.load(f)
        for tm, tdata in dc_raw.get('teams', {}).items():
            off = tdata.get('offense', {})
            for p in off.get('qb', []):
                if p.get('rank') == 1:
                    depth_chart_starters.add(p.get('name'))
            for p in off.get('rb', []):
                if p.get('rank') in [1, 2]:
                    depth_chart_starters.add(p.get('name'))
            for slot in ['wr1', 'wr2', 'wr3', 'wr', 'lwr', 'rwr', 'slot']:
                for p in off.get(slot, []):
                    if p.get('rank') in [1, 2]:
                        depth_chart_starters.add(p.get('name'))
                    if p.get('rank') == 1:
                        depth_chart_alphas.add(p.get('name'))
            for p in off.get('te', []):
                if p.get('rank') in [1, 2]:
                    depth_chart_starters.add(p.get('name'))
                if p.get('rank') == 1:
                    depth_chart_alphas.add(p.get('name'))

def fetch_and_cache_actuals(date_str, cache_path):
    """Fetches full ESPN boxscore actuals for a date and saves to JSON cache."""
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    print(f"Fetching actuals from ESPN API for date {date_str}...")
    sb_url = f'http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date_str}'
    req = urllib.request.Request(sb_url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as resp:
            sb = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Scoreboard fetch error for {date_str}: {e}")
        return {'players': {}, 'dst': {}}

    actuals = {}
    dst_actuals = {}

    for ev in sb.get('events', []):
        gid = ev.get('id')
        summary_url = f'http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={gid}'
        try:
            sreq = urllib.request.Request(summary_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(sreq) as sresp:
                data = json.loads(sresp.read().decode('utf-8'))
                boxscore = data.get('boxscore', {})
                teams = boxscore.get('teams', [])
                players = boxscore.get('players', [])

                comps = ev.get('competitions', [])[0].get('competitors', [])
                team_scores = {c.get('team', {}).get('abbreviation'): int(c.get('score', 0)) for c in comps}

                for t in teams:
                    t_info = t.get('team', {})
                    t_abbr = t_info.get('abbreviation')
                    t_name = t_info.get('displayName')
                    opp_abbr = [k for k in team_scores.keys() if k != t_abbr]
                    pa = team_scores.get(opp_abbr[0], 0) if opp_abbr else 0

                    stats_dict = {s.get('name'): s.get('displayValue') for s in t.get('statistics', [])}
                    sacks = float(stats_dict.get('sacksYardsLost', '0-0').split('-')[0] if '-' in stats_dict.get('sacksYardsLost', '0') else stats_dict.get('sacks', 0) or 0)
                    ints = float(stats_dict.get('interceptions', 0) or 0)
                    fumbles_rec = float(stats_dict.get('turnovers', 0) or 0) - ints

                    if pa == 0: pa_pts = 10
                    elif pa <= 6: pa_pts = 7
                    elif pa <= 13: pa_pts = 4
                    elif pa <= 20: pa_pts = 1
                    elif pa <= 27: pa_pts = 0
                    elif pa <= 34: pa_pts = -1
                    else: pa_pts = -4

                    dst_fp = pa_pts + (sacks * 1.0) + (ints * 2.0) + (max(0, fumbles_rec) * 2.0)
                    dst_actuals[t_abbr] = round(dst_fp, 2)
                    dst_actuals[t_name] = round(dst_fp, 2)

                for p_team in players:
                    t_abbr = p_team.get('team', {}).get('abbreviation')
                    for cat in p_team.get('statistics', []):
                        cat_name = cat.get('name')
                        keys = cat.get('keys', [])
                        for ath in cat.get('athletes', []):
                            pname = ath.get('athlete', {}).get('displayName')
                            stats = ath.get('stats', [])
                            stat_dict = dict(zip(keys, stats))

                            if pname not in actuals:
                                actuals[pname] = {'py': 0, 'ptd': 0, 'int': 0, 'ry': 0, 'rtd': 0, 'rec': 0, 'recy': 0, 'rectd': 0}

                            if cat_name == 'passing':
                                actuals[pname]['py'] = float(stat_dict.get('passingYards', 0) or 0)
                                actuals[pname]['ptd'] = float(stat_dict.get('passingTouchdowns', 0) or 0)
                                actuals[pname]['int'] = float(stat_dict.get('interceptions', 0) or 0)
                            elif cat_name == 'rushing':
                                actuals[pname]['ry'] = float(stat_dict.get('rushingYards', 0) or 0)
                                actuals[pname]['rtd'] = float(stat_dict.get('rushingTouchdowns', 0) or 0)
                            elif cat_name == 'receiving':
                                actuals[pname]['rec'] = float(stat_dict.get('receptions', 0) or 0)
                                actuals[pname]['recy'] = float(stat_dict.get('receivingYards', 0) or 0)
                                actuals[pname]['rectd'] = float(stat_dict.get('receivingTouchdowns', 0) or 0)
        except Exception as e:
            pass

    player_scores = {}
    for name, s in actuals.items():
        fp = (s['py'] * 0.04) + (s['ptd'] * 4.0) - (s['int'] * 1.0) + \
             (s['ry'] * 0.1) + (s['rtd'] * 6.0) + \
             (s['rec'] * 0.5) + (s['recy'] * 0.1) + (s['rectd'] * 6.0)
        player_scores[name] = round(fp, 2)

    res = {'players': player_scores, 'dst': dst_actuals}
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    return res

def evaluate_slate(week_cfg, num_simulations=50):
    w = week_cfg['week']
    csv_file = week_cfg['csv']
    actuals = fetch_and_cache_actuals(week_cfg['date'], week_cfg['cache'])
    player_act = actuals.get('players', {})
    dst_act = actuals.get('dst', {})

    if not os.path.exists(csv_file):
        print(f"Week {w} CSV not found: {csv_file}")
        return None

    df = pd.read_csv(csv_file)
    df['name'] = df['Nickname'].str.strip()
    df['pos'] = df['Position'].str.strip()
    df['team'] = df['Team'].str.strip().replace({'WSH': 'WAS', 'JAX': 'JAC'})
    df['opp'] = df['Opponent'].str.strip().replace({'WSH': 'WAS', 'JAX': 'JAC'})
    df['salary'] = df['Salary'].astype(int)
    df['fppg'] = df['FPPG'].astype(float).fillna(0.0) if 'FPPG' in df.columns else 0.0
    inj_col = 'Injury Indicator' if 'Injury Indicator' in df.columns else 'Injury Details'
    if inj_col in df.columns:
        df['injury'] = df[inj_col].fillna('').astype(str).str.strip()
        df = df[~df['injury'].str.upper().isin(['O', 'IR', 'OUT'])].copy()

    # Base projection using empirical Bayesian prior
    projs = []
    for _, r in df.iterrows():
        pos, sal, fppg = r['pos'], r['salary'], r['fppg']
        sal_k = sal / 1000.0
        if pos == 'QB': prior = max(11.0, sal_k * 2.30 - 2.0)
        elif pos == 'RB': prior = max(6.0, sal_k * 2.05 - 1.5)
        elif pos == 'WR': prior = max(5.0, sal_k * 1.95 - 1.8)
        elif pos == 'TE': prior = max(4.0, sal_k * 1.65 - 1.8)
        elif pos == 'D': prior = max(3.0, sal_k * 1.75)
        else: prior = sal_k * 1.80

        w_bayes = 0.50 if fppg > 0 else 0.0
        projs.append(round((w_bayes * fppg) + ((1.0 - w_bayes) * prior), 2))
    df['proj'] = projs

    # Filter pool using Verified Starter and Role Opportunity Filter (Banning 0-point ghost punts)
    is_verified = (
        (df['pos'] == 'D') |
        (df['name'].isin(depth_chart_starters)) |
        (df['fppg'] >= 4.0) |
        (df['salary'] >= 5200)
    )
    pool = df[is_verified & (df['proj'] >= 4.0)].copy().reset_index(drop=True)
    N = len(pool)

    # Starting QBs with verified role
    starting_qbs = pool[(pool['pos'] == 'QB') & (pool['salary'] >= 6800)]['name'].tolist()
    if not starting_qbs:
        starting_qbs = pool[pool['pos'] == 'QB'].sort_values(by='salary', ascending=False)['name'].head(8).tolist()

    # Build MILP matrices
    qb_mask = (pool['pos'] == 'QB').astype(int).values
    rb_mask = (pool['pos'] == 'RB').astype(int).values
    wr_mask = (pool['pos'] == 'WR').astype(int).values
    te_mask = (pool['pos'] == 'TE').astype(int).values
    dst_mask = (pool['pos'] == 'D').astype(int).values
    salaries = pool['salary'].values

    A_base = [
        np.ones(N), salaries, salaries, qb_mask,
        rb_mask, rb_mask, wr_mask, wr_mask,
        te_mask, te_mask, dst_mask, (rb_mask + wr_mask + te_mask)
    ]
    lhs_base = [9, 0, 58000, 1, 2, 0, 3, 0, 1, 0, 1, 7]
    rhs_base = [9, 60000, 60000, 1, 3, 3, 4, 4, 2, 2, 1, 7]

    lineup_scores = []
    lineup_details = []

    for sim in range(num_simulations):
        qb_choice = np.random.choice(starting_qbs)
        qb_row = pool[pool['name'] == qb_choice].iloc[0]
        qb_team = qb_row['team']
        qb_opp = qb_row['opp']

        target_qb_mask = (pool['name'] == qb_choice).astype(int).values
        # Primary pass catcher must be an alpha/starter on depth chart or have salary >= $5500
        is_primary = (
            (pool['team'] == qb_team) & 
            (pool['pos'].isin(['WR', 'TE'])) & 
            ((pool['name'].isin(depth_chart_alphas)) | (pool['salary'] >= 5500) | (pool['fppg'] >= 6.5))
        )
        qb_recv_mask = is_primary.astype(int).values
        opp_bb_mask = ((pool['team'] == qb_opp) & (pool['pos'].isin(['WR', 'RB', 'TE']))).astype(int).values
        opp_dst_mask = ((pool['team'] == qb_opp) & (pool['pos'] == 'D')).astype(int).values

        A_iter = list(A_base)
        lhs_iter = list(lhs_base)
        rhs_iter = list(rhs_base)

        A_iter.append(target_qb_mask); lhs_iter.append(1); rhs_iter.append(1)
        A_iter.append(qb_recv_mask); lhs_iter.append(1); rhs_iter.append(3)
        A_iter.append(opp_bb_mask); lhs_iter.append(1); rhs_iter.append(2)
        A_iter.append(opp_dst_mask); lhs_iter.append(0); rhs_iter.append(0)

        # Simulation noise
        sim_noise = np.random.normal(0, 1.8, N)
        obj = -(pool['proj'].values + sim_noise)

        constraints = LinearConstraint(A_iter, lhs_iter, rhs_iter)
        integrality = np.ones(N)
        bounds = Bounds(0, 1)

        res = milp(c=obj, integrality=integrality, constraints=constraints, bounds=bounds)
        if res.success:
            sel_idx = np.where(res.x > 0.5)[0]
            roster = pool.iloc[sel_idx].copy()

            tot_actual = 0.0
            roster_str = []
            for _, row in roster.iterrows():
                pn, pos, tm, sal = row['name'], row['pos'], row['team'], row['salary']
                if pos == 'D':
                    pt = dst_act.get(pn, dst_act.get(tm, 0.0))
                else:
                    pt = player_act.get(pn, 0.0)
                    if pt == 0.0:
                        for k, v in player_act.items():
                            if pn.lower() in k.lower():
                                pt = v; break
                tot_actual += pt
                roster_str.append(f"{pn} ({pt:.1f})")

            lineup_scores.append(round(tot_actual, 2))
            lineup_details.append({
                'score': round(tot_actual, 2),
                'qb': qb_choice,
                'players': roster_str
            })

    lineup_scores = np.array(lineup_scores) if lineup_scores else np.array([0.0])
    best_l = max(lineup_details, key=lambda x: x['score']) if lineup_details else {'score': 0, 'qb': '', 'players': []}

    return {
        'week': w,
        'lineups': len(lineup_scores),
        'max_score': round(lineup_scores.max(), 2),
        'p95_score': round(np.percentile(lineup_scores, 95), 2),
        'median_score': round(np.median(lineup_scores), 2),
        'mean_score': round(lineup_scores.mean(), 2),
        'cash_rate': round((lineup_scores >= 135.0).mean() * 100, 1),
        'best_lineup': best_l
    }

def main():
    print("=" * 75)
    print("NFL 2026 DFS SYSTEMATIC BACKTEST & CALIBRATION (WEEKS 1 - 4)")
    print("Analyzing Model Progression, Score Trajectory, and Error Drift")
    print("=" * 75)

    results = []
    for cfg in WEEKS_CONFIG:
        print(f"\nProcessing Week {cfg['week']} (Date: {cfg['date']})...")
        res = evaluate_slate(cfg, num_simulations=50)
        if res:
            results.append(res)

    print("\n" + "=" * 75)
    print("HISTORICAL 4-WEEK PERFORMANCE PROGRESSION")
    print("=" * 75)
    print(f"{'Week':<6} | {'Max Score':<11} | {'95th% Score':<12} | {'Median':<8} | {'Cash %':<8} | {'Top Stack / QB':<16}")
    print("-" * 75)

    for r in results:
        w_str = f"Week {r['week']}"
        print(f"{w_str:<6} | {r['max_score']:<11.2f} | {r['p95_score']:<12.2f} | {r['median_score']:<8.2f} | {r['cash_rate']:<7.1f}% | {r['best_lineup']['qb']:<16}")

    print("\n" + "=" * 75)
    print("WEEK-BY-WEEK BEST SIMULATED LINEUPS & KEY CORRELATIONS")
    print("=" * 75)
    for r in results:
        print(f"\n[Week {r['week']}] Top Score: {r['max_score']} FP (QB: {r['best_lineup']['qb']})")
        print("  Roster:", ", ".join(r['best_lineup']['players']))

if __name__ == '__main__':
    main()
