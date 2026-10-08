import json

print("=== CHECKING nfl_2026_weeks_1_4.json ===")
with open('data/nfl_2026_weeks_1_4.json', 'r') as f:
    w14 = json.load(f)

print("w14 type:", type(w14))
if isinstance(w14, dict):
    print("w14 keys:", list(w14.keys())[:10])
    for k in w14.keys():
        if any(t in str(k) or t in str(w14[k]) for t in ['ATL', 'NO', 'Falcons', 'Saints', 'Bijan', 'Olave', 'London', 'Kamara', 'Shough', 'Penix']):
            print(f"Key {k}:", str(w14[k])[:200])
elif isinstance(w14, list):
    print("w14 len:", len(w14))
    for item in w14[:5]:
        print(item)

print("\n=== CHECKING nfl_intelligence_master_2026.json ===")
with open('data/nfl_intelligence_master_2026.json', 'r') as f:
    intel = json.load(f)
print("intel keys:", list(intel.keys()) if isinstance(intel, dict) else len(intel))
if isinstance(intel, dict):
    for k in intel.keys():
        val = intel[k]
        print(f"Intel section {k}:")
        if isinstance(val, dict):
            matched = {subk: subv for subk, subv in val.items() if any(x in str(subk).lower() or x in str(subv).lower() for x in ['atl', 'no', 'bijan', 'olave', 'london', 'kamara', 'shough', 'penix'])}
            print(f"  Matched keys ({len(matched)}):", list(matched.keys()))
            for mk in list(matched.keys())[:3]:
                print(f"    {mk}: {str(matched[mk])[:200]}")

print("\n=== CHECKING actuals_2026_10_04.json ===")
with open('data/actuals_2026_10_04.json', 'r') as f:
    act = json.load(f)
print("act keys:", list(act.keys()) if isinstance(act, dict) else len(act))
if isinstance(act, list):
    atl_no_players = [p for p in act if p.get('team') in ['ATL', 'NO'] or p.get('opponent') in ['ATL', 'NO']]
    print("ATL/NO actuals count:", len(atl_no_players))
    for p in atl_no_players[:10]:
        print(p.get('name') or p.get('player'), p.get('team'), p.get('fantasy_points'), p.get('stats'))
elif isinstance(act, dict):
    for k, v in act.items():
        if any(x in str(k).lower() or x in str(v).lower() for x in ['atl', 'no', 'bijan', 'olave', 'london', 'kamara', 'shough', 'penix']):
            print(k, str(v)[:200])
