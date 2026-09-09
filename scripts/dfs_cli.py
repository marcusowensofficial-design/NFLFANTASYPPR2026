#!/usr/bin/env python3
"""Interactive Command-Line Interface for FanDuel Daily Fantasy Sports (DFS).

Usage examples:
  python scripts/dfs_cli.py --lineup single-entry
  python scripts/dfs_cli.py --lineup cash
  python scripts/dfs_cli.py --rbs
  python scripts/dfs_cli.py --wrs
  python scripts/dfs_cli.py --stacks
  python scripts/dfs_cli.py --ownership
  python scripts/dfs_cli.py --leverage
  python scripts/dfs_cli.py --audit
"""

import argparse
import asyncio
import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.abspath("."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.dfs.engine import dfs_engine


def render_banner(text: str) -> None:
    line = "=" * 96
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}\n")


def print_lineup_table(result: dict) -> None:
    if not result or "roster" not in result:
        print("No feasible lineup generated.")
        return

    mode = result.get("mode", "GPP")
    render_banner(f"FANDUEL CHAMPIONSHIP LINEUP ({mode.replace('_', ' ')})")

    print(f"{'Slot':<10} | {'Player Name':<22} | {'Team':<4} vs {'Opp':<4} | {'Salary':<6} | {'Median':<6} | {'Ceiling':<7} | {'Own%':<6} | {'Leverage':<8} | {'DvP Soft':<8}")
    print("-" * 104)

    for item in result["roster"]:
        slot = item["slot"]
        name = item["name"]
        team = item["team"]
        opp = item["opponent"]
        sal = f"${item['salary']:,}"
        proj = f"{item['proj']:.2f}"
        ceil = f"{item.get('ceiling', round(item['proj'] * 1.4, 2)):.2f}"
        own = f"{item.get('proj_ownership', 10.0):.1f}%"
        lev = f"{item.get('leverage_score', 1.0):.2f}"
        imp = f"{item['team_implied']:.1f}"
        soft = f"#{item['opp_soft_rank']}"
        print(f"{slot:<10} | {name:<22} | {team:<4} vs {opp:<4} | {sal:<6} | {proj:<6} | {ceil:<7} | {own:<6} | {lev:<8} | {soft:<8}")

    print("-" * 104)
    tot_sal = result["total_salary"]
    rem_sal = result["salary_remaining"]
    tot_proj = result["total_projected_points"]
    tot_ceil = result.get("total_ceiling_points", round(tot_proj * 1.4, 2))
    full_ppr = result["full_ppr_projected_points"]
    val_mult = result["value_multiplier"]
    cum_own = result.get("cumulative_ownership", 120.0)
    own_assess = result.get("ownership_assessment", "")

    print(f"  Total Salary Spent:        ${tot_sal:,} / $60,000  (Remaining: ${rem_sal:,})")
    print(f"  Half-PPR Median Pts:       {tot_proj:.2f} pts  (Value Multiplier: {val_mult:.2f}x)")
    print(f"  90th Percentile Ceiling:   {tot_ceil:.2f} pts  (Tournament Winning Upside)")
    print(f"  Full-PPR Projected Pts:    {full_ppr:.2f} pts  (+17.5 pt reception boost)")
    print(f"  Cumulative Ownership:      {cum_own:.1f}%")
    if own_assess:
        print(f"  Tournament Assessment:     {own_assess}")
    print("=" * 104 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="FanDuel NFL DFS Optimizer & Intelligence System (2026 Season)"
    )
    parser.add_argument(
        "--lineup",
        choices=["single-entry", "cash"],
        help="Generate an optimal lineup (single-entry GPP or cash game)",
    )
    parser.add_argument(
        "--rbs",
        action="store_true",
        help="Show top running backs ranked by salary efficiency and DvP softness",
    )
    parser.add_argument(
        "--wrs",
        action="store_true",
        help="Show top wide receivers ranked by salary efficiency and DvP softness",
    )
    parser.add_argument(
        "--stacks",
        action="store_true",
        help="Show top QB + Pass Catcher + Opposing Bring-Back game stacks",
    )
    parser.add_argument(
        "--ownership",
        action="store_true",
        help="Show projected ownership leaders across the entire slate",
    )
    parser.add_argument(
        "--leverage",
        action="store_true",
        help="Show top tournament leverage targets (high ceiling, low ownership)",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Run live forensic audit on stadium weather and injuries for the top lineup",
    )
    parser.add_argument(
        "--set-ownership",
        nargs=2,
        metavar=("PLAYER_NAME", "OWNERSHIP_PCT"),
        help="Update or override projected ownership for a player (e.g. --set-ownership 'Omarion Hampton' 28.0)",
    )
    parser.add_argument(
        "--import-ownership",
        metavar="CSV_FILE",
        help="Import external ownership projections from a CSV file (e.g. Daily Fantasy Fuel, Footballguys, ETR)",
    )
    parser.add_argument(
        "--reset-ownership",
        action="store_true",
        help="Reset all manual and imported ownership overrides back to baseline simulation",
    )
    parser.add_argument(
        "--csv",
        metavar="CSV_PATH",
        help="Path to a custom player list CSV (e.g. --csv src/dfs/earlyonlysalariesandrosters.csv)",
    )
    parser.add_argument(
        "--show-overrides",
        action="store_true",
        help="Display all currently active manual/external ownership overrides",
    )

    args = parser.parse_args()

    from src.dfs.ownership import dfs_ownership

    if args.set_ownership:
        name, pct = args.set_ownership
        try:
            val = float(pct)
            dfs_ownership.set_override(name, val)
            print(f"\n[SUCCESS] Updated ownership override for '{name}' to {val:.1f}%.")
            print("Run 'python scripts/dfs_cli.py --lineup single-entry' or '--ownership' to solve with updated ownership.\n")
        except ValueError:
            print(f"[ERROR] Invalid ownership value: '{pct}'. Must be a valid number.")
        return

    if args.import_ownership:
        csv_path = args.import_ownership
        if not os.path.exists(csv_path):
            print(f"[ERROR] File not found: '{csv_path}'")
            return
        try:
            count = dfs_ownership.import_overrides_csv(csv_path)
            print(f"\n[SUCCESS] Successfully imported {count} player ownership projections from '{csv_path}'.")
            print("Run 'python scripts/dfs_cli.py --lineup single-entry' or '--ownership' to view.\n")
        except Exception as e:
            print(f"[ERROR] Failed to import CSV: {e}")
        return

    if args.reset_ownership:
        dfs_ownership.reset_overrides()
        print("\n[SUCCESS] Cleared all ownership overrides. Reverted to algorithmic baseline.\n")
        return

    if args.show_overrides:
        overrides = dfs_ownership.load_overrides()
        render_banner("ACTIVE OWNERSHIP OVERRIDES")
        if not overrides:
            print("  No active overrides. Running on algorithmic baseline simulation.")
        else:
            for p, val in sorted(overrides.items()):
                print(f"  {p:<25} : {val:.1f}%")
        print("=" * 96 + "\n")
        return

    # Default to single-entry if no arguments provided
    if not (args.lineup or args.rbs or args.wrs or args.stacks or args.ownership or args.leverage or args.audit):
        args.lineup = "single-entry"

    if args.lineup == "single-entry":
        print("\nSolving optimal Single-Entry GPP Lineup (Game Stack + Opposing Bring-Back)...")
        lineup = await dfs_engine.build_single_entry_lineup(csv_path=args.csv)
        print_lineup_table(lineup)

    elif args.lineup == "cash":
        print("\nSolving optimal Cash Game Lineup (Floor Maximization)...")
        lineup = await dfs_engine.build_cash_lineup(csv_path=args.csv)
        print_lineup_table(lineup)

    if args.rbs:
        render_banner("TOP RUNNING BACKS (RANKED BY PROJECTION & VALUE)")
        df_rbs = await dfs_engine.get_top_running_backs(csv_path=args.csv, min_salary=4800, top_n=15)
        print(df_rbs[["name", "team", "opponent", "salary", "proj", "value_ratio", "proj_ownership", "leverage_score", "opp_soft_rank"]].to_string(index=False))

    if args.wrs:
        render_banner("TOP WIDE RECEIVERS (RANKED BY PROJECTION & VALUE)")
        df_wrs = await dfs_engine.get_top_wide_receivers(csv_path=args.csv, min_salary=4800, top_n=15)
        print(df_wrs[["name", "team", "opponent", "salary", "proj", "value_ratio", "proj_ownership", "leverage_score", "opp_soft_rank"]].to_string(index=False))

    if args.stacks:
        render_banner("TOP TOURNAMENT GAME STACKS (QB + PRIMARY TARGET + BRING-BACK)")
        stacks = await dfs_engine.get_top_game_stacks(csv_path=args.csv, top_n=6)
        for i, s in enumerate(stacks, 1):
            print(f"Stack #{i}: {s['game']} (Game O/U: {s['game_ou']})")
            print(f"  QB:         {s['qb']}")
            print(f"  Target:     {s['target']}")
            print(f"  Bring-Back: {s['bring_back']}")
            print(f"  Total Cost: ${s['total_salary']:,} | Proj: {s['total_proj']} pts | Value: {s['avg_value']}x\n")

    if args.ownership:
        render_banner("PROJECTED OWNERSHIP LEADERS (MEGA-CHALK & POPULAR PLAYS)")
        df_chalk = await dfs_engine.get_top_chalk(csv_path=args.csv, top_n=15)
        print(df_chalk[["name", "position", "team", "opponent", "salary", "proj", "proj_ownership", "ownership_tier", "leverage_score"]].to_string(index=False))

    if args.leverage:
        render_banner("TOP TOURNAMENT LEVERAGE TARGETS (LOW OWNERSHIP, HIGH CEILING)")
        df_lev = await dfs_engine.get_top_leverage(csv_path=args.csv, top_n=15)
        print(df_lev[["name", "position", "team", "opponent", "salary", "proj", "proj_ownership", "leverage_score", "team_implied"]].to_string(index=False))

    if args.audit:
        lineup = await dfs_engine.build_single_entry_lineup(csv_path=args.csv)
        if lineup and "roster" in lineup:
            render_banner("PRE-LOCK LIVE FORENSIC AUDIT (WEATHER & INJURIES)")
            audit_data = await dfs_engine.audit_roster(lineup["roster"])
            print("--- STADIUM WEATHER ---")
            for w in audit_data["weather"]:
                dome_str = "DOME" if w["is_dome"] else f"{w['temp']}°F, Wind {w['wind_mph']} mph (Gusts {w['gusts_mph']})"
                print(f"  {w['team']:<4} | {dome_str:<35} | Concern: {w['concern'] or 'None'}")
            print("\n--- INJURY ALERTS ---")
            if audit_data["injury_alerts"]:
                for a in audit_data["injury_alerts"]:
                    print(f"  {a['player']:<22} | Status: {a['status']} | Practice: {a['practice'] or 'Unknown'}")
                    print(f"    Headline: {a['headline']}\n")
            else:
                print("  All rostered players are fully active with no critical injury designations.")


if __name__ == "__main__":
    asyncio.run(main())
