"""Website Backend Route Registry.

Maps all 10 production API routers servicing the Apex Fantasy frontend web application:
- League & Team Roster Intelligence
- Lineup Optimizer & Optimal Starting Combinations
- Player Recommendations & Head-to-Head Comparisons
- Waiver Wire Consensus & Drop Recommendations
- DFS Single-Game & Main-Slate Matrix Optimizers
- Defense vs Position (DvP) & Matchup Matrix
- Vegas Lines, Syndicate Steam & Player Props
- Live In-Game Actuals & Forensic Game Logs
- Injury Wire, Practice Trends & Decoy Risk
- Sleeper & FantasyPros Real-Time Sync
"""

from src.api.analysis_routes import router as analysis_router
from src.api.backtest_routes import router as backtest_router
from src.api.dfs_routes import router as dfs_router
from src.api.fantasypros_routes import router as fantasypros_router
from src.api.injury_routes import router as injury_router
from src.api.league_routes import router as league_router
from src.api.lineup_routes import router as lineup_router
from src.api.recommendation_routes import router as recommendation_router
from src.api.sleeper_routes import router as sleeper_router
from src.api.waiver_routes import router as waiver_router

WEBSITE_ROUTERS = [
    league_router,
    lineup_router,
    recommendation_router,
    waiver_router,
    backtest_router,
    injury_router,
    fantasypros_router,
    sleeper_router,
    analysis_router,
    dfs_router,
]
