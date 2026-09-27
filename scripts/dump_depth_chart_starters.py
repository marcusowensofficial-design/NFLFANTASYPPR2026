import json

with open("data/nfl_depth_charts_2026.json", "r", encoding="utf-8") as f:
    dc = json.load(f)

teams = dc.get("teams", {})
print(f"Total teams in depth chart: {len(teams)}")

for tm in ['ARI', 'ATL', 'BAL', 'BUF', 'CAR']:
    defense = teams[tm].get("defense", {})
    lcb = [f"{p['name']} (r{p.get('rank')})" for p in defense.get("lcb", [])[:2]]
    rcb = [f"{p['name']} (r{p.get('rank')})" for p in defense.get("rcb", [])[:2]]
    nb = [f"{p['name']} (r{p.get('rank')})" for p in defense.get("nb", [])[:2]]
    ss = [f"{p['name']} (r{p.get('rank')})" for p in defense.get("ss", [])[:1]]
    fs = [f"{p['name']} (r{p.get('rank')})" for p in defense.get("fs", [])[:1]]
    dl = []
    for dpos in ["lde", "rde", "ldt", "rdt", "nt"]:
        for p in defense.get(dpos, [])[:1]:
            dl.append(f"{p['name']} ({dpos})")
    print(f"[{tm}]")
    print(f"  LCB: {lcb}")
    print(f"  RCB: {rcb}")
    print(f"  NB : {nb}")
    print(f"  S  : SS={ss}, FS={fs}")
    print(f"  DL : {dl[:3]}")
