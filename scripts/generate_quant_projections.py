"""Generate Quant Projections for 2026 NFL Season.

Supports Full-PPR (ESPN Season-Long) and Half-PPR (FanDuel DFS) decoupled engines,
incorporating Next Gen Stats micro-metrics, Trench Pass-Protection Multipliers,
Tri-Season XGBoost Machine Learning, Institutional Inverse-Variance Ensemble Blending,
and Positional Outcome Distribution Percentiles (10th Floor, 50th Median, 85th/95th Ceilings, Boom %).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.session import SessionLocal
from src.db.models import PlayerModel
from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.services.recommendation.projection_engine import (
    quant_projection_engine,
    get_receiver_micro_metrics,
    get_team_trench_metrics,
)
from src.dfs.loader import dfs_loader


def run_slate_projections(
    csv_path: str,
    mode: str,
    limit: int,
    use_ensemble: bool = False,
    show_percentiles: bool = False,
) -> list[dict[str, Any]]:
    """Run projections on a FanDuel slate CSV with dual-engine comparison, ML & percentiles."""
    print(f"\n================================================================================")
    print(f"  FANDUEL DFS SLATE PROJECTION ENGINE: {os.path.basename(csv_path)}")
    if use_ensemble:
        print(f"  [MODE: Institutional Inverse-Variance Ensemble (45% Quant + 35% XGB + 20% Props)]")
    print(f"================================================================================")

    df = asyncio.run(dfs_loader.load_slate(csv_path))
    results = []

    db = SessionLocal()
    try:
        source = "ENSEMBLE" if use_ensemble else "MODEL"
        for _, row in df.iterrows():
            p_name = row.get("name") or row.get("Player", "Unknown")
            team = str(row.get("team") or row.get("Team", ""))
            pos = str(row.get("position") or row.get("Position", ""))
            salary = int(row.get("salary") or row.get("Salary", 0))
            half_pts_prior = float(row.get("proj") or row.get("Projection", 0.0))
            bonus = float(row.get("milestone_bonus") or 0.0)
            sep_score = row.get("separation_score")
            first_read = row.get("first_read_pct")
            reg_idx = row.get("regression_index")

            # Check if player exists in database for itemized stat projection
            db_player = db.query(PlayerModel).filter(PlayerModel.full_name == p_name).first()
            if db_player:
                ppr_res = quant_projection_engine.calculate_player_projection(
                    db_player,
                    scoring_format="PPR",
                    projection_source=source,
                )
                half_res = quant_projection_engine.calculate_player_projection(
                    db_player,
                    scoring_format="HALF_PPR",
                    projection_source=source,
                )
            else:
                temp_player = PlayerModel(
                    id=int(row.get("Id", 0)) if str(row.get("Id", "")).isdigit() else 9999,
                    full_name=p_name,
                    position=pos,
                    pro_team=team,
                    projected_points=half_pts_prior,
                )
                ppr_res = quant_projection_engine.calculate_player_projection(
                    temp_player,
                    scoring_format="PPR",
                    projection_source=source,
                )
                half_res = quant_projection_engine.calculate_player_projection(
                    temp_player,
                    scoring_format="HALF_PPR",
                    projection_source=source,
                )

            full_pts = ppr_res.projected_points
            half_pts = half_res.projected_points
            delta = round(full_pts - half_pts, 2)
            val_rating = round((half_pts / max(salary, 1)) * 1000, 2)

            results.append({
                "player": p_name,
                "team": team,
                "position": pos,
                "salary": salary,
                "half_ppr": round(half_pts, 2),
                "full_ppr": round(full_pts, 2),
                "ensemble_half": half_res.ensemble_half_ppr,
                "ensemble_full": ppr_res.ensemble_full_ppr,
                "quant_half": half_res.projected_half_ppr_points,
                "xgboost_pts": half_res.xgboost_points,
                "props_pts": half_res.props_points,
                "delta": delta,
                "value_pt_per_k": val_rating,
                "milestone_bonus": bonus,
                "hvt_inside_5": half_res.hvt_inside_5,
                "hvt_inside_10": half_res.hvt_inside_10,
                "xfp": half_res.xfp,
                "fpoe": half_res.fpoe,
                "tprr_vs_zone": half_res.tprr_vs_zone,
                "inside_5_carry_share": half_res.inside_5_carry_share,
                "scramble_rate": half_res.scramble_rate_pressured,
                "p2s_rate": half_res.p2s_rate,
                "scheme_note": half_res.coverage_scheme_note,
                "floor_10th": half_res.floor_10th,
                "median_50th": half_res.median_50th,
                "ceiling_85th": half_res.ceiling_85th,
                "ceiling_95th": half_res.ceiling_95th,
                "boom_prob_25pt": half_res.boom_probability_25pt,
                "bust_prob_6pt": half_res.bust_probability_6pt,
                "separation_score": sep_score if sep_score is not None and not (isinstance(sep_score, float) and sep_score != sep_score) else None,
                "first_read_pct": first_read if first_read is not None and not (isinstance(first_read, float) and first_read != first_read) else None,
                "regression_index": reg_idx if reg_idx is not None and not (isinstance(reg_idx, float) and reg_idx != reg_idx) else None,
            })
    finally:
        db.close()

    # Sort by half_ppr desc
    sort_key = "ensemble_half" if use_ensemble else "half_ppr"
    results.sort(key=lambda x: x[sort_key], reverse=True)
    top_results = results[:limit]

    # Print Primary Table
    if use_ensemble:
        header = (
            f"{'Player':<20} {'Team':<5} {'Pos':<5} {'Salary':<8} "
            f"{'Ensemble':<9} {'Quant':<7} {'XGB':<7} {'Props':<7} {'xFP':<7} {'FPOE':<7} {'Val/k':<6} {'HVT<5':<6}"
        )
        print("\n" + header)
        print("-" * len(header))
        for r in top_results:
            sal_str = f"${r['salary']:,}" if r['salary'] > 0 else "-"
            prp_str = f"{r['props_pts']:.1f}" if r['props_pts'] > 0 else "-"
            xgb_str = f"{r['xgboost_pts']:.1f}" if r['xgboost_pts'] > 0 else "-"
            line = (
                f"{r['player'][:19]:<20} {r['team']:<5} {r['position']:<5} {sal_str:<8} "
                f"{r['ensemble_half']:<9.2f} {r['quant_half']:<7.2f} {xgb_str:<7} {prp_str:<7} "
                f"{r['xfp']:<7.2f} {r['fpoe']:<+7.2f} {r['value_pt_per_k']:<6.2f} {r['hvt_inside_5']:<6.2f}"
            )
            print(line)
    else:
        header = (
            f"{'Player':<20} {'Team':<5} {'Pos':<5} {'Salary':<8} "
            f"{'Half-PPR':<9} {'Full-PPR':<9} {'xFP':<7} {'FPOE':<7} {'Val/k':<6} {'HVT<5':<6} {'ZnTPRR':<7} {'SepScr':<7}"
        )
        print("\n" + header)
        print("-" * len(header))
        for r in top_results:
            sep_str = f"{r['separation_score']:.2f}" if r['separation_score'] is not None else "-"
            zn_str = f"{r['tprr_vs_zone']:.2f}" if r['tprr_vs_zone'] > 0 else "-"
            sal_str = f"${r['salary']:,}" if r['salary'] > 0 else "-"
            line = (
                f"{r['player'][:19]:<20} {r['team']:<5} {r['position']:<5} {sal_str:<8} "
                f"{r['half_ppr']:<9.2f} {r['full_ppr']:<9.2f} {r['xfp']:<7.2f} {r['fpoe']:<+7.2f} {r['value_pt_per_k']:<6.2f} "
                f"{r['hvt_inside_5']:<6.2f} {zn_str:<7} {sep_str:<7}"
            )
            print(line)

    # Print Percentile Table if requested
    if show_percentiles:
        print("\n" + "=" * 95)
        print("  GPP TOURNAMENT OUTCOME DISTRIBUTIONS (85th/95th CEILINGS & BOOM PROBABILITY)")
        print("=" * 95)
        pct_header = (
            f"{'Player':<20} {'Team':<5} {'Pos':<5} {'Salary':<8} "
            f"{'Floor(10th)':<12} {'Median(50th)':<13} {'Ceil(85th)':<12} {'Ceil(95th)':<12} {'Boom P(>25)':<12}"
        )
        print("\n" + pct_header)
        print("-" * len(pct_header))
        for r in top_results:
            sal_str = f"${r['salary']:,}" if r['salary'] > 0 else "-"
            boom_str = f"{r['boom_prob_25pt']*100:.1f}%"
            line = (
                f"{r['player'][:19]:<20} {r['team']:<5} {r['position']:<5} {sal_str:<8} "
                f"{r['floor_10th']:<12.1f} {r['median_50th']:<13.1f} {r['ceiling_85th']:<12.1f} {r['ceiling_95th']:<12.1f} {boom_str:<12}"
            )
            print(line)

    return results


def run_database_projections(
    week: int,
    mode: str,
    limit: int,
    source: str = "MODEL",
    use_ensemble: bool = False,
    show_percentiles: bool = False,
) -> list[dict[str, Any]]:
    """Run projections across all database players for the active NFL week."""
    resolved_source = "ENSEMBLE" if use_ensemble else source
    print(f"\n================================================================================")
    print(f"  QUANT PROJECTION ENGINE: 2026 NFL WEEK {week} (SOURCE: {resolved_source})")
    if use_ensemble:
        print(f"  [MODE: Institutional Inverse-Variance Ensemble Blend]")
    print(f"================================================================================")

    db = SessionLocal()
    try:
        players = db.query(PlayerModel).all()
        games = asyncio.run(nfl_schedule_client.fetch_week_schedule(season=2026, week=week))
        game_map = {g.home_team: g for g in games}
        game_map.update({g.away_team: g for g in games})

        results = []
        for p in players:
            if not p.position or p.position.upper() not in ("QB", "RB", "WR", "TE", "K", "D/ST", "DST"):
                continue

            nfl_game = game_map.get(p.pro_team.upper() if p.pro_team else "")
            
            # Full-PPR Evaluation
            eval_ppr = quant_projection_engine.calculate_player_projection(
                p,
                nfl_game=nfl_game,
                projection_source=resolved_source,
                scoring_format="PPR",
            )
            # Half-PPR Evaluation
            eval_half = quant_projection_engine.calculate_player_projection(
                p,
                nfl_game=nfl_game,
                projection_source=resolved_source,
                scoring_format="HALF_PPR",
            )

            p_ppr = eval_ppr.projected_points
            p_half = eval_half.projected_points
            delta = round(p_ppr - p_half, 2)

            # Filter out practice squad / zero-projection benchwarmers
            if p_ppr < 4.0 and p_half < 4.0:
                continue

            opp = nfl_game.get_opponent_for_team(p.pro_team.upper()) if nfl_game else "OPP"

            results.append({
                "player_id": p.id,
                "player": p.full_name,
                "team": p.pro_team or "FA",
                "position": p.position.upper(),
                "opponent": opp,
                "full_ppr": round(p_ppr, 2),
                "half_ppr": round(p_half, 2),
                "ensemble_half": eval_half.ensemble_half_ppr,
                "ensemble_full": eval_ppr.ensemble_full_ppr,
                "quant_half": eval_half.projected_half_ppr_points,
                "xgboost_pts": eval_half.xgboost_points,
                "props_pts": eval_half.props_points,
                "delta": delta,
                "hvt_inside_5": eval_half.hvt_inside_5 or 0.0,
                "hvt_inside_10": eval_half.hvt_inside_10 or 0.0,
                "xfp": eval_half.xfp,
                "fpoe": eval_half.fpoe,
                "floor_10th": eval_half.floor_10th,
                "median_50th": eval_half.median_50th,
                "ceiling_85th": eval_half.ceiling_85th,
                "ceiling_95th": eval_half.ceiling_95th,
                "boom_prob_25pt": eval_half.boom_probability_25pt,
                "bust_prob_6pt": eval_half.bust_probability_6pt,
                "tprr_vs_zone": eval_half.tprr_vs_zone,
            })

        # Sort based on mode
        if mode == "half-ppr":
            sort_key = "ensemble_half" if use_ensemble else "half_ppr"
            results.sort(key=lambda x: x[sort_key], reverse=True)
        else:
            sort_key = "ensemble_full" if use_ensemble else "full_ppr"
            results.sort(key=lambda x: x[sort_key], reverse=True)

        top_results = results[:limit]

        if use_ensemble:
            header = (
                f"{'Rank':<5} {'Player':<20} {'Team':<5} {'Pos':<5} {'Opp':<5} "
                f"{'Ensemble':<9} {'Quant':<7} {'XGB':<7} {'Props':<7} {'Delta':<7} {'HVT<5':<6} {'xFP':<6}"
            )
            print("\n" + header)
            print("-" * len(header))
            for idx, r in enumerate(top_results, 1):
                xgb_str = f"{r['xgboost_pts']:.1f}" if r['xgboost_pts'] > 0 else "-"
                prp_str = f"{r['props_pts']:.1f}" if r['props_pts'] > 0 else "-"
                line = (
                    f"{idx:<5} {r['player'][:19]:<20} {r['team']:<5} {r['position']:<5} {r['opponent']:<5} "
                    f"{r['ensemble_half']:<9.2f} {r['quant_half']:<7.2f} {xgb_str:<7} {prp_str:<7} "
                    f"{r['delta']:<+7.2f} {r['hvt_inside_5']:<6.2f} {r['xfp']:<6.2f}"
                )
                print(line)
        else:
            header = (
                f"{'Rank':<5} {'Player':<22} {'Team':<5} {'Pos':<5} {'Opp':<6} "
                f"{'Full-PPR':<10} {'Half-PPR':<10} {'Delta':<8} {'HVT<5':<7} {'HVT<10':<7} {'xFP':<7} {'FPOE':<7}"
            )
            print("\n" + header)
            print("-" * len(header))
            for idx, r in enumerate(top_results, 1):
                line = (
                    f"{idx:<5} {r['player'][:21]:<22} {r['team']:<5} {r['position']:<5} {r['opponent']:<6} "
                    f"{r['full_ppr']:<10.2f} {r['half_ppr']:<10.2f} {r['delta']:<+8.2f} "
                    f"{r['hvt_inside_5']:<7.2f} {r['hvt_inside_10']:<7.2f} {r['xfp']:<7.2f} {r['fpoe']:<+7.2f}"
                )
                print(line)

        if show_percentiles:
            print("\n" + "=" * 95)
            print("  GPP TOURNAMENT OUTCOME DISTRIBUTIONS (85th/95th CEILINGS & BOOM PROBABILITY)")
            print("=" * 95)
            pct_header = (
                f"{'Player':<20} {'Team':<5} {'Pos':<5} {'Opp':<5} "
                f"{'Floor(10th)':<12} {'Median(50th)':<13} {'Ceil(85th)':<12} {'Ceil(95th)':<12} {'Boom P(>25)':<12}"
            )
            print("\n" + pct_header)
            print("-" * len(pct_header))
            for r in top_results:
                boom_str = f"{r['boom_prob_25pt']*100:.1f}%"
                line = (
                    f"{r['player'][:19]:<20} {r['team']:<5} {r['position']:<5} {r['opponent']:<5} "
                    f"{r['floor_10th']:<12.1f} {r['median_50th']:<13.1f} {r['ceiling_85th']:<12.1f} {r['ceiling_95th']:<12.1f} {boom_str:<12}"
                )
                print(line)

        # Format Arbitrage Analysis
        print("\n" + "=" * 80)
        print("  FORMAT ARBITRAGE ANALYSIS: FULL-PPR SURGES VS. HALF-PPR STALWARTS")
        print("=" * 80)

        # Top PPR Gainers (Delta = PPR - Half)
        gainers = sorted(results, key=lambda x: x["delta"], reverse=True)[:5]
        print("\n[TOP FULL-PPR SURGES (Receptions drive outsized value in Season-Long ESPN)]")
        for g in gainers:
            print(
                f"  - {g['player']} ({g['team']} - {g['position']}): +{g['delta']:.2f} pts in Full-PPR "
                f"(PPR: {g['full_ppr']:.2f} | Half: {g['half_ppr']:.2f})"
            )

        return results
    finally:
        db.close()


def export_projections(results: list[dict[str, Any]], week: int) -> tuple[str, str]:
    """Export projections to both JSON and Parquet formats in data/."""
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"projections_week_{week}_2026.json"
    parquet_path = out_dir / f"projections_week_{week}_2026.parquet"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    try:
        import pandas as pd
        df = pd.DataFrame(results)
        df.to_parquet(parquet_path, index=False)
        print(f"[EXPORT] Successfully saved Parquet columnar projections: {parquet_path}")
    except Exception as e:
        print(f"[EXPORT] Note: parquet export skipped: {e}")

    print(f"[EXPORT] Successfully saved JSON projections: {json_path}")
    return str(json_path), str(parquet_path)


def main():
    parser = argparse.ArgumentParser(description="Generate Quant NFL Projections (PPR & Half-PPR)")
    parser.add_argument("--mode", choices=["ppr", "half-ppr", "both"], default="both", help="Scoring format mode")
    parser.add_argument("--week", type=int, default=5, help="NFL Regular Season Week")
    parser.add_argument("--limit", type=int, default=30, help="Number of top players to display")
    parser.add_argument("--source", default="MODEL", choices=["MODEL", "CONSENSUS", "FANTASYPROS", "ESPN", "ENSEMBLE"])
    parser.add_argument("--ensemble", action="store_true", help="Enable Institutional Inverse-Variance Ensemble Blend")
    parser.add_argument("--percentiles", action="store_true", help="Display GPP Tournament Outcome Percentiles")
    parser.add_argument("--slate-csv", type=str, default=None, help="Optional FanDuel slate CSV path")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON file path")
    parser.add_argument("--export", action="store_true", help="Export week projections to data/ in JSON & Parquet")

    args = parser.parse_args()

    if args.slate_csv:
        results = run_slate_projections(
            args.slate_csv,
            mode=args.mode,
            limit=args.limit,
            use_ensemble=args.ensemble,
            show_percentiles=args.percentiles,
        )
    else:
        results = run_database_projections(
            week=args.week,
            mode=args.mode,
            limit=args.limit,
            source=args.source,
            use_ensemble=args.ensemble,
            show_percentiles=args.percentiles,
        )

    if args.export:
        export_projections(results, week=args.week)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nProjections exported to {args.output}")


if __name__ == "__main__":
    main()
