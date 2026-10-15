import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/fantasy.db')
cursor = conn.cursor()

# Check defense_vs_position table for RBs
df_dvp = pd.read_sql_query("SELECT * FROM defense_vs_position WHERE position='RB'", conn)
print("DvP for RBs in DB:")
print(f"Total rows: {len(df_dvp)}")
print("Columns of df_dvp:", df_dvp.columns.tolist())
print(df_dvp.head(10).to_string())

# Also check draftedge_dvp_seed.json
with open('data/draftedge_dvp_seed.json', 'r') as f:
    draftedge = json.load(f)

print("\nDraftEdge keys / structure sample:")
if isinstance(draftedge, list) and len(draftedge) > 0:
    print(f"First item: {draftedge[0]}")
elif isinstance(draftedge, dict):
    print(f"Keys: {list(draftedge.keys())[:10]}")
