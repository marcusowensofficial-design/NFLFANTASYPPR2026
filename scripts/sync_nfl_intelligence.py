"""Master NFL Intelligence Synchronizer.

Fetches real-time official NFL depth charts, live injury wires, and betting lines,
exporting high-performance local JSON caches into data/ for instant zero-latency access.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.adapters.nfl.depthchart_client import nfl_depthchart_client, ALL_NFL_TEAMS
from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.adapters.nfl.schedule_client import nfl_schedule_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_intelligence")

DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


async def sync_depth_charts() -> int:
    """Fetches all 32 NFL depth charts and exports them to data/nfl_depth_charts_2026.json."""
    logger.info("Fetching official depth charts for all 32 NFL teams...")
    charts = await nfl_depthchart_client.fetch_all_depth_charts(force=True)

    summary: dict[str, dict] = {
        "season": 2026,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_teams": len(charts),
        "teams": {},
    }

    for team, chart in charts.items():
        team_data = {
            "pro_team": team,
            "offense": {},
            "defense": {},
            "special_teams": {},
        }

        # Extract offense
        for slot, athletes in chart.offense.items():
            team_data["offense"][slot] = [
                {"name": a.display_name, "rank": a.rank, "id": a.athlete_id}
                for a in athletes
            ]

        # Extract defense
        for slot, athletes in chart.defense.items():
            team_data["defense"][slot] = [
                {"name": a.display_name, "rank": a.rank, "id": a.athlete_id}
                for a in athletes
            ]

        # Extract special teams
        for slot, athletes in chart.special_teams.items():
            team_data["special_teams"][slot] = [
                {"name": a.display_name, "rank": a.rank, "id": a.athlete_id}
                for a in athletes
            ]

        summary["teams"][team] = team_data

    out_file = DATA_DIR / "nfl_depth_charts_2026.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Exported depth charts for {len(charts)} teams to {out_file.name}")
    return len(charts)


async def sync_injuries() -> int:
    """Fetches active injury reports and exports to data/injuries_live_2026.json."""
    logger.info("Fetching live NFL injury wire...")
    injuries = await nfl_injuries_client.fetch_injuries()
    enriched_list = await nfl_injuries_client.enrich_beneficiaries(list(injuries.values()))

    report = {
        "season": 2026,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_injuries": len(enriched_list),
        "injuries": [
            {
                "athlete_id": inj.athlete_id,
                "name": inj.name,
                "position": inj.position,
                "team": inj.team,
                "status": inj.status,
                "headline": inj.headline,
                "notes": inj.notes,
                "practice_status": inj.practice_status,
                "practice_trend": inj.practice_trend,
                "is_playable": inj.is_playable,
                "is_out": inj.is_out,
                "backup_athlete_name": inj.backup_athlete_name,
                "vacated_opportunity_note": inj.vacated_opportunity_note,
            }
            for inj in enriched_list
        ],
    }

    out_file = DATA_DIR / "injuries_live_2026.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Exported {len(injuries)} injury reports to {out_file.name}")
    return len(injuries)


async def sync_vegas_odds() -> int:
    """Fetches week schedule and live betting lines, exporting to data/vegas_movement_2026.json."""
    nfl_schedule_client.clear_cache()
    games = await nfl_schedule_client.fetch_week_schedule(season=2026, week=1)

    summary = {
        "season": 2026,
        "week": 1,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_games": len(games),
        "games": [
            {
                "id": g.id,
                "name": g.name,
                "date": g.date,
                "venue_name": g.venue_name,
                "is_dome": g.is_dome,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "spread": g.spread,
                "over_under": g.over_under,
                "home_implied_total": g.home_implied_total,
                "away_implied_total": g.away_implied_total,
                "is_started": g.is_started,
                "is_final": g.is_final,
            }
            for g in games
        ],
    }

    out_file = DATA_DIR / "vegas_movement_2026.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Exported {len(games)} game odds to {out_file.name}")
    return len(games)


async def main():
    logger.info("=== Starting Master NFL Intelligence Sync ===")
    t1 = asyncio.create_task(sync_depth_charts())
    t2 = asyncio.create_task(sync_injuries())
    t3 = asyncio.create_task(sync_vegas_odds())

    teams_count, inj_count, games_count = await asyncio.gather(t1, t2, t3)
    logger.info(
        f"=== Sync Complete! Synced {teams_count} Teams, {inj_count} Injuries, {games_count} Games ==="
    )


if __name__ == "__main__":
    asyncio.run(main())
