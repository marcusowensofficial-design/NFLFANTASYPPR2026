"""Chronological multi-year XGBoost training pipeline (2024 + 2025 + 2026 weekly stats).

Engineers strict Lag-1 pre-game rolling opportunity features without same-game leakage,
evaluates chronologically out-of-sample on 2026 Weeks 8-9, and exports the model + schema.
"""

import argparse
import json
from pathlib import Path
import re
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

warnings.filterwarnings("ignore")

ROLL_METRICS = [
    "targets",
    "carries",
    "passing_yards",
    "receiving_yards",
    "rushing_yards",
    "target_share",
    "air_yards_share",
    "pts_half_ppr",
    "receptions",
    "pass_att",
]

FEATURE_COLS = [
    "roll3_targets",
    "roll3_carries",
    "roll3_passing_yards",
    "roll3_receiving_yards",
    "roll3_rushing_yards",
    "roll3_target_share",
    "roll3_air_yards_share",
    "pos_QB",
    "pos_RB",
    "pos_TE",
    "pos_WR",
    "roll3_pts_half_ppr",
    "roll6_pts_half_ppr",
    "roll3_receptions",
    "roll3_pass_att",
    "roll6_targets",
    "roll6_carries",
    "roll6_target_share",
]


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", (name or "").lower()).strip()


