import sqlite3
import pandas as pd

conn = sqlite3.connect('data/fantasy.db')
df = pd.read_sql("""
    SELECT full_name, position, pro_team, actual_points, projected_points, 
           projected_points_model, projected_points_consensus, consensus_rank, injury_status
    FROM players 
    WHERE pro_team IN ('BUF', 'DET')
    ORDER BY actual_points DESC;
""", conn)
print(df.to_string())
