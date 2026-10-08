import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import json
import os
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

def load_training_data():
    """Ingests multi-year player-week data from nflverse or local fallback."""
    try:
        import nfl_data_py as nfl
        print("[1] Ingesting Multi-Year nflverse Data (2022-2024)...")
        df = nfl.import_weekly_data([2022, 2023, 2024])
        print(f" -> Pulled {len(df)} total player-game records.")
        return df
    except Exception as e:
        print(f"[!] Remote pull error: {e}. Falling back to local parquets...")
        local_p = Path("data/parquets/player_stats_2024.parquet")
        if local_p.exists():
            df = pd.read_parquet(local_p)
            print(f" -> Loaded local 2024 dataset: {len(df)} records.")
            return df
        raise FileNotFoundError("No training data found.")

def main():
    print("=" * 65)
    print(" TRAINING PRODUCTION XGBOOST FANTASY PROJECTION MODEL ")
    print(" Multi-Year Opportunity & Usage Learning Engine ")
    print("=" * 65 + "\n")
    
    # 1. Load Data
    df = load_training_data()
    
    # Filter to offensive skill positions
    df = df[df['position'].isin(['QB', 'RB', 'WR', 'TE'])].copy()
    
    # Compute FanDuel Half-PPR scoring
    if 'fantasy_points_ppr' in df.columns and 'receptions' in df.columns:
        df['target_fppg'] = df['fantasy_points_ppr'] - (0.5 * df['receptions'].fillna(0))
    elif 'fantasy_points' in df.columns:
        df['target_fppg'] = df['fantasy_points']
    else:
        df['target_fppg'] = df.get('fppg_half', 0)
        
    # 2. Feature Engineering (Strict Lag-1 Rolling Opportunity)
    print("[2] Constructing Rolling Opportunity Features (Lag-1)...")
    df = df.sort_values(by=['player_id', 'season', 'week']).reset_index(drop=True)
    
    metrics = [
        'targets', 'carries', 'passing_yards', 'receiving_yards',
        'rushing_yards', 'target_share', 'air_yards_share'
    ]
    
    for m in metrics:
        if m not in df.columns:
            df[m] = 0.0
        else:
            df[m] = df[m].fillna(0.0)
            
    for m in metrics:
        df[f'roll3_{m}'] = df.groupby('player_id')[m].transform(
            lambda x: x.rolling(window=3, min_periods=1).mean().shift(1)
        )
        
    roll_cols = [f'roll3_{m}' for m in metrics]
    clean_df = df.dropna(subset=roll_cols + ['target_fppg']).copy()
    
    # One-hot encode position
    clean_df = pd.get_dummies(clean_df, columns=['position'], prefix='pos', drop_first=False)
    pos_cols = [c for c in clean_df.columns if c.startswith('pos_')]
    for c in pos_cols:
        clean_df[c] = clean_df[c].astype(int)
        
    feature_cols = roll_cols + pos_cols
    
    X = clean_df[feature_cols]
    y = clean_df['target_fppg']
    
    print(f"Training set: {len(clean_df)} instances across {len(feature_cols)} features.")
    
    # 3. Train/Test Split (80/20 Chronological Split)
    split_idx = int(len(clean_df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")
    
    # 4. Train XGBoost Model
    print("\n[3] Fitting Enterprise XGBoost Model...")
    model = xgb.XGBRegressor(
        n_estimators=150,
        learning_rate=0.03,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # 5. Evaluate
    train_preds = model.predict(X_train)
    test_preds = model.predict(X_test)
    
    train_rmse = np.sqrt(mean_squared_error(y_train, train_preds))
    test_rmse = np.sqrt(mean_squared_error(y_test, test_preds))
    test_r2 = r2_score(y_test, test_preds)
    test_corr = np.corrcoef(y_test, test_preds)[0, 1]
    
    print("\n[Model Performance Evaluation]")
    print(f"Train RMSE:     {train_rmse:.2f} pts")
    print(f"Out-of-Sample:  {test_rmse:.2f} pts")
    print(f"Explained Var:  R2 = {test_r2:.3f}")
    print(f"Correlation:    r = {test_corr:.3f}")
    
    # Feature Importances
    importances = model.feature_importances_
    fi_df = pd.DataFrame({
        'Feature': feature_cols,
        'Importance': importances
    }).sort_values(by='Importance', ascending=False)
    
    print("\n[Learned Quant Feature Importance]")
    print(fi_df.to_string(index=False))
    
    # 6. Save Model and Metadata
    os.makedirs('models', exist_ok=True)
    model_path = 'models/xgboost_fppg_model_2026.json'
    meta_path = 'models/xgboost_feature_schema.json'
    
    model.save_model(model_path)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({
            'features': feature_cols,
            'test_rmse': float(test_rmse),
            'test_corr': float(test_corr),
            'training_samples': len(clean_df)
        }, f, indent=2)
        
    print(f"\n[SUCCESS] Model saved to {model_path}")
    print(f"[SUCCESS] Feature schema saved to {meta_path}")

if __name__ == '__main__':
    main()
