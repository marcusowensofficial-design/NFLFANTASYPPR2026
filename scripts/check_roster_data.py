import sqlite3
import pandas as pd

conn = sqlite3.connect('data/fantasy.db')
cursor = conn.cursor()

# Check players table
df = pd.read_sql("SELECT id, full_name, pro_team, position, injury_status, projected_points FROM players WHERE position='RB' ORDER BY projected_points DESC", conn)
print("Top 35 projected RBs in DB:")
print(df.head(35).to_string())

# Check crosswalk or other info
df_cw = pd.read_json('data/player_crosswalk.json')
print("\nCrosswalk shape:", df_cw.shape)
print("Crosswalk columns:", df_cw.columns.tolist() if hasattr(df_cw, 'columns') else type(df_cw))
