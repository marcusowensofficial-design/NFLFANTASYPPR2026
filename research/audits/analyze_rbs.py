import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import json
import sqlite3
import asyncio
from src.services.matchup.dvp_service import dvp_service
from src.adapters.betting.props_client import vegas_props_client
from src.services.matchup.vegas_gamescript import vegas_gamescript_analyzer
from src.adapters.nfl.schedule_client import nfl_schedule_client

async def main():
    df = pd.read_csv('data/FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv')
    print(f"Total rows: {len(df)}")
    games = sorted(df['Game'].unique().tolist())
    print(f"Games on slate ({len(games)}): {games}")
    teams = sorted(df['Team'].unique().tolist())
    print(f"Teams on slate ({len(teams)}): {teams}")

    sched = await nfl_schedule_client.fetch_week_schedule(season=2026, week=1)
    print(f"Schedule week 1 games count: {len(sched)}")
    
    # Check games matching
    for g in sched:
        matchup = f"{g.away_team}@{g.home_team}"
        alt = f"{g.away_team.replace('WSH', 'WAS')}@{g.home_team.replace('WSH', 'WAS')}"
        in_slate = matchup in games or alt in games
        print(f"Game: {g.away_team} @ {g.home_team} | O/U: {g.over_under} | Spread: {g.spread} | Away Imp: {g.away_implied_total} | Home Imp: {g.home_implied_total} | On Slate: {in_slate}")

if __name__ == '__main__':
    asyncio.run(main())
