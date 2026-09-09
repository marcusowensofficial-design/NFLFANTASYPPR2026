"""Script to execute mid-week ESPN and Sleeper data sync for Week 1 2026."""

import asyncio
import sys
sys.path.insert(0, ".")

from src.db.session import SessionLocal
from src.services.espn_sync import ESPNSyncService
from src.services.sleeper_sync import sleeper_sync_service


async def main():
    db = SessionLocal()
    print("Starting ESPN League sync for Week 1 2026...")
    sync_service = ESPNSyncService(db=db)
    success, message, league = await sync_service.sync(force=True)
    print(f"ESPN Sync Result: Success={success}, Message='{message}', League='{league.name if league else 'None'}'")

    print("\nStarting Sleeper Projections sync (Season 2026, Week 1)...")
    sleeper_res = await sleeper_sync_service.sync_sleeper_projections(season=2026, week=1)
    print(f"Sleeper Sync Result: Success={sleeper_res['success']}, Enriched={sleeper_res['enriched_count']} players")


if __name__ == "__main__":
    asyncio.run(main())
