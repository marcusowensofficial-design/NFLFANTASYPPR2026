import json

with open('data/player_props_live.json', 'r') as f:
    props = json.load(f)

print("=== BIJAN ROBINSON PROPS ===")
print(json.dumps(props.get('players', {}).get('Bijan Robinson', {}), indent=2))

print("\n=== PFF SCOUTING 2026 ===")
with open('data/pff_scouting_2026.json', 'r') as f:
    pff = json.load(f)

for t in ['ATL', 'NO']:
    print(f"*** PFF {t} ***")
    print(json.dumps(pff.get('teams', {}).get(t, {}), indent=2))

print("\n=== NEXTGEN MICRO METRICS 2026 ===")
with open('data/nextgen_micro_metrics_2026.json', 'r') as f:
    ng = json.load(f)

print("NextGen keys:", list(ng.keys()) if isinstance(ng, dict) else len(ng))
if isinstance(ng, dict):
    for k in ng.keys():
        val = ng[k]
        print(f"Key {k}: type={type(val)}")
        if isinstance(val, dict):
            # check if ATL or NO in keys
            relevant = {rk: rv for rk, rv in val.items() if any(x in str(rk) or x in str(rv) for x in ['ATL', 'NO', 'Bijan', 'Olave', 'London', 'Kamara', 'Shough', 'Penix'])}
            print(f"  Relevant in {k}:", list(relevant.keys())[:10])

