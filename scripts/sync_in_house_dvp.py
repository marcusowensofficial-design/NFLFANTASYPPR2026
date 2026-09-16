"""Synchronizes in-house calculated DvP and Fantasy Points Allowed to database and cache."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_DIR))

from src.services.matchup.dvp_service import dvp_service


async def main():
    parser = argparse.ArgumentParser(description="Calculate and sync in-house DvP ratings to database.")
    parser.add_argument("--week", type=int, default=2, help="Current regular season week to calculate (default: 2)")
    parser.add_argument("--season", type=int, default=2026, help="NFL Season year (default: 2026)")
    args = parser.parse_args()

    print(f"🔄 Calculating In-House First-Party DvP & FPA for Season {args.season}, Week {args.week}...")
    res = await dvp_service.sync_dvp_data(season=args.season, week=args.week)
    print(f"✅ Sync Complete! Total records updated: {res['total_records']}")

    # Print summary top smash matchups
    print("\n" + "=" * 80)
    print("🏆 TOP IN-HOUSE SMASH MATCHUPS PER POSITION (Week 2):")
    print("=" * 80)
    for pos in ["QB", "RB", "WR", "TE"]:
        ratings = dvp_service.get_dvp_ratings(season=args.season, week=args.week, position=pos)
        print(f"\n[{pos}] Top 3 Softest Matchups:")
        for r in ratings[:3]:
            print(
                f"   #{r['rank_softness']} {r['pro_team']} ({r['team_name']}): "
                f"{r['dk_fpa']:.1f} Half-PPR (FanDuel) | {r['fd_fpa']:.1f} Full-PPR (ESPN) "
                f"({r['vs_avg']:+.1f} vs avg) — {r['tier_label']}"
            )
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
