"""Database schema migration, duplicate consolidation, and token normalization."""

import re
import sqlite3
from collections import defaultdict


def _norm_name(name: str) -> str:
    cleaned = (name or "").strip().lower()
    cleaned = re.sub(r"\b(jr\.?|sr\.?|iii|ii|iv|v)\b", "", cleaned)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _deduplicate_players(cur: sqlite3.Cursor) -> dict[str, int]:
    """Merge duplicate players & legacy synthetic DST rows while preserving any roster_entries FKs."""
    cur.execute(
        """
        SELECT p.id, p.full_name, p.position, p.pro_team,
               p.projected_points_espn, p.projected_points_fp, p.projected_points_sleeper,
               COUNT(r.id) as roster_cnt
        FROM players p
        LEFT JOIN roster_entries r ON r.player_id = p.id
        GROUP BY p.id
        """
    )
    rows = cur.fetchall()

    # Delete synthetic 99xxxxx DST rows if a canonical D/ST row (-16xxx or position='D/ST') exists for that team
    canon_dst_teams = {
        r[3] for r in rows if r[2] == "D/ST" and r[0] < 0
    }
    dst_removed = 0
    for r in rows:
        pid, name, pos, team, _, _, _, roster_cnt = r
        if pos == "DST":
            if team in canon_dst_teams and roster_cnt == 0:
                cur.execute("DELETE FROM players WHERE id = ?", (pid,))
                dst_removed += 1
            else:
                cur.execute("UPDATE players SET position = 'D/ST' WHERE id = ?", (pid,))

    # Re-fetch after DST normalization and deduplicate remaining identical (norm_name, pos) pairs
    cur.execute(
        """
        SELECT p.id, p.full_name, p.position, p.pro_team,
               p.projected_points_espn, p.projected_points_fp, p.projected_points_sleeper,
               COUNT(r.id) as roster_cnt
        FROM players p
        LEFT JOIN roster_entries r ON r.player_id = p.id
        GROUP BY p.id
        """
    )
    groups: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for r in cur.fetchall():
        pos_norm = "D/ST" if r[2] == "DST" else (r[2] or "").upper().strip()
        key = (_norm_name(r[1]), pos_norm)
        groups[key].append(r)

    dups_merged = 0
    for _, items in groups.items():
        if len(items) <= 1:
            continue
        # Rank keeper: rostered first, non-99xxxxx real ESPN ID second, higher external consensus sum third
        items_sorted = sorted(
            items,
            key=lambda x: (
                int(x[7] > 0),
                int(not (9900000 <= x[0] <= 9999999)),
                float((x[4] or 0.0) + (x[5] or 0.0) + (x[6] or 0.0)),
                -abs(x[0]),
            ),
            reverse=True,
        )
        keeper = items_sorted[0]
        keep_id = keeper[0]
        for dup in items_sorted[1:]:
            dup_id = dup[0]
            cur.execute(
                "UPDATE OR IGNORE roster_entries SET player_id = ? WHERE player_id = ?",
                (keep_id, dup_id),
            )
            cur.execute("DELETE FROM roster_entries WHERE player_id = ?", (dup_id,))
            cur.execute("DELETE FROM players WHERE id = ?", (dup_id,))
            dups_merged += 1

    # Canonicalize any remaining DST -> D/ST
    cur.execute("UPDATE players SET position = 'D/ST' WHERE position = 'DST'")
    return {"dst_removed": dst_removed, "dups_merged": dups_merged}


def migrate(db_path: str = "data/fantasy.db") -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(players)")
    cols = [c[1] for c in cur.fetchall()]
    new_cols = [
        ("projected_points_espn", "REAL DEFAULT 0.0"),
        ("projected_points_fp", "REAL DEFAULT 0.0"),
        ("projected_points_model", "REAL DEFAULT 0.0"),
        ("projected_points_consensus", "REAL DEFAULT 0.0"),
        ("projected_points_sleeper", "REAL DEFAULT 0.0"),
        ("projected_points_sleeper_half", "REAL DEFAULT 0.0"),
        ("fp_projected_stats_json", 'TEXT DEFAULT "{}"'),
        ("sleeper_projected_stats_json", 'TEXT DEFAULT "{}"'),
    ]
    added = []
    for name, defn in new_cols:
        if name not in cols:
            cur.execute(f"ALTER TABLE players ADD COLUMN {name} {defn}")
            added.append(name)

    # Create weekly_projection_history table cleanly via raw SQL (matching ORM model)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_projection_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name VARCHAR(120) NOT NULL,
            position VARCHAR(10) NOT NULL,
            pro_team VARCHAR(10) NOT NULL DEFAULT 'FA',
            season INTEGER NOT NULL DEFAULT 2026,
            week INTEGER NOT NULL,
            scoring_format VARCHAR(16) NOT NULL DEFAULT 'HALF_PPR',
            model_pts REAL DEFAULT 0.0,
            quant_pts REAL DEFAULT 0.0,
            xgboost_pts REAL DEFAULT 0.0,
            ensemble_pts REAL DEFAULT 0.0,
            props_pts REAL DEFAULT 0.0,
            consensus_pts REAL DEFAULT 0.0,
            fp_pts REAL DEFAULT 0.0,
            sleeper_pts REAL DEFAULT 0.0,
            espn_pts REAL DEFAULT 0.0,
            actual_pts REAL,
            floor_10th REAL DEFAULT 0.0,
            median_50th REAL DEFAULT 0.0,
            ceiling_85th REAL DEFAULT 0.0,
            ceiling_95th REAL DEFAULT 0.0,
            is_bye BOOLEAN DEFAULT 0,
            snapshot_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_proj_hist_player_wk_fmt UNIQUE (player_id, season, week, scoring_format)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_proj_hist_season_week_fmt ON weekly_projection_history (season, week, scoring_format)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS ix_proj_hist_player_id ON weekly_projection_history (player_id)"
    )

    dedup_res = _deduplicate_players(cur)
    conn.commit()
    conn.close()
    print(f"Migration completed. Added columns: {added} | Deduplication: {dedup_res}")


if __name__ == "__main__":
    migrate()
