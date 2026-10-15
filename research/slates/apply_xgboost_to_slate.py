import pandas as pd
import json
import xgboost as xgb
import subprocess
import os
import sys
from pathlib import Path

def get_slate_features(name, pos, team, fd_fppg, props_data):
    """
    Constructs opportunity feature vector for a slate player using:
    1. Consensus props from sharp sportsbooks (player_props_live.json)
    2. Baseline usage and position
    """
    player_props = props_data.get('players', {}).get(name, {})
    
    # 1. Rushing metrics
    rush_line = player_props.get('Rushing Yards', {}).get('consensus_line')
    if rush_line is not None:
        rush_yds = float(rush_line)
        carries = rush_yds / 4.2
    else:
        # Fallback to positional estimate
        if pos == 'RB':
            rush_yds = max(0.0, fd_fppg * 3.5)
            carries = rush_yds / 4.0
        elif pos == 'QB':
            rush_yds = 12.0
            carries = 2.5
        else:
            rush_yds, carries = 0.0, 0.0
            
    # 2. Receiving metrics
    rec_line = player_props.get('Receiving Yards', {}).get('consensus_line')
    if rec_line is not None:
        rec_yds = float(rec_line)
        targets = rec_yds / 8.5
        tgt_share = min(0.32, targets / 32.0)
        air_share = min(0.38, tgt_share * 1.2)
    else:
        if pos in ['WR', 'TE']:
            rec_yds = max(0.0, fd_fppg * 4.0)
            targets = rec_yds / 8.0
            tgt_share = min(0.28, targets / 32.0)
            air_share = min(0.35, tgt_share * 1.1)
        elif pos == 'RB':
            rec_yds = max(0.0, (fd_fppg - (carries * 0.4)) * 3.0)
            targets = rec_yds / 6.0
            tgt_share = min(0.18, targets / 32.0)
            air_share = 0.04
        else:
            rec_yds, targets, tgt_share, air_share = 0.0, 0.0, 0.0, 0.0
            
    # 3. Passing metrics
    pass_line = player_props.get('Passing Yards', {}).get('consensus_line')
    if pass_line is not None:
        pass_yds = float(pass_line)
    else:
        if pos == 'QB':
            pass_yds = max(180.0, fd_fppg * 14.0)
        else:
            pass_yds = 0.0
            
    # 4. TD Probability adjustment
    td_books = player_props.get('Touchdowns', {}).get('books', {})
    td_bonus = 0.0
    for b, details in td_books.items():
        odds = str(details.get('odds', details.get('raw', '')))
        if odds.startswith('-'):
            try:
                val = abs(float(odds))
                prob = val / (val + 100.0)
                td_bonus = max(td_bonus, prob * 6.0)
            except:
                pass
        elif odds.startswith('+'):
            try:
                val = float(odds)
                prob = 100.0 / (val + 100.0)
                td_bonus = max(td_bonus, prob * 6.0)
            except:
                pass
                
    return {
        'roll3_carries': carries,
        'roll3_rushing_yards': rush_yds,
        'roll3_targets': targets,
        'roll3_receiving_yards': rec_yds,
        'roll3_passing_yards': pass_yds,
        'roll3_target_share': tgt_share,
        'roll3_air_yards_share': air_share,
        'td_bonus': td_bonus
    }

