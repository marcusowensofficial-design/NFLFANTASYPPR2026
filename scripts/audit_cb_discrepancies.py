import json

with open("data/pff_scouting_2026.json", "r", encoding="utf-8") as f:
    pff = json.load(f)

with open("data/nfl_depth_charts_2026.json", "r", encoding="utf-8") as f:
    dc = json.load(f)

pff_teams = pff.get("teams", {})
dc_teams = dc.get("teams", {})

print("=== PFF SCOUTING CBs VS DEPTH CHARTS ===")
discrepancies = []
for tm, tdata in sorted(pff_teams.items()):
    dc_tm = dc_teams.get(tm, {})
    dc_def = dc_tm.get("defense", {})

    dc_dbs = set()
    for pos in ["lcb", "rcb", "nb", "cb", "fs", "ss", "s", "db"]:
        if pos in dc_def:
            for p in dc_def[pos]:
                dc_dbs.add(p.get("name"))

    pff_cbs = tdata.get("cornerbacks", {})
    for role, cb_info in pff_cbs.items():
        if isinstance(cb_info, dict) and "name" in cb_info:
            cb_name = cb_info["name"]
            if cb_name not in dc_dbs:
                # Find where player actually is
                found_teams = []
                for other_tm, other_data in dc_teams.items():
                    for u, poss in other_data.items():
                        if isinstance(poss, dict):
                            for ppos, plist in poss.items():
                                if isinstance(plist, list):
                                    for plyr in plist:
                                        if isinstance(plyr, dict) and plyr.get("name", "").lower() == cb_name.lower():
                                            found_teams.append((other_tm, f"{u}.{ppos}", plyr.get("rank")))
                discrepancies.append((tm, role, cb_name, found_teams))

print("\n=== SEARCHING FOR MISSING STARS ACROSS ALL TEAMS ===")
queries = ['surtain', 'terrell', 'diggs', 'alexander', 'lattimore', 'murphy', 'slay', 'ramsey', 'minkah', 'chinn', 'reid']
for q in queries:
    found = []
    for tm, tdata in sorted(dc_teams.items()):
        for u, poss in tdata.items():
            if isinstance(poss, dict):
                for ppos, plist in poss.items():
                    if isinstance(plist, list):
                        for plyr in plist:
                            if isinstance(plyr, dict) and q in plyr.get("name", "").lower():
                                found.append((tm, f"{u}.{ppos}", plyr.get("name"), plyr.get("rank")))
    print(f"Query '{q}': {found}")

