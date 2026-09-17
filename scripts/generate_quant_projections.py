"""Generate Quant Projections for 2026 NFL Season.

Supports Full-PPR (ESPN Season-Long) and Half-PPR (FanDuel DFS) decoupled engines,
incorporating Next Gen Stats micro-metrics (Separation Score, First Read %, Regression Index)
and Trench Pass-Protection Collision Multipliers.
"""

import argparse
import json
import os
import sys
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
from src.services.recommendation.scoring_engine import scoring_engine
import asyncio
from src.dfs.loader import dfs_loader


def run_slate_projections(csv_path: str, mode: str, limit: int) -> list[dict[str, Any]]:
    """Run projections on a FanDuel slate CSV with dual-engine comparison."""
    print(f"\n================================================================================")
    print(f"  FANDUEL DFS SLATE PROJECTION ENGINE: {os.path.basename(csv_path)}")
    print(f"================================================================================")
    
    df = asyncio.run(dfs_loader.load_slate(csv_path))
    results = []

    db = SessionLocal()
    try:
        for _, row in df.iterrows():
            p_name = row.get("name") or row.get("Player", "Unknown")
            team = str(row.get("team") or row.get("Team", ""))
            pos = str(row.get("position") or row.get("Position", ""))
            salary = int(row.get("salary") or row.get("Salary", 0))
            half_pts = float(row.get("proj") or row.get("Projection", 0.0))
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
                    projection_source="MODEL",
                )
                full_pts = ppr_res.projected_points
                half_pts = ppr_res.projected_half_ppr_points
            else:
                temp_player = PlayerModel(
                    id=int(row.get("Id", 0)) if str(row.get("Id", "")).isdigit() else 9999,
                    full_name=p_name,
                    position=pos,
                    pro_team=team,
                    projected_points=half_pts,
                )
                ppr_res = quant_projection_engine.calculate_player_projection(
                    temp_player,
                    scoring_format="PPR",
                    projection_source="MODEL",
                )
                full_pts = ppr_res.projected_points
                half_pts = ppr_res.projected_half_ppr_points

            delta = round(full_pts - half_pts, 2)
            val_rating = round((half_pts / max(salary, 1)) * 1000, 2)

            results.append({
                "player": p_name,
                "team": team,
                "position": pos,
                "salary": salary,
                "half_ppr": round(half_pts, 2),
                "full_ppr": round(full_pts, 2),
                "delta": delta,
                "value_pt_per_k": val_rating,
                "milestone_bonus": bonus,
                "hvt_inside_5": ppr_res.hvt_inside_5,
                "hvt_inside_10": ppr_res.hvt_inside_10,
                "xfp": ppr_res.xfp,
                "fpoe": ppr_res.fpoe,
                "tprr_vs_zone": ppr_res.tprr_vs_zone,
                "inside_5_carry_share": ppr_res.inside_5_carry_share,
                "scramble_rate": ppr_res.scramble_rate_pressured,
                "p2s_rate": ppr_res.p2s_rate,
                "scheme_note": ppr_res.coverage_scheme_note,
                "separation_score": sep_score if sep_score is not None and not (isinstance(sep_score, float) and sep_score != sep_score) else None,
                "first_read_pct": first_read if first_read is not None and not (isinstance(first_read, float) and first_read != first_read) else None,
                "regression_index": reg_idx if reg_idx is not None and not (isinstance(reg_idx, float) and reg_idx != reg_idx) else None,
            })
    finally:
        db.close()

    # Sort by half_ppr desc
    results.sort(key=lambda x: x["half_ppr"], reverse=True)
    top_results = results[:limit]

    # Print Table
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

    return results


