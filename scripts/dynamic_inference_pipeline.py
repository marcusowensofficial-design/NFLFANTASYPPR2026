import pandas as pd
import json
import xgboost as xgb
import numpy as np

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_dynamic_inference():
    print("--- NFL Quant Dynamic Inference Engine ---")
    print("1. Loading Static Player Features...")
    
    # Load our base dataset (what players have done historically)
    df = pd.read_parquet('data/parquets/player_stats_2026.parquet')
    df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    
    # We will build a dynamic feature dataframe for the CURRENT week
    current_week_features = df.copy().set_index('player_name')
    
    print("2. Ingesting Live Telemetry (Injuries & Depth Charts)...")
    try:
        # Load the latest 90-minute inactives and injury reports
        injuries = load_json('data/injuries_live_2026.json')
        # Load the live depth charts to know who steps up
        depth_charts = load_json('data/nfl_depth_charts_2026.json')
    except Exception as e:
        print(f"Warning: Could not load live telemetry files: {e}")
        return
        
    print("\n--- Target/Touch Redistribution Protocol ---")
    # Simulate processing an injury (e.g., if a star RB is out)
    # We iterate through the injury report. If a player is OUT, we find their backup
    # and "gift" the backup a portion of the starter's historical usage (carries/routes).
    
    for injury_record in injuries.get('injuries', []):
        if injury_record.get('status') == 'OUT':
            player = injury_record.get('name')
            team = injury_record.get('team')
            if player in current_week_features.index:
                starter_stats = current_week_features.loc[player]
                position = starter_stats['position']
                
                # Find the backup on the depth chart
                team_chart = depth_charts.get(team, {}).get(position, [])
                
                backup = None
                for idx, chart_player in enumerate(team_chart):
                    if chart_player == player and idx + 1 < len(team_chart):
                        backup = team_chart[idx + 1]
                        break
                
                if backup and backup in current_week_features.index:
                    print(f"[{team}] {player} is OUT. Redistributing usage to {backup}...")
                    
                    # Quant Rule: The backup doesn't get 100% of the alpha's volume. 
                    # We apply an efficiency penalty (e.g., 75% of the carries, 80% of routes)
                    if position == 'RB':
                        current_week_features.at[backup, 'carries_pg'] += (starter_stats['carries_pg'] * 0.75)
                        current_week_features.at[backup, 'inside_5_carry_share'] += (starter_stats['inside_5_carry_share'] * 0.80)
                        current_week_features.at[backup, 'snap_share_pct'] = max(60.0, current_week_features.at[backup, 'snap_share_pct'] + 30.0)
                    elif position in ['WR', 'TE']:
                        current_week_features.at[backup, 'targets_pg'] += (starter_stats['targets_pg'] * 0.70)
                        current_week_features.at[backup, 'route_participation_pct'] = max(75.0, current_week_features.at[backup, 'route_participation_pct'] + 40.0)
                
                # Zero out the injured starter so the model predicts 0
                current_week_features.loc[player, ['carries_pg', 'targets_pg', 'snap_share_pct', 'route_participation_pct']] = 0

    print("\n3. Loading XGBoost Model...")
    model = xgb.XGBRegressor()
    model.load_model('models/xgboost_fppg_model_2026.json')
    
    print("4. Generating Live Projections...")
    
    # Prep features exactly as we trained them
    features = [
        'pass_yds_pg', 'pass_tds_pg', 'rush_yds_pg', 'scramble_pct_pressured', 'p2s_rate', 'clean_pocket_rtg', 'cpoe',
        'carries_pg', 'inside_5_carry_share', 'yac_per_att',
        'targets_pg', 'snap_share_pct', 'route_participation_pct', 'first_read_pct', 'separation_score', 'tprr', 'slot_rate_pct'
    ]
    
    for col in features:
        if col in current_week_features.columns:
            current_week_features[col] = current_week_features[col].fillna(0)
            
    # Re-apply one-hot encoding for the model
    current_week_features = pd.get_dummies(current_week_features, columns=['position'], drop_first=False)
    
    # Ensure all columns from training exist (in correct order)
    # Note: In a real pipeline, we save the exact feature list from training to guarantee matching columns
    # For now, we assume the one-hot columns are QB, RB, WR, TE
    expected_cols = features + ['position_QB', 'position_RB', 'position_TE', 'position_WR']
    for col in expected_cols:
        if col not in current_week_features.columns:
            current_week_features[col] = 0
            
    X_live = current_week_features[expected_cols]
    
    # Predict!
    current_week_features['live_projected_fppg'] = model.predict(X_live)
    
    print("\n[Top 5 Value Shifts Post-Injury Report]")
    # We compare the base prediction vs the new dynamic prediction
    display_df = current_week_features[['team', 'live_projected_fppg', 'fppg_half']].copy()
    display_df['projection_delta'] = display_df['live_projected_fppg'] - display_df['fppg_half']
    
    print(display_df.sort_values(by='projection_delta', ascending=False).head(5).to_string())

if __name__ == '__main__':
    run_dynamic_inference()
