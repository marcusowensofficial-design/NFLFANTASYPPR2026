"""ESPN Fantasy Football Adapter Package."""

from src.adapters.espn.client import (
    ESPNAPIError,
    ESPNClient,
    ESPNNotFoundError,
    ESPNRateLimitError,
    ESPNUnauthorizedError,
)
from src.adapters.espn.constants import (
    NFL_TEAM_MAP,
    POSITION_ID_MAP,
    SLOT_NAME_MAP,
    RosterSlot,
    StatSource,
)
from src.adapters.espn.schemas import (
    ESPNAthlete,
    ESPNLeagueResponse,
    ESPNLeagueSettings,
    ESPNPlayerPoolEntry,
    ESPNRoster,
    ESPNRosterEntry,
    ESPNTeam,
    LeagueSummary,
    TeamSummary,
)

__all__ = [
    "ESPNAPIError",
    "ESPNClient",
    "ESPNNotFoundError",
    "ESPNRateLimitError",
    "ESPNUnauthorizedError",
    "NFL_TEAM_MAP",
    "POSITION_ID_MAP",
    "SLOT_NAME_MAP",
    "RosterSlot",
    "StatSource",
    "ESPNAthlete",
    "ESPNLeagueResponse",
    "ESPNLeagueSettings",
    "ESPNPlayerPoolEntry",
    "ESPNRoster",
    "ESPNRosterEntry",
    "ESPNTeam",
    "LeagueSummary",
    "TeamSummary",
]
