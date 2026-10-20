"""
Generate 150 FanDuel Single-Game (Showdown) Lineups strictly calibrated to
Mike McClure's (SportsLine) published MVP and FLEX exposure targets.

Outputs:
1. data/MIKE_MCCLURES_LINEUPS_upload.csv  (FanDuel upload format)
2. data/MIKE_MCCLURES_LINEUPS_readable.csv
3. data/MIKE_MCCLURES_LINEUPS_ids.csv
4. data/MIKE_MCCLURES_LINEUPS_exposures.csv
"""

import os
import random
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SLATE_CSV = os.path.join(DATA_DIR, "seavsdensinglegameslate10-15-26.csv")

# Mike McClure's exact published targets
MVP_TARGETS = {
    "Jaxon Smith-Njigba": 42,   # 28%
    "Bo Nix": 33,               # 22%
    "Emanuel Wilson": 24,       # 16%
    "Sam Darnold": 15,          # 10%
    "Jason Myers": 9,           # 6%
    "J.K. Dobbins": 6,          # 4%
    "RJ Harvey": 6,             # 4%
    "Courtland Sutton": 3,      # 2%
    "AJ Barner": 3,             # 2%
    "Wil Lutz": 3,              # 2%
    "Jaylen Waddle": 3,         # 2%
    "Seattle Seahawks": 3       # 2%
}

FLEX_TARGETS = {
    "Sam Darnold": 102,         # 68%
    "Bo Nix": 75,               # 50%
    "Jaxon Smith-Njigba": 63,   # 42%
    "Wil Lutz": 63,             # 42%
    "Emanuel Wilson": 54,       # 36%
    "Jason Myers": 54,          # 36%
    "Denver Broncos": 51,       # 34%
    "J.K. Dobbins": 39,         # 26%
    "Jaylen Waddle": 36,        # 24%
    "Seattle Seahawks": 36,     # 24%
    "AJ Barner": 33,            # 22%
    "George Holani": 21,        # 14%
    "RJ Harvey": 21,            # 14%
    "Courtland Sutton": 18,     # 12%
    "Lil'Jordan Humphrey": 18,  # 12%
    "Troy Franklin": 18,        # 12%
    "Rashid Shaheed": 15,       # 10%
    "Evan Engram": 15,          # 10%
    "Cooper Kupp": 9,           # 6%
    "Elijah Arroyo": 4,         # ~2%
    "Tory Horton": 4,           # ~2%
    "Tyler Badie": 4            # ~2%
}


def load_player_pool():
    df = pd.read_csv(SLATE_CSV)
    # Strip whitespace
    df['Nickname'] = df['Nickname'].str.strip()
    df['Team'] = df['Team'].str.strip()
    df['Position'] = df['Position'].str.strip()
    df['Id'] = df['Id'].str.strip()
    
    # Filter to the 22 players Mike included
    included_names = list(set(list(MVP_TARGETS.keys()) + list(FLEX_TARGETS.keys())))
    pool_df = df[df['Nickname'].isin(included_names)].copy()
    return pool_df


