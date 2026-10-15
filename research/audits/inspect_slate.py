import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/fantasy.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall()]
print('Tables in fantasy.db:')
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    print(f"  {t}: {cursor.fetchone()[0]} rows")

# Check what columns exist in players or other tables
for t in tables:
    cursor.execute(f"PRAGMA table_info({t});")
    cols = [r[1] for r in cursor.fetchall()]
    print(f"Columns for {t}: {cols[:10]} (total {len(cols)})")
