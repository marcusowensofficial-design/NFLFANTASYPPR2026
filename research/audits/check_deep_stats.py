import json
import sqlite3
import pandas as pd

print("=== CHECKING NEXTGEN MICRO METRICS ===")
with open('data/nextgen_micro_metrics_2026.json', 'r') as f:
    ng = json.load(f)

for category in ['teams_coverage', 'quarterbacks', 'running_backs', 'receivers', 'team_forensics']:
    print(f"\n--- {category.upper()} ---")
    data = ng.get(category, {})
    for k, v in data.items():
        if any(term in str(k).lower() or term in str(v).lower() for term in ['atl', 'no', 'bijan', 'olave', 'london', 'kamara', 'shough', 'penix', 'vele', 'juwan', 'pitts']):
            print(f"  {k}: {json.dumps(v, indent=2)}")

print("\n=== CHECKING COACH FOURTH DOWN TENDENCIES ===")
with open('data/coach_fourth_down_tendencies_2026.json', 'r') as f:
    coach = json.load(f)
for t in ['ATL', 'NO']:
    if t in coach:
        print(f"Coach {t}: {json.dumps(coach[t], indent=2)}")
    elif 'teams' in coach and t in coach['teams']:
        print(f"Coach {t}: {json.dumps(coach['teams'][t], indent=2)}")

print("\n=== CHECKING DATABASE / ACTUALS FOR ATL & NO PLAYERS (WEEKS 1-4) ===")
conn = sqlite3.connect('data/fantasy.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cursor.fetchall()]
print("Tables in fantasy.db:", tables)

for t in tables:
    try:
        df = pd.read_sql_query(f"SELECT * FROM {t} LIMIT 5", conn)
        print(f"Table {t} columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error reading {t}: {e}")

conn.close()
