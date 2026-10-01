#!/usr/bin/env python3
"""Synchronize and fix all 2026 roster references across codebase."""

import json
import re
import sqlite3
from pathlib import Path

def run_fix():
    dc_path = Path("data/nfl_depth_charts_2026.json")
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

    print(f"Loaded {len(real_teams)} players from 2026 depth charts.")

    # 1. Update data/fantasy.db
    db_path = Path("data/fantasy.db")
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        updated_count = 0
        for name, tm in real_teams.items():
            cur.execute("UPDATE players SET pro_team = ? WHERE full_name = ? AND pro_team != ?", (tm, name, tm))
            updated_count += cur.rowcount
        conn.commit()
        conn.close()
        print(f"[data/fantasy.db] Synced {updated_count} player teams to 2026 depth charts.")

    # 2. Update scripts/build_nextgen_dataset.py
    nextgen_py = Path("scripts/build_nextgen_dataset.py")
    if nextgen_py.exists():
        text = nextgen_py.read_text(encoding="utf-8")
        # Replace specific known discrepancies in build_nextgen_dataset
        replacements = [
            ('"aaron rodgers": {"team": "NYJ"', '"aaron rodgers": {"team": "PIT"'),
            ('"sam darnold": {"team": "SEA"', '"sam darnold": {"team": "SEA"'),
            ('"david montgomery": {\n            "team": "DET"', '"david montgomery": {\n            "team": "HOU"'),
            ('"dj moore": {\n            "team": "CHI"', '"dj moore": {\n            "team": "BUF"'),
            ('"kirk cousins": {"team": "ATL"', '"kirk cousins": {"team": "LV"'),
            ('"tua tagovailoa": {"team": "MIA"', '"tua tagovailoa": {"team": "ATL"'),
            ('"kyler murray": {"team": "ARI"', '"kyler murray": {"team": "MIN"'),
            ('"daniel jones": {"team": "NYG"', '"daniel jones": {"team": "IND"'),
            ('"geno smith": {"team": "SEA"', '"geno smith": {"team": "NYJ"'),
            ('"matthew golden": {\n            "team": "GB"', '"matthew golden": {\n            "team": "GB"'),
            ('"kenyon sadiq": {\n            "team": "NYJ"', '"kenyon sadiq": {\n            "team": "NYJ"'),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        nextgen_py.write_text(text, encoding="utf-8")
        print("[scripts/build_nextgen_dataset.py] Updated player team entries.")

    # 3. Update src/core/nfl_rosters.py
    rosters_py = Path("src/core/nfl_rosters.py")
    if rosters_py.exists():
        text = rosters_py.read_text(encoding="utf-8")
        # For each player in CANONICAL_REAL_TEAMS that has a discrepancy, replace their line
        lines = text.split("\n")
        new_lines = []
        replaced_count = 0
        for line in lines:
            m = re.match(r'(\s*"([^"]+)":\s*)"([A-Z]{2,3})"(.*)', line)
            if m:
                prefix = m.group(1)
                name = m.group(2)
                curr_tm = m.group(3)
                suffix = m.group(4)
                if name in real_teams and real_teams[name] != curr_tm:
                    new_tm = real_teams[name]
                    # check aliases
                    if not ((curr_tm, new_tm) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]):
                        line = f'{prefix}"{new_tm}"{suffix}'
                        replaced_count += 1
            new_lines.append(line)
        rosters_py.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"[src/core/nfl_rosters.py] Updated {replaced_count} entries to 2026 real teams.")

    # 4. Update scripts/normalize_nfl_rosters.py
    norm_py = Path("scripts/normalize_nfl_rosters.py")
    if norm_py.exists():
        text = norm_py.read_text(encoding="utf-8")
        lines = text.split("\n")
        new_lines = []
        replaced_count = 0
        for line in lines:
            m = re.match(r'(\s*"([^"]+)":\s*)"([A-Z]{2,3})"(.*)', line)
            if m:
                prefix = m.group(1)
                name = m.group(2)
                curr_tm = m.group(3)
                suffix = m.group(4)
                if name in real_teams and real_teams[name] != curr_tm:
                    new_tm = real_teams[name]
                    if not ((curr_tm, new_tm) in [("JAC", "JAX"), ("JAX", "JAC"), ("WAS", "WSH"), ("WSH", "WAS")]):
                        line = f'{prefix}"{new_tm}"{suffix}'
                        replaced_count += 1
            new_lines.append(line)
        norm_py.write_text("\n".join(new_lines), encoding="utf-8")
        print(f"[scripts/normalize_nfl_rosters.py] Updated {replaced_count} entries to 2026 real teams.")

if __name__ == "__main__":
    run_fix()
