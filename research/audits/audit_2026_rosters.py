#!/usr/bin/env python3
"""Audit all roster and player-team mappings against 2026 authoritative depth charts."""

import json
from pathlib import Path
import re

def audit_rosters():
    dc_path = Path("data/nfl_depth_charts_2026.json")
    if not dc_path.exists():
        print("Error: data/nfl_depth_charts_2026.json not found")
        return

    with open(dc_path, "r", encoding="utf-8") as f:
        dc = json.load(f).get("teams", {})

    real_teams = {}
    for tm, tdata in dc.items():
        for unit, pdict in tdata.items():
            if isinstance(pdict, dict):
                for pos, plist in pdict.items():
                    if isinstance(plist, list):
                        for p in plist:
                            if isinstance(p, dict) and "name" in p:
                                real_teams[p["name"]] = tm

    print(f"Loaded {len(real_teams)} players from 2026 authoritative depth charts.")

    # 1. Audit src/core/nfl_rosters.py
    rosters_py = Path("src/core/nfl_rosters.py")
    if rosters_py.exists():
        text = rosters_py.read_text(encoding="utf-8")
        matches = re.findall(r'"([^"]+)":\s*"([A-Z]{2,3})"', text)
        disc = []
        for name, team in matches:
            if name in real_teams:
                r_team = real_teams[name]
                if r_team != team:
                    # check aliases
                    if (team, r_team) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]:
                        continue
                    disc.append((name, team, r_team))
        print(f"\n[src/core/nfl_rosters.py] Found {len(disc)} discrepancies:")
        for name, old_t, new_t in sorted(disc):
            print(f"  - {name:<26}: was {old_t:<4} -> 2026 real is {new_t}")

    # 2. Audit scripts/normalize_nfl_rosters.py
    norm_py = Path("scripts/normalize_nfl_rosters.py")
    if norm_py.exists():
        text = norm_py.read_text(encoding="utf-8")
        matches = re.findall(r'"([^"]+)":\s*"([A-Z]{2,3})"', text)
        disc = []
        for name, team in matches:
            if name in real_teams:
                r_team = real_teams[name]
                if r_team != team:
                    if (team, r_team) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]:
                        continue
                    disc.append((name, team, r_team))
        print(f"\n[scripts/normalize_nfl_rosters.py] Found {len(disc)} discrepancies:")
        for name, old_t, new_t in sorted(disc):
            print(f"  - {name:<26}: was {old_t:<4} -> 2026 real is {new_t}")

    # 3. Audit scripts/build_nextgen_dataset.py
    nextgen_py = Path("scripts/build_nextgen_dataset.py")
    if nextgen_py.exists():
        text = nextgen_py.read_text(encoding="utf-8")
        # find patterns like "name": {"team": "XYZ"
        matches = re.findall(r'"([^"]+)":\s*\{[^}]*"team":\s*"([A-Z]{2,3})"', text)
        disc = []
        for name, team in matches:
            # normalize name
            norm_lookup = {k.lower(): (k, v) for k, v in real_teams.items()}
            if name.lower() in norm_lookup:
                orig_name, r_team = norm_lookup[name.lower()]
                if r_team != team:
                    if (team, r_team) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]:
                        continue
                    disc.append((orig_name, team, r_team))
        print(f"\n[scripts/build_nextgen_dataset.py] Found {len(disc)} discrepancies:")
        for name, old_t, new_t in sorted(disc):
            print(f"  - {name:<26}: was {old_t:<4} -> 2026 real is {new_t}")

    # 4. Audit sqlite fantasy.db
    import sqlite3
    db_path = Path("data/fantasy.db")
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT full_name, pro_team FROM players").fetchall()
        disc = []
        for name, team in rows:
            if name in real_teams:
                r_team = real_teams[name]
                if team and r_team != team:
                    if (team, r_team) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]:
                        continue
                    disc.append((name, team, r_team))
        print(f"\n[data/fantasy.db] Found {len(disc)} discrepancies:")
        for name, old_t, new_t in sorted(disc)[:25]:
            print(f"  - {name:<26}: was {old_t:<4} -> 2026 real is {new_t}")
        if len(disc) > 25:
            print(f"  ... and {len(disc) - 25} more")

if __name__ == "__main__":
    audit_rosters()
