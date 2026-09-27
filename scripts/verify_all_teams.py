import json

with open("data/pff_scouting_2026.json", "r", encoding="utf-8") as f:
    pff = json.load(f)["teams"]

print("=== VERIFYING KEY TRADED PLAYERS IN PFF SCOUTING ===")
teams_to_check = ['KC', 'TEN', 'LAR', 'IND', 'PIT', 'PHI', 'NYJ', 'BUF', 'WSH', 'LV', 'DET', 'NO', 'DEN', 'HOU', 'CHI', 'CLE']

for tm in teams_to_check:
    cbs = pff[tm]["cornerbacks"]
    o1 = cbs["outside1"]
    o2 = cbs["outside2"]
    sl = cbs["slot"]
    sf = cbs["safety"]
    dl = pff[tm]["defensive_line_front"]["key_disruptors"]
    ol = pff[tm]["offensive_line"]["key_tackles"]
    print(f"[{tm}]")
    print(f"  CB1: {o1['name']} ({o1['role']}, grade={o1['grade']}, shadow={o1['is_shadow']})")
    print(f"  CB2: {o2['name']} ({o2['role']}, grade={o2['grade']}, shadow={o2['is_shadow']})")
    print(f"  SLOT: {sl['name']} (grade={sl['grade']})")
    print(f"  SAFETY: {sf['name']} (role={sf.get('role')}, grade={sf['grade']})")
    print(f"  DL Disruptors: {dl}")
    print(f"  OL Tackles: {ol}")
