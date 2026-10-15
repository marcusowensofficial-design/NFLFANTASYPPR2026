import json

with open('data/encyclopedia/nfl_super_brain_master.json', 'r') as f:
    brain = json.load(f)

print("Super Brain keys count:", len(brain))

target_players = [
    'bijan robinson', 'tyler shough', 'chris olave', 'michael penix jr', 'michael penix jr.',
    'drake london', 'alvin kamara', 'juwan johnson', 'kendre miller', 
    'brian robinson jr', 'brian robinson jr.', 'devaughn vele', 'kyle pitts',
    'kyle pitts sr.', 'bryce lance'
]

for p in target_players:
    if p in brain:
        print(f"\n==================== {p.upper()} ====================")
        print(json.dumps(brain[p], indent=2))
