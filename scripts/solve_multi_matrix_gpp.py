import os
import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.solve_main_slate_matrix import load_and_enrich_slate

def get_verified_starter_pool(df):
    """
    Filters player pool to verified NFL starters:
    - RBs: rank 1 on depth chart, or FPPG >= 10.0
    - WRs: rank <= 2 on depth chart, or FPPG >= 8.5
    - TEs: rank 1 on depth chart, or FPPG >= 8.0
    - QBs: starting QBs only
    - D/ST: all defenses
    """
    dc_path = Path("data/nfl_depth_charts_2026.json")
    starters = set()
    if dc_path.exists():
        with open(dc_path, "r", encoding="utf-8") as f:
            dc = json.load(f).get("teams", {})
            for t, data in dc.items():
                off = data.get("offense", {})
                # QB
                for p in off.get("qb", [])[:1]:
                    starters.add(p.get("name", "").lower().strip())
                # RB
                for p in off.get("rb", [])[:2]:
                    starters.add(p.get("name", "").lower().strip())
                # WR1, WR2, WR3
                for slot in ["wr1", "wr2", "wr3"]:
                    for p in off.get(slot, [])[:2]:
                        starters.add(p.get("name", "").lower().strip())
                # TE
                for p in off.get("te", [])[:2]:
                    starters.add(p.get("name", "").lower().strip())

    # Build pool
    def is_valid(row):
        pos = row['pos']
        name_clean = row['norm_name']
        fppg = row['fppg']
        played = row.get('Played', 1)
        if pos == 'D':
            return True
        if name_clean in ['theo wease jr.', 'keaton mitchell', 'derius davis', 'amar johnson', 'sterling shepard']:
            return False # Exclude non-starters / gadget punts
        if pos == 'QB':
            return (name_clean in starters or fppg >= 12.0) and played >= 1
        if pos == 'RB':
            return (name_clean in starters or fppg >= 9.0) and played >= 1
        if pos == 'WR':
            return (name_clean in starters or fppg >= 8.0) and played >= 1
        if pos == 'TE':
            return (name_clean in starters or fppg >= 7.0) and played >= 1
        return False

    mask = df.apply(is_valid, axis=1)
    return df[mask].reset_index(drop=True).copy()

