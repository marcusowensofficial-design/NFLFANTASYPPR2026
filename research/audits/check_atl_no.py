import json

with open('data/injuries_live_2026.json', 'r') as f:
    inj = json.load(f)

print("=== INJURIES (ATL & NO) ===")
for item in inj.get('injuries', []):
    if item.get('team') in ['ATL', 'NO']:
        print(f"[{item.get('team')}] {item.get('player')} ({item.get('position')}): Status={item.get('status')} | Injury={item.get('injury')} | Notes={item.get('notes')}")

with open('data/nfl_depth_charts_2026.json', 'r') as f:
    depth = json.load(f)

for t in ['ATL', 'NO']:
    print(f"\n*** {t} STARTERS ***")
    off = depth.get('teams', {}).get(t, {}).get('offense', {})
    for pos in ['qb', 'rb', 'wr1', 'wr2', 'wr3', 'te', 'lt', 'lg', 'c', 'rg', 'rt']:
        players = off.get(pos, [])
        pnames = [p.get('name') for p in players[:2]] if isinstance(players, list) else str(players)
        print(f"  {pos.upper()}: {pnames}")

print("\n=== LIVE TOUCHDOWN PROPS SUMMARY ===")
with open('data/player_props_live.json', 'r') as f:
    props = json.load(f)

target_players = [
    'Bijan Robinson', 'Tyler Shough', 'Chris Olave', 'Michael Penix Jr.', 
    'Drake London', 'Alvin Kamara', 'Juwan Johnson', 'Kendre Miller', 
    'Brian Robinson Jr.', 'Devaughn Vele', 'Kyle Pitts Sr.', 'Kyle Pitts',
    'Noah Fant', 'Bryce Lance', 'Zachariah Branch', 'Jahan Dotson', 'Austin Hooper'
]

td_data = []
for p in target_players:
    p_data = props.get('players', {}).get(p, {})
    td = p_data.get('Touchdowns', {})
    rush = p_data.get('Rushing Yards', {})
    rec = p_data.get('Receiving Yards', {})
    if td or rush or rec:
        td_books = td.get('books', {})
        # Extract TD odds
        b_odds = {}
        for b, val in td_books.items():
            b_odds[b] = val.get('raw')
        
        rush_line = rush.get('consensus_line')
        rec_line = rec.get('consensus_line')
        td_data.append({
            'player': p,
            'td_odds': b_odds,
            'rush_yds_line': rush_line,
            'rec_yds_line': rec_line
        })

for item in td_data:
    print(f"Player: {item['player']}")
    print(f"  TD Odds: {item['td_odds']}")
    print(f"  Rush Yds Line: {item['rush_yds_line']} | Rec Yds Line: {item['rec_yds_line']}")