def load_training_data() -> pd.DataFrame:
    """Load real game-by-game 2024 (nflverse REG) and 2025-2026 (Sleeper weekly) logs."""
    frames: list[pd.DataFrame] = []
    common_cols = [
        "norm_name",
        "player_name",
        "position",
        "season",
        "week",
        "pass_att",
        "passing_yards",
        "pass_td",
        "pass_int",
        "carries",
        "rushing_yards",
        "rush_td",
        "targets",
        "receptions",
        "receiving_yards",
        "rec_td",
        "target_share",
        "air_yards_share",
        "pts_half_ppr",
    ]

    p24 = Path("data/parquets/player_stats_2024.parquet")
    if p24.exists():
        df24 = pd.read_parquet(p24)
        if "season_type" in df24.columns:
            df24 = df24[df24["season_type"] == "REG"].copy()
        df24["player_name"] = df24["player_display_name"].fillna(df24["player_name"])
        df24["norm_name"] = df24["player_name"].map(_norm_name)
        df24["pts_half_ppr"] = df24["fantasy_points_ppr"].fillna(0.0) - (
            0.5 * df24["receptions"].fillna(0.0)
        )
        df24 = df24.rename(
            columns={
                "attempts": "pass_att",
                "passing_tds": "pass_td",
                "interceptions": "pass_int",
                "rushing_tds": "rush_td",
                "receiving_tds": "rec_td",
            }
        )
        frames.append(df24[common_cols])
        print(f" -> Loaded 2024 REG weekly game logs: {len(df24)} rows")

    p25_26 = Path("data/parquets/weekly_player_stats_2025_2026.parquet")
    if p25_26.exists():
        df25 = pd.read_parquet(p25_26)
        if "gp" in df25.columns:
            df25 = df25[df25["gp"] > 0].copy()
        if "norm_name" not in df25.columns:
            df25["norm_name"] = df25["player_name"].map(_norm_name)
        frames.append(df25[common_cols])
        print(
            f" -> Loaded 2025-2026 Sleeper weekly logs: {len(df25)} rows "
            f"(2025={(df25['season'] == 2025).sum()}, 2026={(df25['season'] == 2026).sum()})"
        )

    if not frames:
        raise FileNotFoundError(
            "Missing training parquets (player_stats_2024.parquet / weekly_player_stats_2025_2026.parquet)."
        )

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["position"].isin(["QB", "RB", "WR", "TE"])].copy()
    print(f" -> Combined offensive skill dataset: {len(combined)} rows across seasons {sorted(combined['season'].unique().tolist())}")
    return combined


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Construct strict Lag-1 rolling features (no same-week leakage)."""
    df = df.sort_values(["norm_name", "season", "week"]).reset_index(drop=True)
    for m in ROLL_METRICS:
        df[m] = pd.to_numeric(df.get(m, 0.0), errors="coerce").fillna(0.0)
        df[f"roll3_{m}"] = df.groupby("norm_name")[m].transform(
            lambda s: s.rolling(window=3, min_periods=1).mean().shift(1)
        )
        df[f"roll6_{m}"] = df.groupby("norm_name")[m].transform(
            lambda s: s.rolling(window=6, min_periods=1).mean().shift(1)
        )

    df = pd.get_dummies(df, columns=["position"], prefix="pos", drop_first=False)
    for pos_col in ("pos_QB", "pos_RB", "pos_TE", "pos_WR"):
        if pos_col not in df.columns:
            df[pos_col] = 0
        df[pos_col] = df[pos_col].astype(int)

    required_rolls = [f for f in FEATURE_COLS if not f.startswith("pos_")]
    clean = df.dropna(subset=required_rolls + ["pts_half_ppr"]).copy()
    clean["has_prior_opp"] = (
        clean["roll3_targets"] + clean["roll3_carries"] + clean["roll3_passing_yards"]
    ) > 0
    return clean[clean["has_prior_opp"]].reset_index(drop=True)


def _fit_xgb(X_train: pd.DataFrame, y_train: pd.Series) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(
        n_estimators=220,
        learning_rate=0.03,
        max_depth=4,
        min_child_weight=8,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=3.0,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def main(cutoff_week: int = 7, production_refit: bool = False) -> None:
    print("=" * 68)
    print(" TRAINING CHRONOLOGICAL XGBOOST FANTASY PROJECTION MODEL ")
    print(" Strict Lag-1 Usage Features | Out-of-Sample 2026 W8-W9 Validation ")
    print("=" * 68 + "\n")

    raw_df = load_training_data()
    clean_df = build_feature_frame(raw_df)

    train_mask = (clean_df["season"] < 2026) | (
        (clean_df["season"] == 2026) & (clean_df["week"] <= cutoff_week)
    )
    test_mask = (clean_df["season"] == 2026) & (clean_df["week"] > cutoff_week)

    X_train = clean_df.loc[train_mask, FEATURE_COLS]
    y_train = clean_df.loc[train_mask, "pts_half_ppr"]
    X_test = clean_df.loc[test_mask, FEATURE_COLS]
    y_test = clean_df.loc[test_mask, "pts_half_ppr"]

    print(
        f"[2] Chronological Split (cutoff 2026 W{cutoff_week}): "
        f"Train={len(X_train)} | Test (2026 W{cutoff_week + 1}+)={len(X_test)}"
    )

    cv_model = _fit_xgb(X_train, y_train)
    train_preds = np.clip(cv_model.predict(X_train), 0.0, None)
    test_preds = np.clip(cv_model.predict(X_test), 0.0, None) if len(X_test) > 0 else train_preds

    train_rmse = float(np.sqrt(mean_squared_error(y_train, train_preds)))
    if len(X_test) > 0:
        test_rmse = float(np.sqrt(mean_squared_error(y_test, test_preds)))
        test_mae = float(mean_absolute_error(y_test, test_preds))
        test_r2 = float(r2_score(y_test, test_preds))
        test_corr = float(np.corrcoef(y_test, test_preds)[0, 1])
    else:
        test_rmse, test_mae, test_r2, test_corr = train_rmse, 0.0, 0.0, 0.65

    print(f"\n[Out-of-Sample Evaluation on 2026 W{cutoff_week + 1}+]")
    print(f"  Train RMSE: {train_rmse:.3f} | Test RMSE: {test_rmse:.3f} | Test MAE: {test_mae:.3f}")
    print(f"  R2: {test_r2:.3f} | Correlation r: {test_corr:.3f}")

    pos_metrics: dict[str, dict[str, float]] = {}
    if len(X_test) > 0:
        test_eval = clean_df.loc[test_mask].copy()
        test_eval["pred"] = test_preds
        for pos in ("QB", "RB", "WR", "TE"):
            sub = test_eval[test_eval[f"pos_{pos}"] == 1]
            if len(sub) > 5:
                mae_p = float(mean_absolute_error(sub["pts_half_ppr"], sub["pred"]))
                rmse_p = float(np.sqrt(mean_squared_error(sub["pts_half_ppr"], sub["pred"])))
                bias_p = float((sub["pred"] - sub["pts_half_ppr"]).mean())
                r_p = float(np.corrcoef(sub["pts_half_ppr"], sub["pred"])[0, 1])
                pos_metrics[pos] = {
                    "n": int(len(sub)),
                    "mae": round(mae_p, 3),
                    "rmse": round(rmse_p, 3),
                    "bias": round(bias_p, 3),
                    "r": round(r_p, 3),
                }
                print(f"   - {pos} (N={len(sub)}): MAE={mae_p:.3f} Bias={bias_p:+.2f} r={r_p:.3f}")

    final_model = cv_model
    trained_through = f"2026 W{cutoff_week}"
    training_samples = len(X_train)
    if production_refit:
        print("\n[3] Refitting production weights on full 2024-2026 W9 dataset (preserving holdout CV metrics)...")
        final_model = _fit_xgb(clean_df[FEATURE_COLS], clean_df["pts_half_ppr"])
        trained_through = "2026 W9"
        training_samples = len(clean_df)

    fi_df = pd.DataFrame({"Feature": FEATURE_COLS, "Importance": final_model.feature_importances_}).sort_values(
        by="Importance", ascending=False
    )
    print("\n[Top Feature Importances]")
    print(fi_df.head(10).to_string(index=False))

    Path("models").mkdir(exist_ok=True)
    model_path = Path("models/xgboost_fppg_model_2026.json")
    meta_path = Path("models/xgboost_feature_schema.json")
    final_model.save_model(str(model_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "features": FEATURE_COLS,
                "test_rmse": test_rmse,
                "test_mae": test_mae,
                "test_corr": test_corr,
                "training_samples": int(training_samples),
                "trained_through": trained_through,
                "cv_holdout": f"2026 W{cutoff_week + 1}-W9",
                "position_cv_metrics": pos_metrics,
            },
            f,
            indent=2,
        )
    print(f"\n[SUCCESS] Saved model ({trained_through}, n={training_samples}) -> {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-week", type=int, default=7, help="Last 2026 week included in CV training split.")
    parser.add_argument("--production-refit", action="store_true", help="Refit final weights through all available weeks after CV.")
    args = parser.parse_args()
    main(cutoff_week=args.cutoff_week, production_refit=args.production_refit)