def main():
    print("=" * 65)
    print(" SYNDICATE PIPELINE: Injecting Quant ML Projections into Slate ")
    print("=" * 65 + "\n")
    
    # 1. Get Vegas Total for Dynamic Salary Buffer (GEMINI.md Rule)
    vegas_total = 44.5
    try:
        with open('data/vegas_movement_2026.json', 'r', encoding='utf-8') as f:
            vegas = json.load(f)
            for game in vegas.get('games', []):
                if 'ATL' in game.get('teams', []) and 'NO' in game.get('teams', []):
                    vegas_total = float(game.get('total', 44.5))
                    break
    except Exception:
        pass
        
    if vegas_total <= 42.0:
        min_buffer, max_buffer = 1500, 3500
    elif vegas_total <= 46.5:
        min_buffer, max_buffer = 800, 2500
    else:
        min_buffer, max_buffer = 200, 1000
        
    print(f"Vegas Game Total: {vegas_total} | Salary Buffer: ${min_buffer} - ${max_buffer} unspent\n")
    
    # 2. Load Model and Feature Schema
    with open('models/xgboost_feature_schema.json', 'r', encoding='utf-8') as f:
        schema = json.load(f)
    feature_names = schema['features']
    
    model = xgb.XGBRegressor()
    model.load_model('models/xgboost_fppg_model_2026.json')
    print(f"Loaded trained XGBoost model ({schema['training_samples']} samples, Out-of-Sample RMSE: {schema['test_rmse']:.2f})\n")
    
    # 3. Load Sharp Props
    props_data = {}
    try:
        with open('data/player_props_live.json', 'r', encoding='utf-8') as f:
            props_data = json.load(f)
    except Exception as e:
        print(f"[!] Could not load player_props_live.json: {e}")
        
    # 4. Load Slate CSV
    csv_path = 'data/10-5-26-falcons-vs-saintssinglegameslate.csv'
    slate_df = pd.read_csv(csv_path)
    print(f"Loaded {len(slate_df)} players from {csv_path}")
    
    # 5. Predict Projections for All Offensive Skill Players
    skill_rows = []
    skill_indices = []
    
    # Known ghost punts / backups to strictly zero out
    ghost_punts = {
        'Charlie Smyth', 'Vinny Anthony II', 'Antwane Wells Jr.', 'Cal Adomitis', 
        'Charlie Woerner', 'Nick Muse', 'Trey Sermon', 'Spencer Rattler', 
        'Tua Tagovailoa', 'Zach Wilson', 'Cooper Rush', 'Jack Strand', 
        'Jalen Moreno-Cropper', 'Casey Washington', 'Nathaniel Peat', 'Ulysses Bentley IV'
    }

    for idx, row in slate_df.iterrows():
        pos = row['Position']
        name = row['Nickname']
        team = row['Team']
        played = pd.to_numeric(row.get('Played', 0), errors='coerce') or 0
        fd_fppg = float(row.get('FPPG', 0.0)) if pd.notnull(row.get('FPPG')) else 0.0
        
        # Zero out ghost punts or players with 0 games played
        if name in ghost_punts or (played == 0 and pos != 'D'):
            slate_df.at[idx, 'FPPG'] = 0.0
            continue
            
        if pos in ['QB', 'RB', 'WR', 'TE'] and row.get('Salary', 0) > 0 and fd_fppg > 0:
            feat_dict = get_slate_features(name, pos, team, fd_fppg, props_data)
            
            # Position dummy indicators
            for p in ['QB', 'RB', 'TE', 'WR']:
                feat_dict[f'pos_{p}'] = 1 if pos == p else 0
                
            skill_rows.append(feat_dict)
            skill_indices.append(idx)
            
    if skill_rows:
        features_df = pd.DataFrame(skill_rows)
        # Separate td_bonus
        td_bonuses = features_df['td_bonus'].values
        X_slate = features_df[feature_names]
        
        raw_preds = model.predict(X_slate)
        # Apply TD probability boost from sportsbook props
        final_preds = raw_preds + (td_bonuses * 0.7)
        
        # Write back to slate
        for i, idx in enumerate(skill_indices):
            new_fppg = round(float(final_preds[i]), 2)
            slate_df.at[idx, 'FPPG'] = new_fppg
            
        print(f"Successfully generated ML & Sharp Props projections for {len(skill_indices)} viable skill players.")
        print(f"Strictly zeroed out {len(ghost_punts)} ghost punts, backup kickers, and 0-game depth players.")
        
    # Save enriched slate
    output_csv = 'data/xgboost-falcons-saints-slate.csv'
    slate_df.to_csv(output_csv, index=False)
    print(f"Saved optimized slate CSV to {output_csv}\n")
    
    # 6. Execute Multi-Script Tournament Optimizer in Portfolio Mode
    print("=" * 65)
    print(" EXECUTING 5-ENTRY DIVERSIFIED TOURNAMENT PORTFOLIO (GEMINI.md) ")
    print(" Enforcing 50% Max Non-QB Exposure & Multi-MVP Allocation ")
    print("=" * 65)
    
    cmd = [
        sys.executable,
        'scripts/run_showdown_optimizer.py',
        '--slate', output_csv,
        '--portfolio', '5',
        '--max-exposure', '0.50',
        '--max-mvp-exposure', '0.20',
        '--vegas-total', str(vegas_total),
        '--min-buffer', str(min_buffer),
        '--max-buffer', str(max_buffer)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Optimizer Errors / Warnings:\n", result.stderr)

if __name__ == '__main__':
    main()
