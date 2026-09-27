import sys
sys.path.insert(0, ".")
import json
from src.services.matchup.wrcb_matrix import NFL_CB_DEPTH_CHARTS

with open("data/nfl_depth_charts_2026.json", "r", encoding="utf-8") as f:
    dc = json.load(f)["teams"]

print(f"Total teams in wrcb_matrix: {len(NFL_CB_DEPTH_CHARTS)}")

discrepancies = []
for tm, cb_room in sorted(NFL_CB_DEPTH_CHARTS.items()):
    team_dc = dc.get(tm, {}).get("defense", {})
    dc_players = set()
    for pos in ["lcb", "rcb", "nb", "cb", "fs", "ss", "db"]:
        for p in team_dc.get(pos, []):
            dc_players.add(p.get("name"))

    for role, profile in cb_room.items():
        if profile.name not in dc_players:
            # where is player actually?
            actual_location = []
            for other_tm, otdata in dc.items():
                for u, poss in otdata.items():
                    if isinstance(poss, dict):
                        for ppos, plist in poss.items():
                            if isinstance(plist, list):
                                for plyr in plist:
                                    if isinstance(plyr, dict) and plyr.get("name", "").lower() == profile.name.lower():
                                        actual_location.append((other_tm, f"{u}.{ppos}"))
            discrepancies.append((tm, role, profile.name, actual_location))

print(f"Total discrepancies in wrcb_matrix: {len(discrepancies)}")
for tm, role, name, loc in discrepancies:
    print(f"[{tm}] {role}: {name} -> {loc}")
