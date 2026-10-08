import json
import math

with open('data/player_props_live.json', 'r') as f:
    props = json.load(f)

# Let's inspect all prop categories for Bijan, Olave, London, Kamara, Shough, etc.
key_players = ['Bijan Robinson', 'Chris Olave', 'Drake London', 'Alvin Kamara', 'Tyler Shough', 'Juwan Johnson', 'Devaughn Vele', 'Kyle Pitts', 'Kendre Miller', 'Brian Robinson Jr.']

print("=== DETAILED PROPS PER PLAYER ===")
for p in key_players:
    p_data = props.get('players', {}).get(p, {})
    print(f"\n*** {p} ***")
    for cat, val in p_data.items():
        if cat == 'Touchdowns':
            print(f"  Touchdowns: {val}")
        elif cat in ['Rushing Yards', 'Receiving Yards', 'Passing Yards', 'Receptions']:
            print(f"  {cat}: consensus={val.get('consensus_line')}")
        else:
            print(f"  {cat}: {val}")