def run_database_projections(week: int, mode: str, limit: int, source: str) -> list[dict[str, Any]]:
    """Run projections across all database players for the active NFL week."""
    print(f"\n================================================================================")
    print(f"  QUANT PROJECTION ENGINE: 2026 NFL WEEK {week} (SOURCE: {source})")
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
            eval_ppr = scoring_engine.evaluate_player(
                p,
                nfl_game=nfl_game,
                projection_source=source,
                scoring_format="PPR",
            )
            # Half-PPR Evaluation
            eval_half = scoring_engine.evaluate_player(
                p,
                nfl_game=nfl_game,
                projection_source=source,
                scoring_format="HALF_PPR",
            )

            p_ppr = eval_ppr.projected_points
            p_half = eval_half.projected_points
            delta = round(p_ppr - p_half, 2)

            # Filter out practice squad / zero-projection benchwarmers
            if p_ppr < 4.0 and p_half < 4.0:
                continue

            results.append({
                "player_id": p.id,
                "player": p.full_name,
                "team": p.pro_team or "FA",
                "position": p.position.upper(),
                "opponent": eval_ppr.opponent,
                "full_ppr": round(p_ppr, 2),
                "half_ppr": round(p_half, 2),
                "delta": delta,
                "hvt_inside_5": eval_ppr.hvt_inside_5 or 0.0,
                "hvt_inside_10": eval_ppr.hvt_inside_10 or 0.0,
                "separation_score": eval_ppr.separation_score,
                "first_read_pct": eval_ppr.first_read_pct,
                "regression_index": eval_ppr.regression_index,
                "tprr": eval_ppr.tprr,
                "reasons": eval_ppr.reasons_positive[:3],
            })

        # Sort based on mode
        if mode == "half-ppr":
            results.sort(key=lambda x: x["half_ppr"], reverse=True)
        else:
            results.sort(key=lambda x: x["full_ppr"], reverse=True)

        top_results = results[:limit]

        header = (
            f"{'Rank':<5} {'Player':<22} {'Team':<5} {'Pos':<5} {'Opp':<6} "
            f"{'Full-PPR':<10} {'Half-PPR':<10} {'Delta':<8} {'HVT<5':<7} {'HVT<10':<7} {'SepScr':<8} {'RegIdx':<8}"
        )
        print("\n" + header)
        print("-" * len(header))
        for idx, r in enumerate(top_results, 1):
            sep_str = f"{r['separation_score']:.2f}" if r['separation_score'] is not None else "-"
            reg_str = f"{r['regression_index']:.2f}" if r['regression_index'] is not None else "-"
            line = (
                f"{idx:<5} {r['player'][:21]:<22} {r['team']:<5} {r['position']:<5} {r['opponent']:<6} "
                f"{r['full_ppr']:<10.2f} {r['half_ppr']:<10.2f} {r['delta']:<+8.2f} "
                f"{r['hvt_inside_5']:<7.2f} {r['hvt_inside_10']:<7.2f} {sep_str:<8} {reg_str:<8}"
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

        # Coiled Spring Regression Candidates (High separation/TPRR but depressed box score)
        coiled = [r for r in results if r["regression_index"] and r["regression_index"] >= 0.75]
        coiled = sorted(coiled, key=lambda x: x["regression_index"] or 0, reverse=True)[:5]
        if coiled:
            print("\n[NEXT GEN STATS COILED-SPRING CANDIDATES (High Separation & First-Read %)]")
            for c in coiled:
                sep = f"{c['separation_score']:.2f}" if c['separation_score'] is not None else "N/A"
                print(
                    f"  - {c['player']} ({c['team']} - {c['position']}): Regression Index {c['regression_index']:.2f} "
                    f"| Separation Score: {sep} | Proj: {c['full_ppr']:.2f} PPR"
                )

        return results
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Generate Quant NFL Projections (PPR & Half-PPR)")
    parser.add_argument("--mode", choices=["ppr", "half-ppr", "both"], default="both", help="Scoring format mode")
    parser.add_argument("--week", type=int, default=2, help="NFL Regular Season Week")
    parser.add_argument("--limit", type=int, default=30, help="Number of top players to display")
    parser.add_argument("--source", default="MODEL", choices=["MODEL", "CONSENSUS", "FANTASYPROS", "ESPN"])
    parser.add_argument("--slate-csv", type=str, default=None, help="Optional FanDuel slate CSV path")
    parser.add_argument("--output", type=str, default=None, help="Optional output JSON file path")

    args = parser.parse_args()

    if args.slate_csv:
        results = run_slate_projections(args.slate_csv, mode=args.mode, limit=args.limit)
    else:
        results = run_database_projections(week=args.week, mode=args.mode, limit=args.limit, source=args.source)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nProjections exported to {args.output}")


if __name__ == "__main__":
    main()
