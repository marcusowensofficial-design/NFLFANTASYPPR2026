"""CLI Executable for World-Class NFL Betting & Pre-Flight Forensic Auditor.

Usage:
    python scripts/audit_game_for_betting.py --away PIT --home CLE --csv data/PITVSCLESINGLEGAMESLATE10-01-26.csv
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.services.intelligence.world_class_betting_auditor import world_class_auditor


def main():
    parser = argparse.ArgumentParser(description="World-Class NFL Betting & Pre-Flight Forensic Auditor")
    parser.add_argument("--away", type=str, required=True, help="Away team abbreviation (e.g. PIT)")
    parser.add_argument("--home", type=str, required=True, help="Home team abbreviation (e.g. CLE)")
    parser.add_argument("--csv", type=str, default=None, help="Optional FanDuel slate CSV path")

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print(f"  QUANTITATIVE NFL BETTING & PRE-FLIGHT AUDITOR: {args.away.upper()} @ {args.home.upper()}")
    print("=" * 80)

    report = asyncio.run(world_class_auditor.audit_matchup(args.away, args.home, slate_csv_path=args.csv))

    print(f"\n[1] VEGAS MARKET BLUEPRINT:")
    print(f"  Spread:           {args.home.upper()} {report.spread:+} (Implied: {args.away.upper()} {report.away_implied_total} - {args.home.upper()} {report.home_implied_total})")
    print(f"  Over/Under:       {report.over_under}")
    print(f"  Market Velocity:  {report.market_velocity.steam_classification}")
    print(f"  Steam Notes:      {report.market_velocity.notes}")

    print(f"\n[2] STADIUM AERODYNAMICS & REAL-TIME WEATHER:")
    print(f"  Venue:            {report.weather.venue} ({'Dome / Climate-Controlled' if report.weather.is_dome else 'Open-Air Waterfront / Field'})")
    print(f"  Condition:        {report.weather.weather_classification}")
    print(f"  Metrics:          {report.weather.notes}")
    print(f"  Passing Impact:   -{report.weather.passing_suppression_pct}% suppression on deep aDOT")
    print(f"  Kicking Impact:   -{report.weather.field_goal_suppression_pct}% suppression on 42+ yd field goals")

    print(f"\n[3] TRENCH COLLISION & OL STARTER INTEGRITY:")
    print(f"  {report.away_team} OL Pass Block: {report.away_trench.ol_pass_block_grade} | Starting Tackles Intact: {report.away_trench.starting_tackles_intact}")
    if report.away_trench.injured_ol_starters:
        print(f"    ⚠️ Injured Starters: {', '.join(report.away_trench.injured_ol_starters)}")
    if report.away_trench.notes:
        print(f"    🚨 {report.away_trench.notes}")

    print(f"  {report.home_team} OL Pass Block: {report.home_trench.ol_pass_block_grade} | Starting Tackles Intact: {report.home_trench.starting_tackles_intact}")
    if report.home_trench.injured_ol_starters:
        print(f"    ⚠️ Injured Starters: {', '.join(report.home_trench.injured_ol_starters)}")
    if report.home_trench.notes:
        print(f"    🚨 {report.home_trench.notes}")

    print(f"\n[4] SPECIALIST ROSTER & SLATE INTEGRITY:")
    print(f"  {report.away_team} Kicker: {report.away_specialist.active_kicker_name} (FG Rate: {report.away_specialist.kicker_fg_pct_2026}% | Multiplier: {report.away_specialist.coach_kicker_multiplier}x)")
    if report.away_specialist.warning:
        print(f"    🚨 {report.away_specialist.warning}")
    print(f"  {report.home_team} Kicker: {report.home_specialist.active_kicker_name} (FG Rate: {report.home_specialist.kicker_fg_pct_2026}% | Multiplier: {report.home_specialist.coach_kicker_multiplier}x)")
    if report.home_specialist.warning:
        print(f"    🚨 {report.home_specialist.warning}")

    print(f"\n[5] STANFORD WONG TEASER MATHEMATICAL SCREENER:")
    for t in report.wong_teasers:
        status_tag = "✅ QUALIFIED WONG TEASER" if t.is_wong_teaser else "❌ INELIGIBLE"
        print(f"  {t.team}: Teased from {t.original_line:+} to {t.teased_line:+} | Crosses 3 & 7: {t.crosses_3_and_7} | {status_tag} (Hist Win Rate: {t.historical_cover_probability}%)")

    print(f"\n[6] FIRST HALF DERIVATIVE PROJECTION:")
    print(f"  1H Total:         {report.first_half_projection.get('first_half_total_line')}")
    print(f"  1H Under Prob:    {report.first_half_projection.get('first_half_under_probability')}%")
    print(f"  1H Rationale:     {report.first_half_projection.get('rationale')}")

    if report.critical_alerts:
        print(f"\n🚨 CRITICAL PRE-FLIGHT ALERTS ({len(report.critical_alerts)}):")
        for alert in report.critical_alerts:
            print(f"  * {alert}")

    print(f"\n🎯 SHARP SYNDICATE BETTING CARD & DIRECTIVES:")
    print(f"  Primary Spread:   {report.sharp_betting_verdict.get('primary_spread_lean')}")
    print(f"  Primary Total:    {report.sharp_betting_verdict.get('primary_total_lean')}")
    print(f"  Structured Play:  {report.sharp_betting_verdict.get('highest_ev_structured_play')}")
    print(f"  Correlated Props: {', '.join(report.sharp_betting_verdict.get('key_props_edge', []))}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
