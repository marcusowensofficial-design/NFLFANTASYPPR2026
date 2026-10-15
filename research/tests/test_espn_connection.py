#!/usr/bin/env python3
"""CLI diagnostic tool to test and verify connection to an ESPN Fantasy Football league."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.espn.client import ESPNClient
from src.adapters.espn.schemas import ESPNLeagueResponse, LeagueSummary, TeamSummary
from src.core.config import settings


def mask_secret(val: str | None) -> str:
    if not val:
        return "<Not Provided>"
    if len(val) <= 8:
        return "***"
    return f"{val[:4]}...{val[-4:]} (Length: {len(val)})"


def print_banner() -> None:
    print("=" * 70)
    print("   ESPN FANTASY FOOTBALL 2026 - CONNECTION & DIAGNOSTIC TEST")
    print("=" * 70)


def print_league_summary(summary: LeagueSummary) -> None:
    print("\n" + "-" * 70)
    print(f" LEAGUE: {summary.name.upper()} (ID: {summary.league_id})")
    print("-" * 70)
    print(f"  Season:           {summary.season}")
    print(f"  Current Week:     Week {summary.current_week}")
    print(f"  Teams:            {summary.size}")
    print(f"  Scoring Format:   {'Full PPR' if summary.reception_points == 1.0 else f'{summary.reception_points} PPR'}")
    print("  Roster Settings:  " + ", ".join(f"{k}: {v}" for k, v in summary.roster_slots.items() if v > 0))
    print("\n TEAMS IN LEAGUE:")
    print(f"  {'#':<3} {'Team Name':<28} {'Abbrev':<8} {'Owner':<18} {'Record':<8} {'Roster'}")
    print("  " + "-" * 66)
    for i, t in enumerate(summary.teams, 1):
        owner_str = t.owner or "N/A"
        roster_str = f"{t.starter_count} Starters, {t.bench_count} Bench"
        print(f"  {i:<3} {t.name[:27]:<28} {t.abbrev:<8} {owner_str[:17]:<18} {t.record:<8} {roster_str}")
    print("-" * 70)


async def run_mock_test() -> None:
    print("\n[INFO] Running in --mock mode using local 2026 8-team PPR fixture...\n")
    mock_file = PROJECT_ROOT / "tests" / "fixtures" / "mock_espn_league.json"
    if not mock_file.exists():
        print(f"[ERROR] Mock fixture not found at {mock_file}")
        sys.exit(1)

    with open(mock_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    league = ESPNLeagueResponse.model_validate(data)
    settings_obj = league.settings
    roster_settings = settings_obj.roster_settings if settings_obj else None
    scoring_settings = settings_obj.scoring_settings if settings_obj else None

    slot_counts = roster_settings.parsed_slot_counts if roster_settings else {}
    is_ppr = scoring_settings.is_ppr if scoring_settings else True
    rec_pts = scoring_settings.reception_points if scoring_settings else 1.0

    teams: list[TeamSummary] = []
    for t in league.teams:
        record_str = "0-0"
        pf = 0.0
        if t.record and t.record.overall:
            record_str = f"{t.record.overall.wins}-{t.record.overall.losses}"
            pf = round(t.record.overall.points_for, 1)

        starters = 0
        bench = 0
        if t.roster and t.roster.entries:
            for e in t.roster.entries:
                if e.lineup_slot_id == 20:
                    bench += 1
                elif e.lineup_slot_id != 21:
                    starters += 1

        teams.append(
            TeamSummary(
                id=t.id,
                name=t.full_name,
                abbrev=t.abbrev,
                owner=t.primary_owner,
                record=record_str,
                points_for=pf,
                starter_count=starters,
                bench_count=bench,
            )
        )

    summary = LeagueSummary(
        league_id=league.id,
        season=league.season_id,
        name=settings_obj.name if settings_obj else "Mock League",
        size=settings_obj.size if settings_obj else len(teams),
        current_week=league.scoring_period_id,
        is_ppr=is_ppr,
        reception_points=rec_pts,
        roster_slots=slot_counts,
        teams=teams,
    )

    print("[SUCCESS] Mock data loaded and validated successfully against Pydantic schemas!")
    print_league_summary(summary)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test connection to ESPN Fantasy Football League.")
    parser.add_argument("--league-id", type=int, help="ESPN League ID (overrides .env)")
    parser.add_argument("--season", type=int, default=2026, help="Season year (default: 2026)")
    parser.add_argument("--swid", type=str, help="ESPN SWID cookie (overrides .env)")
    parser.add_argument("--espn-s2", type=str, help="ESPN espn_s2 cookie (overrides .env)")
    parser.add_argument("--mock", action="store_true", help="Run test against local mock data fixture")

    args = parser.parse_args()
    print_banner()

    if args.mock:
        await run_mock_test()
        return

    league_id = args.league_id or settings.espn_league_id
    season = args.season or settings.espn_season
    swid = args.swid or settings.espn_swid
    espn_s2 = args.espn_s2 or settings.espn_s2

    print(f"Target Season:   {season}")
    print(f"League ID:       {league_id if league_id else '<NOT SET>'}")
    print(f"SWID Cookie:     {mask_secret(swid)}")
    print(f"ESPN_S2 Cookie:  {mask_secret(espn_s2)}")
    print("-" * 70)

    if not league_id:
        print("\n[ATTENTION] No ESPN League ID was provided.")
        print("Please configure ESPN_LEAGUE_ID in your .env file, or pass --league-id <ID>.")
        print("\nTip: To test the parser with sample data immediately, run:")
        print("     python scripts/test_espn_connection.py --mock\n")
        sys.exit(1)

    print(f"\n[INFO] Connecting to ESPN API for League #{league_id} (Season {season})...")

    client = ESPNClient(
        league_id=league_id,
        season=season,
        swid=swid,
        espn_s2=espn_s2,
    )

    success, message, summary = await client.test_connection()

    if success and summary:
        print(f"\n[SUCCESS] {message}")
        print_league_summary(summary)
        print("\n[STATUS] Connection verified! Your ESPN league is ready for Phase 2.")
    else:
        print(f"\n[FAILED] {message}\n")
        if "UNAUTHORIZED" in message:
            print("=" * 70)
            print(" PRIVATE LEAGUE AUTHENTICATION GUIDE")
            print("=" * 70)
            print("Your league is PRIVATE. ESPN requires session cookies from your browser:")
            print("\n1. Open Chrome/Edge/Firefox and log in to https://fantasy.espn.com")
            print("2. Navigate to your 2026 fantasy league page.")
            print("3. Press F12 to open Developer Tools.")
            print("4. Go to Application tab (Chrome/Edge) or Storage tab (Firefox).")
            print("5. Under 'Cookies', select 'https://espn.com' or 'https://fantasy.espn.com'.")
            print("6. Locate and copy the values for:")
            print("   - SWID: (format looks like {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX})")
            print("   - espn_s2: (long alphanumeric token ~200+ characters)")
            print("7. Add them to your local .env file:")
            print("   ESPN_SWID={YOUR-SWID-VALUE}")
            print("   ESPN_S2=YOUR-LONG-ESPN-S2-VALUE")
            print("8. Re-run this script.")
            print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
