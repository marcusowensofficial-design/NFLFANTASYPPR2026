import json
import re
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds

# Load slate data
csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
import sys
sys.path.insert(0, ".")
from scripts.solve_main_slate_matrix import load_and_enrich_slate

df_slate, vegas = load_and_enrich_slate(csv_path)

# Load actuals
with open("data/week3_sunday_actuals.json", "r") as f:
    act_data = json.load(f)

players_act = act_data["players"]
game_scores = act_data["game_scores"]

# Map actuals to df_slate
def clean_name(n):
    return re.sub(r"[^\w\s]", "", str(n)).lower().strip()

name_map = {}
for p_name, p_stat in players_act.items():
    name_map[clean_name(p_name)] = p_stat

# Standard aliases
aliases = {
    clean_name("Kenneth Walker III"): clean_name("Kenneth Walker"),
    clean_name("James Cook III"): clean_name("James Cook"),
    clean_name("Travis Etienne Jr."): clean_name("Travis Etienne"),
    clean_name("Brian Robinson Jr."): clean_name("Brian Robinson"),
    clean_name("Marvin Harrison Jr."): clean_name("Marvin Harrison"),
    clean_name("Michael Pittman Jr."): clean_name("Michael Pittman"),
    clean_name("Tyrone Tracy Jr."): clean_name("Tyrone Tracy"),
    clean_name("Ray Davis"): clean_name("Ray Davis"),
}

actual_points_half = []
actual_points_full = []
rush_yds = []
rush_tds = []
rec_yds = []
rec_tds = []
receptions = []
targets = []
pass_yds = []
pass_tds = []

for idx, row in df_slate.iterrows():
    c_name = row['norm_name']
    pos = row['pos']
    
    stat = None
    if c_name in name_map:
        stat = name_map[c_name]
    elif aliases.get(c_name) in name_map:
        stat = name_map[aliases[c_name]]
    else:
        # Try finding substring
        for k in name_map:
            if c_name in k or k in c_name:
                stat = name_map[k]
                break
                
    if stat and pos != 'D':
        actual_points_half.append(stat.get('half_ppr', 0.0))
        actual_points_full.append(stat.get('full_ppr', 0.0))
        rush_yds.append(stat.get('rush_yds', 0))
        rush_tds.append(stat.get('rush_tds', 0))
        rec_yds.append(stat.get('rec_yds', 0))
        rec_tds.append(stat.get('rec_tds', 0))
        receptions.append(stat.get('receptions', 0))
        targets.append(stat.get('targets', 0))
        pass_yds.append(stat.get('pass_yds', 0))
        pass_tds.append(stat.get('pass_tds', 0))
    else:
        actual_points_half.append(0.0)
        actual_points_full.append(0.0)
        rush_yds.append(0)
        rush_tds.append(0)
        rec_yds.append(0)
        rec_tds.append(0)
        receptions.append(0)
        targets.append(0)
        pass_yds.append(0)
        pass_tds.append(0)

df_slate['act_half'] = actual_points_half
df_slate['act_full'] = actual_points_full
df_slate['rush_yds'] = rush_yds
df_slate['rush_tds'] = rush_tds
df_slate['rec_yds'] = rec_yds
df_slate['rec_tds'] = rec_tds
df_slate['receptions'] = receptions
df_slate['targets'] = targets
df_slate['pass_yds'] = pass_yds
df_slate['pass_tds'] = pass_tds
df_slate['diff_half'] = df_slate['act_half'] - df_slate['gpp_proj']

# Filter only offensive players who played or had salary > 5000
off = df_slate[df_slate['pos'] != 'D'].copy()

print("="*80)
print("WEEK 3 SUNDAY FORENSIC AUDIT: PROJECTIONS VS REALITY")
print("="*80)

print("\n--- TOP 15 FANTASY SCORERS TODAY (HALF-PPR) ---")
top_scorers = off.sort_values(by='act_half', ascending=False).head(15)
cols = ['name', 'pos', 'team', 'opp', 'salary', 'gpp_proj', 'act_half', 'diff_half']
print(top_scorers[cols].to_string(index=False))

print("\n--- TOP 10 BIGGEST PROJECTION BEATERS (SMASH HITS / CEILINGS) ---")
top_smashes = off[off['salary'] >= 4500].sort_values(by='diff_half', ascending=False).head(10)
print(top_smashes[cols].to_string(index=False))

print("\n--- TOP 10 BIGGEST PROJECTION BUSTS (UNDERPERFORMERS WITH SALARY >= $6,000) ---")
top_busts = off[off['salary'] >= 6000].sort_values(by='diff_half', ascending=True).head(10)
print(top_busts[cols].to_string(index=False))

print("\n--- TOP VALUES BY VALUE MULTIPLIER (FP / $1,000) ---")
off['val_mult'] = off['act_half'] / (off['salary'] / 1000.0)
top_values = off[off['salary'] >= 4000].sort_values(by='val_mult', ascending=False).head(10)
print(top_values[['name', 'pos', 'team', 'salary', 'act_half', 'val_mult']].to_string(index=False))

# Check McClure exposure list specifically
mcclure_list = [
    "Jahmyr Gibbs", "Kenneth Walker III", "Jaylen Warren", "Garrett Wilson",
    "Chuba Hubbard", "Mark Andrews", "Josh Allen", "Dalton Kincaid",
    "Jalen Coker", "Parker Washington", "Travis Kelce", "Ashton Jeanty",
    "Derrick Henry", "Ladd McConkey", "Adonai Mitchell", "James Cook III",
    "Lamar Jackson", "Brock Purdy", "Dak Prescott", "Patrick Mahomes", "Jared Goff"
]

print("\n--- AUDIT OF CORE MCCLURE / PRO EXPOSURES TODAY ---")
mc_rows = off[off['name'].isin(mcclure_list)].copy()
print(mc_rows[cols].sort_values(by='act_half', ascending=False).to_string(index=False))

