"""NFL Schedule and Injuries adapter package."""

from src.adapters.nfl.injuries_client import (
    NFLInjuriesClient,
    PlayerInjuryReport,
    nfl_injuries_client,
)
from src.adapters.nfl.schedule_client import (
    NFLGame,
    NFLScheduleClient,
    NFLTeamOdds,
    nfl_schedule_client,
)

__all__ = [
    "NFLGame",
    "NFLScheduleClient",
    "NFLTeamOdds",
    "nfl_schedule_client",
    "PlayerInjuryReport",
    "NFLInjuriesClient",
    "nfl_injuries_client",
]
