"""ESPN Fantasy Football v3 API client with support for public and private leagues."""

import logging
from typing import Any
import httpx

from src.adapters.espn.constants import ESPN_FFL_BASE_URL, RosterSlot
from src.adapters.espn.schemas import (
    ESPNAthlete,
    ESPNLeagueResponse,
    LeagueSummary,
    TeamSummary,
)

logger = logging.getLogger(__name__)


class ESPNAPIError(Exception):
    """Base exception for ESPN Fantasy API errors."""
    def __init__(self, message: str, status_code: int | None = None, response_data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ESPNUnauthorizedError(ESPNAPIError):
    """Raised when access to a private league is denied due to missing or invalid cookies."""


class ESPNNotFoundError(ESPNAPIError):
    """Raised when a league ID or season cannot be found on ESPN."""


class ESPNRateLimitError(ESPNAPIError):
    """Raised when ESPN rate limits API requests."""


class ESPNClient:
    """Robust client for fetching data from ESPN Fantasy Football v3 API."""

    def __init__(
        self,
        league_id: int,
        season: int = 2026,
        swid: str | None = None,
        espn_s2: str | None = None,
        timeout: float = 12.0,
    ):
        self.league_id = league_id
        self.season = season
        self.swid = self._normalize_swid(swid) if swid else None
        self.espn_s2 = espn_s2.strip() if espn_s2 else None
        self.timeout = timeout

    @staticmethod
    def _normalize_swid(swid: str | None) -> str | None:
        if not swid:
            return None
        cleaned = swid.strip()
        # ESPN SWID cookies are GUIDs typically wrapped in curly braces {GUID}
        if not cleaned.startswith("{") and len(cleaned) == 36:
            cleaned = f"{{{cleaned}}}"
        return cleaned

    @property
    def has_credentials(self) -> bool:
        """Returns True if private league session cookies are present."""
        return bool(self.swid and self.espn_s2)

    def _get_cookies(self) -> dict[str, str]:
        cookies: dict[str, str] = {}
        if self.swid:
            cookies["SWID"] = self.swid
        if self.espn_s2:
            cookies["espn_s2"] = self.espn_s2
        return cookies

    def _get_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "x-fantasy-platform": "kona",
            "x-fantasy-source": "kona",
        }

    @property
    def league_url(self) -> str:
        return f"{ESPN_FFL_BASE_URL}/seasons/{self.season}/segments/0/leagues/{self.league_id}"

    async def fetch_league_raw(
        self,
        views: list[str] | None = None,
        scoring_period_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch raw JSON league data with requested views."""
        if views is None:
            views = ["mTeam", "mRoster", "mSettings", "mMatchupScore", "mScoreboard"]

        params: list[tuple[str, str]] = [("view", v) for v in views]
        if scoring_period_id is not None:
            params.append(("scoringPeriodId", str(scoring_period_id)))

        async with httpx.AsyncClient(
            timeout=self.timeout,
            cookies=self._get_cookies(),
            headers=self._get_headers(),
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(self.league_url, params=params)
            except httpx.TimeoutException as exc:
                raise ESPNAPIError(
                    f"Connection timed out while connecting to ESPN for league {self.league_id}.",
                    status_code=504,
                ) from exc
            except httpx.RequestError as exc:
                raise ESPNAPIError(
                    f"Network error while connecting to ESPN: {exc}",
                    status_code=500,
                ) from exc

        if response.status_code == 200:
            return response.json()

        if response.status_code == 401:
            raise ESPNUnauthorizedError(
                f"ESPN League {self.league_id} is PRIVATE or the session expired. "
                "Valid ESPN_SWID and ESPN_S2 cookies must be configured in your .env file.",
                status_code=401,
                response_data=response.text,
            )

        if response.status_code == 404:
            raise ESPNNotFoundError(
                f"ESPN League {self.league_id} was not found for season {self.season}. "
                "Check that your league ID and season are correct.",
                status_code=404,
                response_data=response.text,
            )

        if response.status_code == 429:
            raise ESPNRateLimitError(
                "ESPN returned 429 Rate Limited. Please wait a few moments before trying again.",
                status_code=429,
                response_data=response.text,
            )

        raise ESPNAPIError(
            f"ESPN API returned unexpected status code {response.status_code}: {response.text[:250]}",
            status_code=response.status_code,
            response_data=response.text,
        )

    async def fetch_league(self, scoring_period_id: int | None = None) -> ESPNLeagueResponse:
        """Fetch and parse league data into verified Pydantic schema."""
        raw_data = await self.fetch_league_raw(scoring_period_id=scoring_period_id)
        return ESPNLeagueResponse.model_validate(raw_data)

    async def fetch_free_agents_raw(
        self,
        scoring_period_id: int | None = None,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """Fetch available free agents and players on waivers for the league."""
        filter_header = (
            f'{{"players":{{"filterStatus":{{"value":["FREEAGENT","WAIVERS"]}},"limit":{limit},'
            f'"sortDraftRanks":{{"sortPriority":100,"sortAsc":true,"value":"STANDARD"}}}}}}'
        )
        headers = self._get_headers()
        headers["X-Fantasy-Filter"] = filter_header

        params: list[tuple[str, str]] = [("view", "kona_player_info")]
        if scoring_period_id is not None:
            params.append(("scoringPeriodId", str(scoring_period_id)))

        async with httpx.AsyncClient(
            timeout=self.timeout,
            cookies=self._get_cookies(),
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(self.league_url, params=params)

        if response.status_code != 200:
            raise ESPNAPIError(
                f"Failed to fetch free agents from ESPN (HTTP {response.status_code}): {response.text[:200]}",
                status_code=response.status_code,
            )

        data = response.json()
        return data.get("players", [])

    async def fetch_free_agents(
        self,
        scoring_period_id: int | None = None,
        limit: int = 100,
    ) -> list[ESPNAthlete]:
        """Fetch and parse available free agents into validated ESPNAthlete objects."""
        raw_items = await self.fetch_free_agents_raw(scoring_period_id=scoring_period_id, limit=limit)
        athletes: list[ESPNAthlete] = []
        for item in raw_items:
            player_dict = item.get("player")
            if player_dict:
                try:
                    athletes.append(ESPNAthlete.model_validate(player_dict))
                except Exception as e:
                    logger.debug(f"Failed to validate free agent athlete: {e}")
        return athletes

    async def test_connection(self) -> tuple[bool, str, LeagueSummary | None]:
        """Test league connection and return diagnostic result."""
        try:
            league = await self.fetch_league()
            settings = league.settings
            league_name = settings.name if settings else f"League #{league.id}"
            size = settings.size if settings else len(league.teams)
            roster_settings = settings.roster_settings if settings else None
            scoring_settings = settings.scoring_settings if settings else None

            slot_counts = roster_settings.parsed_slot_counts if roster_settings else {}
            is_ppr = scoring_settings.is_ppr if scoring_settings else True
            rec_pts = scoring_settings.reception_points if scoring_settings else 1.0

            teams: list[TeamSummary] = []
            for t in league.teams:
                record_str = "0-0"
                pf = 0.0
                if t.record and t.record.overall:
                    record_str = f"{t.record.overall.wins}-{t.record.overall.losses}"
                    if t.record.overall.ties > 0:
                        record_str += f"-{t.record.overall.ties}"
                    pf = round(t.record.overall.points_for, 1)

                starter_count = 0
                bench_count = 0
                if t.roster and t.roster.entries:
                    for entry in t.roster.entries:
                        if entry.lineup_slot_id == RosterSlot.BENCH:
                            bench_count += 1
                        elif entry.lineup_slot_id == RosterSlot.IR:
                            pass
                        else:
                            starter_count += 1

                teams.append(
                    TeamSummary(
                        id=t.id,
                        name=t.full_name,
                        abbrev=t.abbrev,
                        owner=t.primary_owner,
                        record=record_str,
                        points_for=pf,
                        starter_count=starter_count,
                        bench_count=bench_count,
                    )
                )

            summary = LeagueSummary(
                league_id=league.id,
                season=league.season_id,
                name=league_name,
                size=size,
                current_week=league.scoring_period_id,
                is_ppr=is_ppr,
                reception_points=rec_pts,
                roster_slots=slot_counts,
                teams=teams,
            )
            return True, f"Successfully connected to ESPN league '{league_name}' ({len(teams)} teams).", summary

        except ESPNUnauthorizedError as e:
            return False, f"UNAUTHORIZED (Private League): {e}", None
        except ESPNNotFoundError as e:
            return False, f"NOT FOUND: {e}", None
        except ESPNAPIError as e:
            return False, f"ESPN API Error: {e}", None
        except Exception as e:
            logger.exception("Unexpected error testing ESPN connection")
            return False, f"Unexpected error connecting to ESPN: {e}", None

    async def execute_roster_transaction(
        self,
        team_id: int,
        moves: list[dict[str, Any]],
        scoring_period_id: int = 1,
        dry_run: bool = False,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Submit an authenticated lineup transaction to ESPN to move players between slots."""
        if not self.has_credentials:
            return False, "Cannot push to ESPN: missing SWID or espn_s2 session cookies in .env", {}

        transaction_url = f"{self.league_url}/transactions/roster"
        items = []
        for m in moves:
            items.append({
                "playerId": int(m["player_id"]),
                "type": "LINEUP",
                "fromLineupSlotId": int(m["from_slot_id"]),
                "toLineupSlotId": int(m["to_slot_id"]),
            })

        payload = {
            "isLeagueManager": False,
            "teamId": team_id,
            "type": "ROSTER",
            "scoringPeriodId": scoring_period_id,
            "executionType": "EXECUTE",
            "items": items,
        }

        if dry_run:
            return True, f"Dry-run preview: prepared {len(items)} moves for ESPN submission.", payload

        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(
            timeout=self.timeout,
            cookies=self._get_cookies(),
            headers=headers,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.post(transaction_url, json=payload)
            except Exception as exc:
                return False, f"Network error submitting lineup to ESPN: {exc}", payload

        if response.status_code in (200, 204):
            return True, f"Successfully updated ESPN lineup with {len(items)} moves!", payload
        else:
            err_detail = response.text[:300]
            logger.error(f"ESPN transaction error (HTTP {response.status_code}): {err_detail}")
            return False, f"ESPN rejected roster change (HTTP {response.status_code}): {err_detail}", payload
