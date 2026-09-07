import sqlite3

def migrate():
    conn = sqlite3.connect('data/fantasy.db')
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(players)')
    cols = [c[1] for c in cur.fetchall()]
    new_cols = [
        ('projected_points_espn', 'REAL DEFAULT 0.0'),
        ('projected_points_fp', 'REAL DEFAULT 0.0'),
        ('projected_points_model', 'REAL DEFAULT 0.0'),
        ('projected_points_consensus', 'REAL DEFAULT 0.0'),
        ('fp_projected_stats_json', 'TEXT DEFAULT "{}"'),
    ]
    added = []
    for name, defn in new_cols:
        if name not in cols:
            cur.execute(f'ALTER TABLE players ADD COLUMN {name} {defn}')
            added.append(name)
    conn.commit()
    conn.close()
    print(f"Migration completed. Added columns: {added}")

if __name__ == "__main__":
    migrate()
