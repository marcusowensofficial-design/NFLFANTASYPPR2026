import json

with open("data/injuries_live_2026.json", "r", encoding="utf-8") as f:
    inj = json.load(f)

queries = ['diggs', 'alexander', 'lattimore', 'slay', 'bunting', 'stevenson', 'hilton', 'ward', 'darby', 'white', 'sneed']
print("=== INJURIES / INACTIVES CHECK ===")
for item in inj.get("injuries", []):
    name = item.get("name", "")
    for q in queries:
        if q in name.lower():
            team = item.get("team")
            status = item.get("status")
            pos = item.get("position")
            print(f"Injured/Status: {name} ({pos}), Team: {team}, Status: {status}")