def solve_mike_mcclure_lineups():
    pool_df = load_player_pool()
    player_dict = pool_df.set_index('Nickname').to_dict('index')
    
    # Track current exposures
    mvp_counts = {name: 0 for name in pool_df['Nickname']}
    flex_counts = {name: 0 for name in pool_df['Nickname']}
    
    lineups = []
    seen_rosters = set()
    
    # We have 150 lineups to build. We build by looping through the exact MVP quotas.
    mvp_schedule = []
    for player, target in MVP_TARGETS.items():
        mvp_schedule.extend([player] * target)
    
    random.seed(42)
    random.shuffle(mvp_schedule)
    
    for idx, mvp_name in enumerate(mvp_schedule):
        mvp_info = player_dict[mvp_name]
        mvp_cost = mvp_info['Salary'] * 1.5
        mvp_team = mvp_info['Team']
        
        remaining_cap = 60000 - mvp_cost
        
        # Candidates for FLEX
        eligible_flex = [p for p in player_dict.keys() if p != mvp_name]
        
        best_lineup = None
        best_score = -999999
        
        # We attempt multiple randomized greedy searches weighted by deficit in FLEX target
        attempts = 0
        while attempts < 250:
            attempts += 1
            
            # Weight candidates by their remaining need
            weights = []
            for p in eligible_flex:
                target = FLEX_TARGETS.get(p, 0)
                current = flex_counts[p]
                deficit = max(0.1, target - current + 5.0)
                weights.append(deficit)
            
            weights = np.array(weights)
            weights = weights / weights.sum()
            
            # Sample 5 candidates
            chosen = list(np.random.choice(eligible_flex, size=5, replace=False, p=weights))
            
            # Validate lineup
            # 1. Salary check
            total_salary = mvp_cost + sum(player_dict[p]['Salary'] for p in chosen)
            if total_salary > 60000:
                continue
            
            # 2. Team check (must have at least one SEA and at least one DEN)
            teams = {mvp_team} | {player_dict[p]['Team'] for p in chosen}
            if len(teams) < 2:
                continue
            
            # 3. Correlation check: Never pair D/ST against opposing starting RB1
            has_sea_dst = (mvp_name == "Seattle Seahawks") or ("Seattle Seahawks" in chosen)
            has_den_dst = (mvp_name == "Denver Broncos") or ("Denver Broncos" in chosen)
            has_dobbins = (mvp_name == "J.K. Dobbins") or ("J.K. Dobbins" in chosen)
            has_wilson = (mvp_name == "Emanuel Wilson") or ("Emanuel Wilson" in chosen)
            
            if has_sea_dst and has_dobbins:
                continue
            if has_den_dst and has_wilson:
                continue
            
            # 4. Uniqueness check
            roster_key = (mvp_name, tuple(sorted(chosen)))
            if roster_key in seen_rosters:
                continue
            
            # Evaluate how well this combination helps reach our targets
            score = 0.0
            for p in chosen:
                deficit = FLEX_TARGETS.get(p, 0) - flex_counts[p]
                score += deficit * 10.0
            
            # Slight salary efficiency bonus (spending $57k-$59.5k)
            if 56500 <= total_salary <= 59600:
                score += 25.0
            
            if score > best_score:
                best_score = score
                best_lineup = (mvp_name, chosen, total_salary)
                if attempts > 80:
                    break
        
        if best_lineup is None:
            # Fallback relaxed search
            for _ in range(500):
                chosen = random.sample(eligible_flex, 5)
                total_salary = mvp_cost + sum(player_dict[p]['Salary'] for p in chosen)
                if total_salary <= 60000:
                    teams = {mvp_team} | {player_dict[p]['Team'] for p in chosen}
                    if len(teams) >= 2:
                        roster_key = (mvp_name, tuple(sorted(chosen)))
                        if roster_key not in seen_rosters:
                            best_lineup = (mvp_name, chosen, total_salary)
                            break
        
        if best_lineup is None:
            raise RuntimeError(f"Could not generate valid unique lineup for MVP {mvp_name} at index {idx}")
        
        mvp_name, chosen, total_salary = best_lineup
        roster_key = (mvp_name, tuple(sorted(chosen)))
        seen_rosters.add(roster_key)
        
        mvp_counts[mvp_name] += 1
        for p in chosen:
            flex_counts[p] += 1
        
        lineups.append({
            'MVP': mvp_name,
            'FLEX1': chosen[0],
            'FLEX2': chosen[1],
            'FLEX3': chosen[2],
            'FLEX4': chosen[3],
            'FLEX5': chosen[4],
            'Salary_Spent': int(total_salary),
            'Unspent_Buffer': int(60000 - total_salary)
        })

    # Output files
    df_lineups = pd.DataFrame(lineups)
    
    # 1. Readable CSV
    readable_path = os.path.join(DATA_DIR, "MIKE_MCCLURES_LINEUPS_readable.csv")
    df_lineups.to_csv(readable_path, index=False)
    
    # 2. Upload CSV (MVP,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX,AnyFLEX) formatted as Id:Nickname
    upload_rows = []
    for _, row in df_lineups.iterrows():
        mvp_id_str = f"{player_dict[row['MVP']]['Id']}:{row['MVP']}"
        flex_id_strs = [f"{player_dict[row[f'FLEX{i}']]['Id']}:{row[f'FLEX{i}']}" for i in range(1, 6)]
        upload_rows.append([mvp_id_str] + flex_id_strs)
    
    df_upload = pd.DataFrame(upload_rows, columns=["MVP", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX"])
    upload_path = os.path.join(DATA_DIR, "MIKE_MCCLURES_LINEUPS_upload.csv")
    df_upload.to_csv(upload_path, index=False)
    
    # 3. Raw IDs CSV
    id_rows = []
    for _, row in df_lineups.iterrows():
        mvp_id = player_dict[row['MVP']]['Id']
        flex_ids = [player_dict[row[f'FLEX{i}']]['Id'] for i in range(1, 6)]
        id_rows.append([mvp_id] + flex_ids)
    
    df_ids = pd.DataFrame(id_rows, columns=["MVP", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX", "AnyFLEX"])
    ids_path = os.path.join(DATA_DIR, "MIKE_MCCLURES_LINEUPS_ids.csv")
    df_ids.to_csv(ids_path, index=False)
    
    # 4. Exposure Audit CSV
    exp_records = []
    for p in player_dict.keys():
        m_count = mvp_counts[p]
        m_pct = (m_count / 150.0) * 100.0
        f_count = flex_counts[p]
        f_pct = (f_count / 150.0) * 100.0
        tot_count = m_count + f_count
        tot_pct = (tot_count / 150.0) * 100.0
        
        target_mvp_pct = (MVP_TARGETS.get(p, 0) / 150.0) * 100.0
        target_flex_pct = (FLEX_TARGETS.get(p, 0) / 150.0) * 100.0
        target_tot_pct = target_mvp_pct + target_flex_pct
        
        exp_records.append({
            'Player': p,
            'Target_MVP%': round(target_mvp_pct, 1),
            'Realized_MVP_Count': m_count,
            'Realized_MVP%': round(m_pct, 1),
            'Target_FLEX%': round(target_flex_pct, 1),
            'Realized_FLEX_Count': f_count,
            'Realized_FLEX%': round(f_pct, 1),
            'Target_Total%': round(target_tot_pct, 1),
            'Realized_Total_Count': tot_count,
            'Realized_Total%': round(tot_pct, 1)
        })
    
    df_exp = pd.DataFrame(exp_records).sort_values(by='Realized_Total%', ascending=False)
    exp_path = os.path.join(DATA_DIR, "MIKE_MCCLURES_LINEUPS_exposures.csv")
    df_exp.to_csv(exp_path, index=False)
    
    print("SUCCESS: Generated 150 Mike McClure Calibrated Lineups!")
    print(f"1. [Upload Ready]:   {upload_path}")
    print(f"2. [IDs Only]:       {ids_path}")
    print(f"3. [Readable Audit]: {readable_path}")
    print(f"4. [Exposures]:      {exp_path}\n")
    
    print("=" * 105)
    print("MIKE MCCLURE REALIZED VS TARGET EXPOSURES (150 LINEUPS)")
    print("=" * 105)
    print(df_exp.to_string(index=False))
    print("=" * 105)
    
    print("\nPORTFOLIO METRICS:")
    print(f"- Total Lineups:     {len(df_lineups)}")
    print(f"- Unique Check:      {len(seen_rosters)} / 150")
    print(f"- Min Salary Spent:  ${df_lineups['Salary_Spent'].min():,} (Buffer: ${df_lineups['Unspent_Buffer'].max():,})")
    print(f"- Max Salary Spent:  ${df_lineups['Salary_Spent'].max():,} (Buffer: ${df_lineups['Unspent_Buffer'].min():,})")
    print(f"- Mean Salary Spent: ${df_lineups['Salary_Spent'].mean():,.0f} (Mean Buffer: ${df_lineups['Unspent_Buffer'].mean():,.0f})")


if __name__ == "__main__":
    solve_mike_mcclure_lineups()
