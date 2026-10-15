import json

print("=" * 60)
print("BUFFALO BILLS INJURIES")
print("=" * 60)
inj_data = json.load(open('data/injuries_live_2026.json'))['injuries']
for x in inj_data:
    if x.get('team') in ['Buffalo Bills', 'BUF']:
        print(f"[BUF] {x.get('name')} ({x.get('position')}): Status={x.get('status')}, is_playable={x.get('is_playable')}, headline={x.get('headline')}, notes={x.get('notes')[:120] if x.get('notes') else ''}")

print("\n" + "=" * 60)
print("DEPTH CHARTS (BUF & DET)")
print("=" * 60)
dc = json.load(open('data/nfl_depth_charts_2026.json'))['teams']
for t in ['BUF', 'DET']:
    if t in dc:
        print(f"\n--- Depth Chart {t} ---")
        team_dc = dc[t]
        for pos, players in team_dc.items():
            if pos in ['QB', 'RB', 'WR', 'TE', 'PK', 'K']:
                print(f"  {pos}: {players}")

print("\n" + "=" * 60)
print("PFF SCOUTING TRENCH & DEFENSE (BUF & DET)")
print("=" * 60)
pff = json.load(open('data/pff_scouting_2026.json'))['teams']
for t in ['BUF', 'DET']:
    if t in pff:
        print(f"\n--- {t} PFF Scouting ---")
        print(json.dumps(pff[t], indent=2))

print("\n" + "=" * 60)
print("WEEK 1 RECEIVER MICRO METRICS (BUF & DET)")
print("=" * 60)
rec = json.load(open('data/week_1_receiver_micro_metrics_2026.json'))['players']
for r in rec:
    if r.get('team') in ['BUF', 'DET']:
        print(f"[{r.get('team')}] {r.get('name')} ({r.get('position')}): Sep={r.get('separation_score')}, TPRR={r.get('realized_tprr')}, FirstRead={r.get('first_read_share')}, RoutePart={r.get('route_participation')}, Align={r.get('alignment_tendency')}, RegIdx={r.get('regression_index')}, Targets={r.get('targets')}, Rec={r.get('receptions')}, Yds={r.get('receiving_yards')}, TDs={r.get('touchdowns')}")

print("\n" + "=" * 60)
print("WEEK 1 RUNNING BACK MICRO METRICS (BUF & DET)")
print("=" * 60)
rbs = json.load(open('data/week_1_running_back_micro_metrics_2026.json'))['players']
for rb in rbs:
    if rb.get('team') in ['BUF', 'DET']:
        print(f"[{rb.get('team')}] {rb.get('name')}: Snap%={rb.get('snap_share')}, Carries={rb.get('carries')}, Targets={rb.get('targets')}, HVTs={rb.get('high_value_touches')}, YCO/A={rb.get('yco_per_att')}, BoxScoreFP={rb.get('fantasy_points')}, Yds={rb.get('rushing_yards')}, TDs={rb.get('rushing_touchdowns')}")