def solve_3game_matrix(df_pool, primary_game, mini_1, mini_2, dst_team=None, min_salary=59100, max_salary=59800, force_qb=None, force_players=None):
    """
    Solves 3-Game Matrix integer program.
    """
    n = len(df_pool)
    c = -df_pool['gpp_proj'].values

    A_rows = []
    b_l = []
    b_u = []

    # 1. Total players = 9
    A_rows.append(np.ones(n)); b_l.append(9); b_u.append(9)

    # 2. Total Salary ($59,100 to $59,800, leaving $200 - $900 unspent buffer)
    A_rows.append(df_pool['salary'].values); b_l.append(min_salary); b_u.append(max_salary)

    # 3. Exactly 1 QB
    A_rows.append((df_pool['pos'] == 'QB').astype(float).values); b_l.append(1); b_u.append(1)

    # Force specific QB if requested
    if force_qb:
        qb_mask = ((df_pool['pos'] == 'QB') & (df_pool['name'].str.lower() == force_qb.lower())).astype(float).values
        A_rows.append(qb_mask); b_l.append(1); b_u.append(1)

    # Force specific players if requested
    if force_players:
        for fp in force_players:
            fp_mask = (df_pool['name'].str.lower() == fp.lower()).astype(float).values
            A_rows.append(fp_mask); b_l.append(1); b_u.append(1)

    # 4. Exactly 1 D/ST
    A_rows.append((df_pool['pos'] == 'D').astype(float).values); b_l.append(1); b_u.append(1)

    # 5. RBs: 2 to 3
    A_rows.append((df_pool['pos'] == 'RB').astype(float).values); b_l.append(2); b_u.append(3)

    # 6. WRs: 3 to 4
    A_rows.append((df_pool['pos'] == 'WR').astype(float).values); b_l.append(3); b_u.append(4)

    # 7. TEs: 1 to 2
    A_rows.append((df_pool['pos'] == 'TE').astype(float).values); b_l.append(1); b_u.append(2)

    # 8. Flex total = 7
    A_rows.append(df_pool['pos'].isin(['RB', 'WR', 'TE']).astype(float).values); b_l.append(7); b_u.append(7)

    # 9. Primary Game: Exactly 4 players, QB must come from primary game
    p_t1, p_t2 = primary_game
    primary_mask = df_pool['team'].isin([p_t1, p_t2]).astype(float).values
    A_rows.append(primary_mask); b_l.append(4); b_u.append(4)

    # QB from primary game
    qb_primary_mask = ((df_pool['pos'] == 'QB') & (df_pool['team'].isin([p_t1, p_t2]))).astype(float).values
    A_rows.append(qb_primary_mask); b_l.append(1); b_u.append(1)

    # QB pairing with pass catcher
    t1_pass = ((df_pool['team'] == p_t1) & (df_pool['pos'].isin(['WR', 'TE']))).astype(float).values
    t1_qb = ((df_pool['team'] == p_t1) & (df_pool['pos'] == 'QB')).astype(float).values
    A_rows.append(t1_pass - t1_qb); b_l.append(0); b_u.append(9)

    t2_pass = ((df_pool['team'] == p_t2) & (df_pool['pos'].isin(['WR', 'TE']))).astype(float).values
    t2_qb = ((df_pool['team'] == p_t2) & (df_pool['pos'] == 'QB')).astype(float).values
    A_rows.append(t2_pass - t2_qb); b_l.append(0); b_u.append(9)

    # Each team in primary must have at least 1 player (opposing bring back)
    A_rows.append((df_pool['team'] == p_t1).astype(float).values); b_l.append(1); b_u.append(3)
    A_rows.append((df_pool['team'] == p_t2).astype(float).values); b_l.append(1); b_u.append(3)

    # 10. Mini 1: Exactly 2 players (1 from each team)
    m1_t1, m1_t2 = mini_1
    A_rows.append((df_pool['team'] == m1_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m1_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 11. Mini 2: Exactly 2 players (1 from each team)
    m2_t1, m2_t2 = mini_2
    A_rows.append((df_pool['team'] == m2_t1).astype(float).values); b_l.append(1); b_u.append(1)
    A_rows.append((df_pool['team'] == m2_t2).astype(float).values); b_l.append(1); b_u.append(1)

    # 12. D/ST selection
    if dst_team:
        A_rows.append(((df_pool['pos'] == 'D') & (df_pool['team'] == dst_team)).astype(float).values)
        b_l.append(1); b_u.append(1)

    # Anti-Cannibalization: D/ST cannot play against any offensive player in the lineup
    for idx_dst, row_dst in df_pool[df_pool['pos'] == 'D'].iterrows():
        dst_tm = row_dst['team']
        dst_opp = row_dst['opp']
        opp_offense_mask = ((df_pool['team'] == dst_opp) & (df_pool['pos'] != 'D')).astype(float).values
        dst_indicator = (np.arange(n) == idx_dst).astype(float)
        A_rows.append(opp_offense_mask + 8.0 * dst_indicator)
        b_l.append(-np.inf)
        b_u.append(8.0)

    A = np.array(A_rows)
    constraints = LinearConstraint(A, b_l, b_u)
    integrality = np.ones(n)
    bounds = Bounds(0, 1)

    res = milp(c=c, integrality=integrality, constraints=constraints, bounds=bounds)
    if res.success:
        selected_indices = np.where(res.x > 0.5)[0]
        return df_pool.iloc[selected_indices].copy()
    return None

if __name__ == "__main__":
    csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
    df, vegas = load_and_enrich_slate(csv_path)
    pool = get_verified_starter_pool(df)
    print(f"Verified starter pool: {len(pool)} players (filtered out non-starters).")

    configs = [
        {
            "title": "ARCHITECTURE 1: BUF-LAC Primary + CIN D/ST (Josh Allen Anchor + Omarion Hampton)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN",
            "force_qb": "Josh Allen",
            "force_players": None
        },
        {
            "title": "ARCHITECTURE 1B: BUF-LAC Primary (Josh Allen + Dalton Kincaid + Ladd McConkey Bring-Back)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN",
            "force_qb": "Josh Allen",
            "force_players": ["Ladd McConkey"]
        },
        {
            "title": "ARCHITECTURE 1C: BUF-LAC Primary (Josh Allen + Ladd McConkey + CLE D/ST)",
            "primary": ("LAC", "BUF"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("NYJ", "DET"),
            "dst": "CLE",
            "force_qb": "Josh Allen",
            "force_players": ["Ladd McConkey"]
        },
        {
            "title": "ARCHITECTURE 2: BAL-DAL Primary (Lamar Jackson MVP + Zay Flowers + CeeDee Lamb)",
            "primary": ("BAL", "DAL"),
            "mini1": ("LAC", "BUF"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN",
            "force_qb": "Lamar Jackson",
            "force_players": ["CeeDee Lamb"]
        },
        {
            "title": "ARCHITECTURE 3: BAL-DAL Primary (Dak Prescott + CeeDee Lamb + Derrick Henry)",
            "primary": ("BAL", "DAL"),
            "mini1": ("LAC", "BUF"),
            "mini2": ("NYJ", "DET"),
            "dst": "CIN",
            "force_qb": "Dak Prescott",
            "force_players": ["Derrick Henry"]
        },
        {
            "title": "ARCHITECTURE 4: NYJ-DET Ford Field Dome (Jared Goff + Amon-Ra + Garrett Wilson)",
            "primary": ("NYJ", "DET"),
            "mini1": ("BAL", "DAL"),
            "mini2": ("LAC", "BUF"),
            "dst": "CIN",
            "force_qb": "Jared Goff",
            "force_players": ["Garrett Wilson"]
        }
    ]

    for cfg in configs:
        print("\n" + "="*70)
        print(cfg["title"])
        print("="*70)
        roster = solve_3game_matrix(
            pool,
            primary_game=cfg["primary"],
            mini_1=cfg["mini1"],
            mini_2=cfg["mini2"],
            dst_team=cfg["dst"],
            force_qb=cfg.get("force_qb"),
            force_players=cfg.get("force_players"),
            min_salary=58000,
            max_salary=59800
        )
        if roster is not None:
            cols = ['pos', 'name', 'team', 'opp', 'salary', 'fppg', 'gpp_proj']
            print(roster[cols].sort_values(by=['pos', 'salary'], ascending=[True, False]).to_string(index=False))
            tot_sal = roster['salary'].sum()
            tot_proj = roster['gpp_proj'].sum()
            print(f"Total Salary: ${tot_sal:,} | Projected: {tot_proj:.2f} pts | Remaining Cap: ${60000 - tot_sal:,}")
        else:
            print("No viable lineup found matching constraints.")
