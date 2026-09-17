"""Solve the mathematically optimal FanDuel Showdown lineup strictly using Vegas Player Props."""

import pandas as pd
import numpy as np
from itertools import combinations
from collections import Counter

# Exact Vegas Implied Fantasy Points from Sportsbook Props (FD Half-PPR scoring):
vegas_props = {
    "Josh Allen": {"team": "BUF", "pos": "QB", "salary": 13200, "fpts": 21.09},
    "Jahmyr Gibbs": {"team": "DET", "pos": "RB", "salary": 12400, "fpts": 20.10},
    "Jared Goff": {"team": "DET", "pos": "QB", "salary": 10600, "fpts": 17.63},
    "Amon-Ra St. Brown": {"team": "DET", "pos": "WR", "salary": 11600, "fpts": 15.22},
    "James Cook III": {"team": "BUF", "pos": "RB", "salary": 10200, "fpts": 13.65},
    "Tyler Bass": {"team": "BUF", "pos": "K", "salary": 6800, "fpts": 10.20},
    "Jameson Williams": {"team": "DET", "pos": "WR", "salary": 9200, "fpts": 9.66},
    "Sam LaPorta": {"team": "DET", "pos": "TE", "salary": 7400, "fpts": 8.74},
    "Jake Bates": {"team": "DET", "pos": "K", "salary": 6600, "fpts": 8.70},
    "DJ Moore": {"team": "BUF", "pos": "WR", "salary": 8600, "fpts": 8.37},
    "Dalton Kincaid": {"team": "BUF", "pos": "TE", "salary": 7600, "fpts": 7.23},
    "Khalil Shakir": {"team": "BUF", "pos": "WR", "salary": 8200, "fpts": 6.72},
    "Buffalo Bills": {"team": "BUF", "pos": "D", "salary": 6400, "fpts": 4.50},
    "Detroit Lions": {"team": "DET", "pos": "D", "salary": 6200, "fpts": 4.20},
    "Dawson Knox": {"team": "BUF", "pos": "TE", "salary": 4200, "fpts": 3.45},
    "Keon Coleman": {"team": "BUF", "pos": "WR", "salary": 5600, "fpts": 2.60},
    "Joshua Palmer": {"team": "BUF", "pos": "WR", "salary": 3200, "fpts": 2.35},
    "Sione Vaki": {"team": "DET", "pos": "RB", "salary": 3600, "fpts": 1.20},
    "Ray Davis": {"team": "BUF", "pos": "RB", "salary": 4600, "fpts": 1.50},
}

players = list(vegas_props.keys())
n = len(players)

buf_pass_catchers = set(["DJ Moore", "Dalton Kincaid", "Khalil Shakir", "Keon Coleman", "Dawson Knox"])
det_pass_catchers = set(["Amon-Ra St. Brown", "Sam LaPorta", "Jameson Williams"])

valid_rosters = []

for mvp_idx, mvp in enumerate(players):
    mvp_sal = vegas_props[mvp]["salary"] * 1.5
    mvp_fpts = vegas_props[mvp]["fpts"] * 1.5

    other_players = [p for p in players if p != mvp]
    for flex in combinations(other_players, 5):
        tot_sal = mvp_sal + sum(vegas_props[p]["salary"] for p in flex)
        # Cap check: $58,500 <= tot_sal <= $59,800 (Leaves $200-$1500 unspent buffer)
        if tot_sal > 59800 or tot_sal < 58000:
            continue

        roster = [mvp] + list(flex)
        all_teams = [vegas_props[p]["team"] for p in roster]

        # Rule 1: Both teams represented
        tc = Counter(all_teams)
        if tc["BUF"] == 0 or tc["DET"] == 0:
            continue

        # Rule 2: QB Stacking (No naked QB)
        has_buf_qb = "Josh Allen" in roster
        has_det_qb = "Jared Goff" in roster

        buf_pc = sum(1 for p in roster if p in buf_pass_catchers)
        det_pc = sum(1 for p in roster if p in det_pass_catchers)

        if has_buf_qb and buf_pc == 0:
            continue
        if has_det_qb and det_pc == 0:
            continue

        # Rule 3: Anti-cannibalization (max 2 WR without QB)
        if not has_buf_qb and buf_pc >= 3:
            continue
        if not has_det_qb and det_pc >= 3:
            continue

        # Rule 4: D/ST correlation
        if "Buffalo Bills" in roster and "Jahmyr Gibbs" in roster:
            continue
        if "Detroit Lions" in roster and "James Cook III" in roster:
            continue

        # Rule 5: Single-entry discipline - no sub-$3500 punts
        if any(vegas_props[p]["salary"] < 3500 for p in roster):
            continue

        tot_fpts = mvp_fpts + sum(vegas_props[p]["fpts"] for p in flex)

        valid_rosters.append({
            "mvp": mvp,
            "flex": list(flex),
            "salary": tot_sal,
            "buffer": 60000 - tot_sal,
            "teams": dict(tc),
            "vegas_fpts": tot_fpts,
        })

ranked = sorted(valid_rosters, key=lambda x: x["vegas_fpts"], reverse=True)

print("=" * 80)
print(f"TOP 5 FANDUEL SHOWDOWN LINEUPS STRICTLY SOLVED FROM VEGAS PLAYER PROPS")
print("=" * 80)
for idx, r in enumerate(ranked[:5], 1):
    print(f"Rank {idx}: [MVP] {r['mvp']} ({vegas_props[r['mvp']]['team']}) | Sal: ${r['salary']:,} (Buf: ${r['buffer']:,}) | Vegas Implied: {r['vegas_fpts']:.2f} pts | Teams: {r['teams']}")
    print(f"         FLEX: {', '.join(r['flex'])}")
    print("-" * 80)

print("\n" + "=" * 80)
print("BEST LINEUP FOR EACH MAJOR MVP CANDIDATE (VEGAS PROPS ONLY)")
print("=" * 80)
for target_mvp in ['Jahmyr Gibbs', 'Josh Allen', 'Dalton Kincaid', 'Amon-Ra St. Brown', 'Jared Goff']:
    lus = [r for r in ranked if r['mvp'] == target_mvp]
    if lus:
        top = lus[0]
        print(f"*** {target_mvp.upper()} MVP *** | Sal: ${top['salary']:,} (Buf: ${top['buffer']:,}) | Vegas: {top['vegas_fpts']:.2f} pts")
        print(f"FLEX: {', '.join(top['flex'])}")
        print(f"Teams: {top['teams']}")
        print("-" * 80)

