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
    """Ingests multi-year player-week data from nflverse or local fallback + 2026 actuals."""
    frames = []

    # 1. Historical baseline (2024 local parquet or remote nflverse)
    try:
        import nfl_data_py as nfl
        print("[1] Ingesting Multi-Year nflverse Data (2022-2024)...")
        df_hist = nfl.import_weekly_data([2022, 2023, 2024])
        print(f" -> Pulled {len(df_hist)} total player-game records from remote.")
        frames.append(df_hist)
    except Exception as e:
        print(f"[!] Remote pull error: {e}. Falling back to local parquets...")
        local_p = Path("data/parquets/player_stats_2024.parquet")
        if local_p.exists():
            df_hist = pd.read_parquet(local_p)
            print(f" -> Loaded local 2024 dataset: {len(df_hist)} records.")
            frames.append(df_hist)

    # 2. Ingest 2025 Prior Baseline Data (data/parquets/player_stats_2025.parquet)
    p25_path = Path("data/parquets/player_stats_2025.parquet")
    if p25_path.exists():
        try:
            df25 = pd.read_parquet(p25_path)
            records_25 = []
            for _, row in df25.iterrows():
                pos = row["position"]
                if pos not in ["QB", "RB", "WR", "TE"]:
                    continue
                games = int(row.get("games", 0))
                fpts = float(row.get("fppg_half", 0.0))
                if games <= 0 or fpts <= 0.0 or pd.isna(fpts):
                    continue
                name = row["player_name"]
                pid = name.lower().replace(" ", "_")
                tm = row.get("team", "")

                pass_yds = float(row["pass_yds_pg"]) if pd.notna(row.get("pass_yds_pg")) else (max(160.0, fpts * 12.0) if pos == "QB" else 0.0)
                rush_yds = float(row["rush_yds_pg"]) if pd.notna(row.get("rush_yds_pg")) else (max(10.0, fpts * 3.5) if pos == "RB" else (8.0 if pos == "QB" else 0.0))
                carries = float(row["carries_pg"]) if pd.notna(row.get("carries_pg")) else (max(2.5, rush_yds / 4.2) if pos in ["RB", "QB"] else 0.0)
                targets = float(row["targets_pg"]) if pd.notna(row.get("targets_pg")) else (max(1.0, fpts * 0.35) if pos in ["WR", "TE", "RB"] else 0.0)
                rec_yds = float(row["rec_yds_pg"]) if pd.notna(row.get("rec_yds_pg")) else (max(5.0, targets * 10.0) if pos in ["WR", "TE"] else targets * 6.0)
                tgt_share = min(0.35, targets / 32.0)
                air_share = min(0.40, tgt_share * 1.15)

                for wk in range(1, games + 1):
                    records_25.append({
                        "player_id": pid,
                        "player_name": name,
                        "position": pos,
                        "recent_team": tm,
                        "season": 2025,
                        "week": wk,
                        "targets": targets,
                        "carries": carries,
                        "passing_yards": pass_yds,
                        "receiving_yards": rec_yds,
                        "rushing_yards": rush_yds,
                        "target_share": tgt_share,
                        "air_yards_share": air_share,
                        "fantasy_points_ppr": fpts + (0.5 * (targets * 0.65)),
                        "receptions": targets * 0.65,
                        "target_fppg": fpts
                    })
            if records_25:
                df25_expanded = pd.DataFrame(records_25)
                print(f" -> Ingested 2025 prior baseline dataset: {len(df25_expanded)} records across {df25['player_name'].nunique()} key anchors.")
                frames.append(df25_expanded)
        except Exception as err:
            print(f"[!] Warning: failed to load 2025 prior stats: {err}")

    # 3. Ingest 2026 In-Season Realized Player-Game Box Scores (Weeks 1-4)
    dc_path = Path("data/nfl_depth_charts_2026.json")
    p26_path = Path("data/parquets/player_stats_2026.parquet")
    if dc_path.exists() and p26_path.exists():
        try:
            dc = json.load(open(dc_path, "r", encoding="utf-8"))["teams"]
            pos_map = {}
            for tm, tdata in dc.items():
                for slot, plist in tdata.get("offense", {}).items():
                    pos = 'QB' if 'qb' in slot else ('RB' if 'rb' in slot else ('WR' if 'wr' in slot else ('TE' if 'te' in slot else None)))
                    if pos:
                        for p in plist:
                            pos_map[p['name']] = (pos, tm)

            p26 = pd.read_parquet(p26_path)
            p26_map = {row['player_name']: row for _, row in p26.iterrows()}

            weeks = [
                (1, "data/actuals_week1.json"),
                (2, "data/actuals_week2.json"),
                (3, "data/actuals_week3.json"),
                (4, "data/actuals_2026_10_04.json")
            ]

            records_26 = []
            for wk, fpath in weeks:
                p_file = Path(fpath)
                if not p_file.exists():
                    continue
                data = json.load(open(p_file, "r", encoding="utf-8"))
                actuals = data.get("players", data)
                for name, fpts in actuals.items():
                    if not isinstance(fpts, (int, float)) or fpts <= 0.0:
                        continue
                    if name in pos_map:
                        pos, tm = pos_map[name]
                        p_stat = p26_map.get(name)
                        pid = name.lower().replace(" ", "_")

                        if pos == 'QB':
                            pass_yds = float(p_stat['pass_yds_pg']) if p_stat is not None and pd.notna(p_stat.get('pass_yds_pg')) else max(150.0, fpts * 12.0)
                            rush_yds = float(p_stat['rush_yds_pg']) if p_stat is not None and pd.notna(p_stat.get('rush_yds_pg')) else 10.0
                            carries = 3.0
                            targets, rec_yds, tgt_share, air_share = 0.0, 0.0, 0.0, 0.0
                        elif pos == 'RB':
                            carries = float(p_stat['carries_pg']) if p_stat is not None and pd.notna(p_stat.get('carries_pg')) else max(5.0, fpts * 0.8)
                            rush_yds = float(p_stat['rush_yds_pg']) if p_stat is not None and pd.notna(p_stat.get('rush_yds_pg')) else carries * 4.2
                            targets = float(p_stat['targets_pg']) if p_stat is not None and pd.notna(p_stat.get('targets_pg')) else max(1.0, fpts * 0.2)
                            rec_yds = float(p_stat['rec_yds_pg']) if p_stat is not None and pd.notna(p_stat.get('rec_yds_pg')) else targets * 7.0
                            pass_yds = 0.0
                            tgt_share = targets / 32.0
                            air_share = tgt_share * 0.3
                        elif pos in ['WR', 'TE']:
                            targets = float(p_stat['targets_pg']) if p_stat is not None and pd.notna(p_stat.get('targets_pg')) else max(2.0, fpts * 0.5)
                            rec_yds = float(p_stat['rec_yds_pg']) if p_stat is not None and pd.notna(p_stat.get('rec_yds_pg')) else targets * 11.0
                            pass_yds, carries, rush_yds = 0.0, 0.0, 0.0
                            tgt_share = min(0.35, targets / 32.0)
                            air_share = min(0.40, tgt_share * 1.2)
                        else:
                            continue

                        records_26.append({
                            'player_id': pid,
                            'player_name': name,
                            'position': pos,
                            'recent_team': tm,
                            'season': 2026,
                            'week': wk,
                            'targets': targets,
                            'carries': carries,
                            'passing_yards': pass_yds,
                            'receiving_yards': rec_yds,
                            'rushing_yards': rush_yds,
                            'target_share': tgt_share,
                            'air_yards_share': air_share,
                            'fantasy_points_ppr': fpts + (0.5 * (targets * 0.65)),
                            'receptions': targets * 0.65,
                            'target_fppg': fpts
                        })
            if records_26:
                df26 = pd.DataFrame(records_26)
                print(f" -> Ingested 2026 in-season dataset: {len(df26)} records (Weeks 1-4).")
                frames.append(df26)
        except Exception as err:
            print(f"[!] Warning: failed to load 2026 in-season stats: {err}")

    if not frames:
        raise FileNotFoundError("No training data found.")

    combined_df = pd.concat(frames, ignore_index=True)
    print(f" -> Total combined training corpus: {len(combined_df)} records across {combined_df['season'].nunique()} seasons.")
    return combined_df

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
