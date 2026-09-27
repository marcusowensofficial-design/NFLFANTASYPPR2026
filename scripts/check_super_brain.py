import json

with open("data/encyclopedia/nfl_super_brain_master.json", "r", encoding="utf-8") as f:
    sb = json.load(f)

print("Keys:", list(sb.keys()))
players = sb.get("players", {})
print("Total players:", len(players))

for name in ["L'Jarius Sneed", "Trent McDuffie", "Sauce Gardner", "Charvarius Ward"]:
    if name in players:
        p = players[name]
        print(f"{name}: team={p.get('team')}, pos={p.get('position')}")
    else:
        print(f"{name}: NOT IN SUPER BRAIN")
