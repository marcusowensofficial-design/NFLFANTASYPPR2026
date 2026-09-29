import sys
import json
import re
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.solve_main_slate_matrix import load_and_enrich_slate
from scripts.solve_multi_matrix_gpp import get_verified_starter_pool, solve_3game_matrix

df, vegas = load_and_enrich_slate('data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv')
pool = get_verified_starter_pool(df)

configs = [
    {
        'title': 'PORTFOLIO LINEUP 1: SEA-WAS Primary Track Meet (Darnold/JSN Stack)',
        'primary': ('SEA', 'WAS'),
        'mini1': ('NYJ', 'DET'),
        'mini2': ('BAL', 'DAL'),
        'dst': 'WAS',
        'force_qb': 'Sam Darnold'
    },
    {
        'title': 'PORTFOLIO LINEUP 2: SF-ARI Primary Shootout (Purdy/Kittle Stack)',
        'primary': ('SF', 'ARI'),
        'mini1': ('NYJ', 'DET'),
        'mini2': ('BAL', 'DAL'),
        'dst': 'CLE',
        'force_qb': 'Brock Purdy'
    },
    {
        'title': 'PORTFOLIO LINEUP 3: NYJ-DET Primary Ford Field Dome (Goff/Wilson Stack)',
        'primary': ('NYJ', 'DET'),
        'mini1': ('SF', 'ARI'),
        'mini2': ('BAL', 'DAL'),
        'dst': 'TEN',
        'force_qb': 'Jared Goff'
    },
    {
        'title': 'PORTFOLIO LINEUP 4: BAL-DAL Primary JerryWorld Shootout (Lamar/Lamb Stack)',
        'primary': ('BAL', 'DAL'),
        'mini1': ('SEA', 'WAS'),
        'mini2': ('NYJ', 'DET'),
        'dst': 'CIN',
        'force_qb': 'Lamar Jackson'
    },
    {
        'title': 'PORTFOLIO LINEUP 5: BUF-LAC Primary (Josh Allen Anchor + Ladd McConkey)',
        'primary': ('LAC', 'BUF'),
        'mini1': ('SEA', 'WAS'),
        'mini2': ('SF', 'ARI'),
        'dst': 'WAS',
        'force_qb': 'Josh Allen'
    },
    {
        'title': 'PORTFOLIO LINEUP 6: LV-NO Primary Track Meet (Tyler Shough / Brock Bowers)',
        'primary': ('LV', 'NO'),
        'mini1': ('NYJ', 'DET'),
        'mini2': ('SEA', 'WAS'),
        'dst': 'CLE',
        'force_qb': 'Tyler Shough'
    }
]

with open('data/week3_sunday_actuals.json', 'r') as f:
    act_data = json.load(f)
p_act = act_data['players']

def clean_name(n):
    return re.sub(r'[^\w\s]', '', str(n)).lower().strip()

m = {clean_name(k): v.get('half_ppr', 0.0) for k, v in p_act.items()}
m['kenneth walker iii'] = m.get('kenneth walker', 0.0)
m['james cook iii'] = m.get('james cook', 0.0)
dst_acts = {'WAS': 15.0, 'CLE': 2.0, 'TEN': 4.0, 'CIN': 2.0, 'NE': 9.0}

print("\n" + "="*80)
print("TESTING DIVERSE 3-GAME MATRIX PORTFOLIO (WITH SYSTEMIC UPGRADES)")
print("="*80)

for cfg in configs:
    roster = solve_3game_matrix(
        pool,
        primary_game=cfg['primary'],
        mini_1=cfg['mini1'],
        mini_2=cfg['mini2'],
        dst_team=cfg['dst'],
        force_qb=cfg.get('force_qb')
    )
    if roster is not None:
        act_tot = 0.0
        details = []
        for _, r in roster.iterrows():
            pos = r['pos']
            tm = r['team']
            pname = r['name']
            if pos == 'D':
                sc = dst_acts.get(tm, 2.0)
            else:
                sc = m.get(clean_name(pname), 0.0)
            act_tot += sc
            details.append(f"{pname} ({pos}, {sc:.1f})")
        print(f"\n{cfg['title']}")
        print(f"Projected: {roster['gpp_proj'].sum():.2f} FP | ACTUAL SCORE: {act_tot:.2f} FP | Salary: ${roster['salary'].sum():,}")
        print("  " + ", ".join(details))
    else:
        print(f"\n{cfg['title']}: No solution found.")
