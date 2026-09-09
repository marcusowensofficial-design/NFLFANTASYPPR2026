"""NFL Schedule, Venues, and Betting Odds Client using ESPN Public API."""

import logging
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"


class NFLTeamOdds(BaseModel):
    team: str
    is_home: bool
    spread: float = 0.0
    implied_total: float = 22.0


class NFLGame(BaseModel):
    id: str
    name: str
    date: str
    venue_name: str
    is_dome: bool = False
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    is_started: bool = False
    is_final: bool = False
    over_under: float = 44.0
    spread: float = 0.0  # From home perspective: -3.5 means home favored by 3.5
    home_implied_total: float = 23.75
    away_implied_total: float = 20.25

    def get_implied_total_for_team(self, team_abbrev: str) -> float:
        if team_abbrev == self.home_team:
            return self.home_implied_total
        if team_abbrev == self.away_team:
            return self.away_implied_total
        return 21.0

    def get_opponent_for_team(self, team_abbrev: str) -> str | None:
        if team_abbrev == self.home_team:
            return self.away_team
        if team_abbrev == self.away_team:
            return self.home_team
        return None

    def is_home_for_team(self, team_abbrev: str) -> bool:
        return team_abbrev == self.home_team


class NFLScheduleClient:
    """Client for retrieving live NFL schedules, dome flags, and DraftKings odds."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self._cache: dict[tuple[int, int], list[NFLGame]] = {}

    def clear_cache(self) -> None:
        """Clear the in-memory NFL schedule cache."""
        self._cache.clear()

    async def fetch_week_schedule(self, season: int = 2026, week: int = 1) -> list[NFLGame]:
        """Fetch all games for a specific NFL week with dome status and betting lines."""
        cache_key = (season, week)
        if cache_key in self._cache:
            return self._cache[cache_key]

        params = {"seasontype": "2", "week": str(week), "dates": str(season)}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(ESPN_SCOREBOARD_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f"Failed to fetch live NFL schedule from ESPN for week {week}: {e}")
                return self._get_fallback_schedule(week)

        games: list[NFLGame] = []
        for ev in data.get("events", []):
            try:
                comp = ev.get("competitions", [{}])[0]
                venue = comp.get("venue", {})
                venue_name = venue.get("fullName", "NFL Stadium")
                is_dome = venue.get("indoor", False)

                competitors = comp.get("competitors", [])
                home_c = next((c for c in competitors if c.get("homeAway") == "home"), {})
                away_c = next((c for c in competitors if c.get("homeAway") == "away"), {})

                home_team = home_c.get("team", {}).get("abbreviation", "UNK")
                away_team = away_c.get("team", {}).get("abbreviation", "UNK")
                home_score = int(home_c.get("score", 0) or 0)
                away_score = int(away_c.get("score", 0) or 0)

                status = ev.get("status", {}).get("type", {})
                state = status.get("state", "pre")
                is_started = state in ("in", "post")
                is_final = state == "post"

                # Parse odds (over/under and spread)
                over_under = 44.0
                spread = 0.0
                odds_list = comp.get("odds", [])
                if odds_list:
                    primary_odds = odds_list[0]
                    over_under = float(primary_odds.get("overUnder", 44.0) or 44.0)
                    spread = float(primary_odds.get("spread", 0.0) or 0.0)

                # Derive implied totals:
                # spread is from home team perspective: spread = -3.5 means home is favored by 3.5
                home_implied = round((over_under / 2.0) - (spread / 2.0), 2)
                away_implied = round((over_under / 2.0) + (spread / 2.0), 2)

                games.append(
                    NFLGame(
                        id=str(ev.get("id")),
                        name=ev.get("name", f"{away_team} at {home_team}"),
                        date=ev.get("date", ""),
                        venue_name=venue_name,
                        is_dome=is_dome,
                        home_team=home_team,
                        away_team=away_team,
                        home_score=home_score,
                        away_score=away_score,
                        is_started=is_started,
                        is_final=is_final,
                        over_under=over_under,
                        spread=spread,
                        home_implied_total=home_implied,
                        away_implied_total=away_implied,
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing event {ev.get('id')}: {e}")

        result = games if games else self._get_fallback_schedule(week)
        self._cache[cache_key] = result
        return result

    async def get_upcoming_schedule_for_team(
        self,
        pro_team: str,
        current_week: int = 1,
        count: int = 3,
        season: int = 2026,
    ) -> list[dict[str, Any]]:
        """Returns the upcoming 3-game schedule for a pro team."""
        team_clean = pro_team.upper().strip()
        schedule_chips: list[dict[str, Any]] = []

        for target_week in range(current_week, current_week + count):
            games = await self.fetch_week_schedule(season=season, week=target_week)
            matchup = next((g for g in games if g.home_team == team_clean or g.away_team == team_clean), None)

            if matchup:
                opp = matchup.get_opponent_for_team(team_clean) or "BYE"
                is_home = matchup.is_home_for_team(team_clean)
                implied = matchup.get_implied_total_for_team(team_clean)
                spread = matchup.spread if is_home else -matchup.spread
                schedule_chips.append({
                    "week": target_week,
                    "opp": opp,
                    "is_home": is_home,
                    "date": matchup.date,
                    "venue": matchup.venue_name,
                    "is_dome": matchup.is_dome,
                    "spread": spread,
                    "implied_total": implied,
                })
            else:
                schedule_chips.append({
                    "week": target_week,
                    "opp": "BYE",
                    "is_home": False,
                    "date": "",
                    "venue": "BYE",
                    "is_dome": True,
                    "spread": 0.0,
                    "implied_total": 0.0,
                })

        return schedule_chips

    def _get_fallback_schedule(self, week: int = 1) -> list[NFLGame]:
        """Provides verified official 2026 NFL schedule for Weeks 1-3 when offline."""
        import json
        from pathlib import Path
        data_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "nfl_2026_weeks_1_3.json"
        if data_path.exists():
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    weeks_data = json.load(f)
                week_key = str(week)
                if week_key in weeks_data:
                    return [NFLGame(**g) for g in weeks_data[week_key]]
            except Exception as e:
                logger.debug(f"Error loading {data_path}: {e}")

        if week == 1:
            return [
                NFLGame(id="401872656", name="New England Patriots at Seattle Seahawks", date="2026-09-10T00:20Z", venue_name="Lumen Field", is_dome=False, home_team="SEA", away_team="NE", over_under=43.5, spread=-4.5, home_implied_total=24.0, away_implied_total=19.5),
                NFLGame(id="401872657", name="San Francisco 49ers at Los Angeles Rams", date="2026-09-11T00:35Z", venue_name="SoFi Stadium", is_dome=True, home_team="LAR", away_team="SF", over_under=47.5, spread=2.5, home_implied_total=22.5, away_implied_total=25.0),
                NFLGame(id="401872925", name="Tampa Bay Buccaneers at Cincinnati Bengals", date="2026-09-13T17:00Z", venue_name="Paycor Stadium", is_dome=False, home_team="CIN", away_team="TB", over_under=48.0, spread=-3.5, home_implied_total=25.75, away_implied_total=22.25),
                NFLGame(id="401872923", name="New Orleans Saints at Detroit Lions", date="2026-09-13T17:00Z", venue_name="Ford Field", is_dome=True, home_team="DET", away_team="NO", over_under=51.5, spread=-6.5, home_implied_total=29.0, away_implied_total=22.5),
                NFLGame(id="401872924", name="New York Jets at Tennessee Titans", date="2026-09-13T17:00Z", venue_name="Nissan Stadium", is_dome=False, home_team="TEN", away_team="NYJ", over_under=42.0, spread=4.0, home_implied_total=19.0, away_implied_total=23.0),
                NFLGame(id="401872659", name="Baltimore Ravens at Indianapolis Colts", date="2026-09-13T17:00Z", venue_name="Lucas Oil Stadium", is_dome=True, home_team="IND", away_team="BAL", over_under=49.0, spread=3.5, home_implied_total=22.75, away_implied_total=26.25),
                NFLGame(id="401872658", name="Atlanta Falcons at Pittsburgh Steelers", date="2026-09-13T17:00Z", venue_name="Acrisure Stadium", is_dome=False, home_team="PIT", away_team="ATL", over_under=43.0, spread=-2.5, home_implied_total=22.75, away_implied_total=20.25),
                NFLGame(id="401872661", name="Chicago Bears at Carolina Panthers", date="2026-09-13T17:00Z", venue_name="Bank of America Stadium", is_dome=False, home_team="CAR", away_team="CHI", over_under=45.5, spread=4.5, home_implied_total=20.5, away_implied_total=25.0),
                NFLGame(id="401872922", name="Cleveland Browns at Jacksonville Jaguars", date="2026-09-13T17:00Z", venue_name="EverBank Stadium", is_dome=False, home_team="JAX", away_team="CLE", over_under=44.0, spread=-1.5, home_implied_total=22.75, away_implied_total=21.25),
                NFLGame(id="401872660", name="Buffalo Bills at Houston Texans", date="2026-09-13T17:00Z", venue_name="NRG Stadium", is_dome=True, home_team="HOU", away_team="BUF", over_under=50.5, spread=1.5, home_implied_total=24.5, away_implied_total=26.0),
                NFLGame(id="401872928", name="Miami Dolphins at Las Vegas Raiders", date="2026-09-13T20:25Z", venue_name="Allegiant Stadium", is_dome=True, home_team="LV", away_team="MIA", over_under=47.0, spread=3.5, home_implied_total=21.75, away_implied_total=25.25),
                NFLGame(id="401872927", name="Green Bay Packers at Minnesota Vikings", date="2026-09-13T20:25Z", venue_name="U.S. Bank Stadium", is_dome=True, home_team="MIN", away_team="GB", over_under=46.5, spread=2.5, home_implied_total=22.0, away_implied_total=24.5),
                NFLGame(id="401872929", name="Washington Commanders at Philadelphia Eagles", date="2026-09-13T20:25Z", venue_name="Lincoln Financial Field", is_dome=False, home_team="PHI", away_team="WSH", over_under=48.5, spread=-5.5, home_implied_total=27.0, away_implied_total=21.5),
                NFLGame(id="401872926", name="Arizona Cardinals at Los Angeles Chargers", date="2026-09-13T20:25Z", venue_name="SoFi Stadium", is_dome=True, home_team="LAC", away_team="ARI", over_under=46.0, spread=-3.0, home_implied_total=24.5, away_implied_total=21.5),
                NFLGame(id="401872930", name="Dallas Cowboys at New York Giants", date="2026-09-14T00:20Z", venue_name="MetLife Stadium", is_dome=False, home_team="NYG", away_team="DAL", over_under=46.5, spread=4.5, home_implied_total=21.0, away_implied_total=25.5),
                NFLGame(id="401872931", name="Denver Broncos at Kansas City Chiefs", date="2026-09-15T00:15Z", venue_name="GEHA Field at Arrowhead Stadium", is_dome=False, home_team="KC", away_team="DEN", over_under=48.5, spread=-6.5, home_implied_total=27.5, away_implied_total=21.0),
            ]
        return []


nfl_schedule_client = NFLScheduleClient()
