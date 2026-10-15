import json

with open("data/nfl_depth_charts_2026.json", "r", encoding="utf-8") as f:
    dc = json.load(f)["teams"]

player_map = {}
for tm, tdata in dc.items():
    for unit, pdict in tdata.items():
        if isinstance(pdict, dict):
            for pos, plist in pdict.items():
                if isinstance(plist, list):
                    for p in plist:
                        if isinstance(p, dict) and "name" in p:
                            player_map[p["name"]] = tm

print("Total unique players in official depth charts:", len(player_map))
checks = [
    "Isaiah Likely", "Kenneth Walker III", "David Montgomery", "Isiah Pacheco",
    "Stefon Diggs", "Adonai Mitchell", "Mike Evans", "Aaron Rodgers",
    "L'Jarius Sneed", "Trent McDuffie", "Sauce Gardner", "Charvarius Ward"
]
for check in checks:
    print(f"  {check} -> {player_map.get(check)}")
