"""Synchronize DraftEdge Week 2 2026 Defense vs Position data across database, seed, and in-memory client."""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.nfl.draftedge_client import draftedge_client
from src.services.matchup.dvp_service import dvp_service
from src.adapters.nfl.dvp_client import dvp_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Step 1: Fetching live DraftEdge data for all 4 positions (QB, RB, WR, TE)...")
    all_data = await draftedge_client.fetch_all_positions()

    for pos, items in all_data.items():
        logger.info("Position %s: scraped %d teams", pos, len(items))
        car_item = next((x for x in items if x["pro_team"] == "CAR"), None)
        jax_item = next((x for x in items if x["pro_team"] == "JAX"), None)
        if car_item:
            logger.info("  CAR %s: rank_defense=%s, rank_softness=%s, tier=%s, 2026_fpa=%s",
                        pos, car_item["rank_defense"], car_item["rank_softness"], car_item["tier"], car_item.get("current_season_fpa"))
        if jax_item:
            logger.info("  JAX %s: rank_defense=%s, rank_softness=%s, tier=%s, 2026_fpa=%s",
                        pos, jax_item["rank_defense"], jax_item["rank_softness"], jax_item["tier"], jax_item.get("current_season_fpa"))

    # Overwrite seed file
    seed_path = Path(__file__).resolve().parent.parent / "data" / "draftedge_dvp_seed.json"
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)
    logger.info("Step 2: Saved updated seed file to %s", seed_path)

    # Sync to database for Week 2
    logger.info("Step 3: Syncing Week 2 to database...")
    res_w2 = await dvp_service.sync_dvp_data(season=2026, week=2)
    logger.info("Week 2 sync result: %s", res_w2)

    # Sync to database for Week 1 (so any queries for week 1 baseline are also clean)
    logger.info("Step 4: Syncing Week 1 baseline to database...")
    res_w1 = await dvp_service.sync_dvp_data(season=2026, week=1)
    logger.info("Week 1 sync result: %s", res_w1)

    # Test in-memory hydration
    logger.info("Step 5: Testing in-memory hydration...")
    dvp_client.hydrate_from_db(season=2026, week=2)
    car_rb = dvp_client.get_position_rank("CAR", "RB")
    jax_rb = dvp_client.get_position_rank("JAX", "RB")
    logger.info("dvp_client CAR RB rank: %s (expected 32)", car_rb)
    logger.info("dvp_client JAX RB rank: %s (expected 1)", jax_rb)
    assert car_rb == 32, f"Expected CAR RB rank 32, got {car_rb}"
    assert jax_rb == 1, f"Expected JAX RB rank 1, got {jax_rb}"

    logger.info("All DraftEdge Week 2 sync verifications PASSED successfully!")

if __name__ == "__main__":
    asyncio.run(main())
