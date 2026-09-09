"""Official NFL Injury Client querying live ESPN/RotoWire injury reports."""

import logging
import re
from typing import Any
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"


class PlayerInjuryReport(BaseModel):
    athlete_id: int
    name: str
    position: str
    team: str
    status: str  # ACTIVE, QUESTIONABLE, OUT, DOUBTFUL, IR
    headline: str | None = None
    notes: str | None = None
    date: str | None = None

    @property
    def is_playable(self) -> bool:
        return self.status.upper() in ("ACTIVE", "QUESTIONABLE") and not self.is_out

    @property
    def is_out(self) -> bool:
        st = self.status.upper()
        return st in ("OUT", "DOUBTFUL", "IR", "INACTIVE", "SUSPENDED") or "IR" in st

    @property
    def practice_status(self) -> str | None:
        """Parses practice progression (FULL, LIMITED, DNP) from latest injury notes and headlines."""
        text = f"{self.headline or ''} {self.notes or ''}".lower()
        if not text.strip():
            return None
        if "full practice" in text or "full participant" in text or "practiced in full" in text or "fp" in text.split():
            return "FULL"
        if "limited" in text or "lp" in text.split() or "limited participant" in text:
            return "LIMITED"
        if "did not practice" in text or "dnp" in text.split() or "missed practice" in text or "held out" in text:
            return "DNP"
        return None


class NFLInjuriesClient:
    """Client for retrieving official NFL injury reports and practice notes."""

    def __init__(self, timeout: float = 10.0, cache_ttl: float = 300.0):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: dict[int, PlayerInjuryReport] = {}
        self._cache_time: float = 0.0

    def clear_cache(self) -> None:
        """Clear the in-memory injury reports cache."""
        self._cache.clear()
        self._cache_time = 0.0

    async def fetch_injuries(self, force: bool = False) -> dict[int, PlayerInjuryReport]:
        """Fetch all official NFL injury updates indexed by athlete ID with 5-min TTL cache."""
        import time
        now = time.time()
        if not force and self._cache_time > 0 and (now - self._cache_time) < self.cache_ttl:
            return self._cache

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(ESPN_INJURIES_URL)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f"Failed to fetch live injuries from ESPN: {e}")
                return self._cache

        results: dict[int, PlayerInjuryReport] = {}
        for team_entry in data.get("injuries", []):
            team_display = team_entry.get("displayName", "")
            for inj in team_entry.get("injuries", []):
                try:
                    athlete = inj.get("athlete", {})
                    athlete_id = None
                    if athlete.get("id"):
                        try:
                            athlete_id = int(athlete["id"])
                        except (ValueError, TypeError):
                            pass

                    if not athlete_id:
                        for link in athlete.get("links", []):
                            href = link.get("href", "")
                            m = re.search(r"/id/(\d+)", href) or re.search(r"~a:(\d+)", href)
                            if m:
                                athlete_id = int(m.group(1))
                                break

                    if not athlete_id:
                        continue

                    full_name = athlete.get("displayName", "")
                    pos = athlete.get("position", {}).get("abbreviation", "UNK")
                    status_raw = inj.get("status", "Active")
                    if isinstance(status_raw, dict):
                        status_name = status_raw.get("name", "Active").upper()
                    else:
                        status_name = str(status_raw).upper()

                    notes_obj = athlete.get("notes", {})
                    notes_list = notes_obj.get("items", []) if isinstance(notes_obj, dict) else []
                    headline = None
                    text = None
                    date_str = None
                    if notes_list and isinstance(notes_list[0], dict):
                        latest_note = notes_list[0]
                        headline = latest_note.get("headline")
                        text = latest_note.get("text")
                        date_str = latest_note.get("date")

                    # Elevate status to OUT only if this athlete is the direct subject of surgery, meniscus trim, or being ruled out
                    if headline:
                        h_lower = headline.lower()
                        last_name = full_name.split()[-1].lower() if full_name else ""
                        if last_name and (
                            f"{last_name} underwent" in h_lower
                            or f"ruled out {last_name}" in h_lower
                            or f"{last_name} has been ruled out" in h_lower
                            or f"{last_name} is expected to miss" in h_lower
                            or (status_name == "DOUBTFUL" and ("meniscus" in h_lower or "surgery" in h_lower))
                        ):
                            if "ir" not in status_name.lower():
                                status_name = "OUT"

                    results[athlete_id] = PlayerInjuryReport(
                        athlete_id=athlete_id,
                        name=full_name,
                        position=pos,
                        team=team_display,
                        status=status_name,
                        headline=headline,
                        notes=text,
                        date=date_str,
                    )
                except Exception as e:
                    logger.debug(f"Error parsing injury entry: {e}")

        self._cache = results
        self._cache_time = now
        return results


nfl_injuries_client = NFLInjuriesClient()
