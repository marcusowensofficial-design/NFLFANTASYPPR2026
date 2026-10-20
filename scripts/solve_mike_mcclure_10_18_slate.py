import json
import os
import pandas as pd
import numpy as np

def run_all_qb_audits():
    csv_path = "data/mainslate10-18-26.csv"
    df = pd.read_csv(csv_path)

    df['name'] = df['Nickname'].str.strip()
    df['pos'] = df['Position'].str.strip()
    df['team'] = df['Team'].str.strip()
    df['opp'] = df['Opponent'].str.strip()
    df['salary'] = df['Salary'].astype(int)
    df['fppg'] = df['FPPG'].fillna(0.0).astype(float)
    df['injury'] = df['Injury Indicator'].fillna('').str.strip()

    core = ['Drake London', 'Puka Nacua', "D'Andre Swift", 'Rhamondre Stevenson']
    core_sal = 7600 + 9000 + 6600 + 6300 # $29,500
    core_fppg = 13.74 + 17.08 + 15.36 + 10.66 # 56.84

    pool_qbs = ['Matthew Stafford', 'Caleb Williams', 'Josh Allen', 'Kirk Cousins', 'Drake Maye', 'Patrick Mahomes', 'Daniel Jones', 'Tyler Shough']
    pool_rbs = ["D'Andre Swift", 'Rhamondre Stevenson', 'Bijan Robinson', 'Kyren Williams', 'Jonathan Taylor', 'Chuba Hubbard', 'Kenneth Walker III', 'Tyler Allgeier', 'Braelon Allen', 'James Cook III', 'Jaylen Warren', 'Ashton Jeanty']
    pool_wrs = ['Drake London', 'Puka Nacua', 'Luther Burden III', 'Davante Adams', 'Michael Wilson', 'Carnell Tate', 'Germie Bernard', 'Garrett Wilson', 'Tetairoa McMillan', 'Rome Odunze', 'Xavier Worthy', 'KC Concepcion Jr.', 'Jalen Coker', 'Denzel Boston', 'Chris Olave', 'Devaughn Vele', 'Khalil Shakir']
    pool_tes = ['Isaiah Likely', 'Travis Kelce', 'Brock Bowers', 'Colston Loveland', 'Dalton Kincaid', 'Harold Fannin Jr.']
    pool_dsts = ['Carolina Panthers', 'Tampa Bay Buccaneers', 'Cleveland Browns', 'New England Patriots', 'Kansas City Chiefs', 'New Orleans Saints', 'Philadelphia Eagles', 'Los Angeles Rams']

    all_pool_names = set(core + pool_qbs + pool_rbs + pool_wrs + pool_tes + pool_dsts)
    pool_df = df[df['name'].isin(all_pool_names) | df['Last Name'].isin(pool_dsts)].copy().reset_index(drop=True)

    # Convert to pure dicts for ultra-fast lookup
    records_by_name = {}
    for _, r in pool_df.iterrows():
        rec = r.to_dict()
        records_by_name[r['name']] = rec
        records_by_name[r['Last Name']] = rec

    dst_records = [records_by_name[d] for d in pool_dsts]
    te_records = [records_by_name[t] for t in pool_tes]
    wr_records = [records_by_name[w] for w in pool_wrs if w not in core]
    rb_records = [records_by_name[r] for r in pool_rbs if r not in core]

    # Pre-build flex candidates
    # (name, record, pos_type)
    base_flex = [(r['name'], r, 'RB') for r in rb_records] + [(t['name'], t, 'TE') for t in te_records]

    for target_qb in ['Matthew Stafford', 'Caleb Williams', 'Josh Allen', 'Kirk Cousins', 'Drake Maye']:
        qb_row = records_by_name[target_qb]
        results = []

        for wr3_row in wr_records:
            wr3_name = wr3_row['name']
            curr_flex_candidates = base_flex + [(w['name'], w, 'WR') for w in wr_records if w['name'] != wr3_name]

            for te_row in te_records:
                te_name = te_row['name']

                for flex_name, flex_row, fpos in curr_flex_candidates:
                    if fpos == 'TE' and flex_name == te_name:
                        continue

                    # Pre-calculate partial salary
                    sub_sal = core_sal + qb_row['salary'] + wr3_row['salary'] + te_row['salary'] + flex_row['salary']
                    if sub_sal + 3200 > 60000: # 3200 is cheapest DST
                        continue

                    sub_fppg = core_fppg + qb_row['fppg'] + wr3_row['fppg'] + te_row['fppg'] + flex_row['fppg']
                    teams = {'ATL', 'LAR', 'CHI', 'NE', qb_row['team'], wr3_row['team'], te_row['team'], flex_row['team']}

                    for dst_row in dst_records:
                        if dst_row['opp'] in teams:
                            continue

                        tot_sal = sub_sal + dst_row['salary']
                        if 57000 <= tot_sal <= 60000:
                            fppg = sub_fppg + dst_row['fppg']
                            has_stack = (wr3_row['team'] == qb_row['team'] or te_row['team'] == qb_row['team'] or flex_row['team'] == qb_row['team'])
                            has_bringback = (wr3_row['team'] == qb_row['opp'] or te_row['team'] == qb_row['opp'] or flex_row['team'] == qb_row['opp'])
                            results.append((
                                fppg, tot_sal, target_qb, wr3_name, te_name, flex_name, fpos, dst_row['name'], has_stack, has_bringback
                            ))

        # Sort results
        results.sort(key=lambda x: x[0], reverse=True)
        print(f"\n==================================================")
        print(f"QB: {target_qb} | Total Valid: {len(results)}")
        print(f"==================================================")

        # Deduplicate
        seen = set()
        deduped = []
        for r in results:
            key = (r[2], r[3], r[4], r[5], r[7], r[1])
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        print("--- Top 3 Overall ---")
        for r in deduped[:3]:
            print(f"WR3: {r[3]:<16} | TE: {r[4]:<14} | FLEX: {r[5]} ({r[6]}) | DST: {r[7]:<20} | ${r[1]:,} | FPPG: {r[0]:.2f} | Stk: {r[8]} | BB: {r[9]}")

        # Best Stacked
        stacked = [r for r in deduped if r[8]]
        if stacked:
            print("--- Top 3 Stacked with Primary Pass Catcher ---")
            for r in stacked[:3]:
                print(f"WR3: {r[3]:<16} | TE: {r[4]:<14} | FLEX: {r[5]} ({r[6]}) | DST: {r[7]:<20} | ${r[1]:,} | FPPG: {r[0]:.2f} | BB: {r[9]}")

if __name__ == '__main__':
    run_all_qb_audits()
