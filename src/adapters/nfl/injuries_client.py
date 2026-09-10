"""Official NFL Injury Client querying live ESPN/RotoWire injury reports."""

import logging
import re
from typing import Any
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"


TEAM_NAME_TO_ABBR: dict[str, str] = {
    "ARIZONA CARDINALS": "ARI", "CARDINALS": "ARI", "ARI": "ARI",
    "ATLANTA FALCONS": "ATL", "FALCONS": "ATL", "ATL": "ATL",
    "BALTIMORE RAVENS": "BAL", "RAVENS": "BAL", "BAL": "BAL",
    "BUFFALO BILLS": "BUF", "BILLS": "BUF", "BUF": "BUF",
    "CAROLINA PANTHERS": "CAR", "PANTHERS": "CAR", "CAR": "CAR",
    "CHICAGO BEARS": "CHI", "BEARS": "CHI", "CHI": "CHI",
    "CINCINNATI BENGALS": "CIN", "BENGALS": "CIN", "CIN": "CIN",
    "CLEVELAND BROWNS": "CLE", "BROWNS": "CLE", "CLE": "CLE",
    "DALLAS COWBOYS": "DAL", "COWBOYS": "DAL", "DAL": "DAL",
    "DENVER BRONCOS": "DEN", "BRONCOS": "DEN", "DEN": "DEN",
    "DETROIT LIONS": "DET", "LIONS": "DET", "DET": "DET",
    "GREEN BAY PACKERS": "GB", "PACKERS": "GB", "GB": "GB",
    "HOUSTON TEXANS": "HOU", "TEXANS": "HOU", "HOU": "HOU",
    "INDIANAPOLIS COLTS": "IND", "COLTS": "IND", "IND": "IND",
    "JACKSONVILLE JAGUARS": "JAX", "JAGUARS": "JAX", "JAX": "JAX", "JAC": "JAX",
    "KANSAS CITY CHIEFS": "KC", "CHIEFS": "KC", "KC": "KC",
    "LAS VEGAS RAIDERS": "LV", "RAIDERS": "LV", "LV": "LV", "OAK": "LV",
    "LOS ANGELES CHARGERS": "LAC", "CHARGERS": "LAC", "LAC": "LAC", "SD": "LAC",
    "LOS ANGELES RAMS": "LAR", "RAMS": "LAR", "LAR": "LAR", "LA": "LAR", "STL": "LAR",
    "MIAMI DOLPHINS": "MIA", "DOLPHINS": "MIA", "MIA": "MIA",
    "MINNESOTA VIKINGS": "MIN", "VIKINGS": "MIN", "MIN": "MIN",
    "NEW ENGLAND PATRIOTS": "NE", "PATRIOTS": "NE", "NE": "NE",
    "NEW ORLEANS SAINTS": "NO", "SAINTS": "NO", "NO": "NO",
    "NEW YORK GIANTS": "NYG", "GIANTS": "NYG", "NYG": "NYG",
    "NEW YORK JETS": "NYJ", "JETS": "NYJ", "NYJ": "NYJ",
    "PHILADELPHIA EAGLES": "PHI", "EAGLES": "PHI", "PHI": "PHI",
    "PITTSBURGH STEELERS": "PIT", "STEELERS": "PIT", "PIT": "PIT",
    "SAN FRANCISCO 49ERS": "SF", "49ERS": "SF", "SF": "SF",
    "SEATTLE SEAHAWKS": "SEA", "SEAHAWKS": "SEA", "SEA": "SEA",
    "TAMPA BAY BUCCANEERS": "TB", "BUCCANEERS": "TB", "TB": "TB",
    "TENNESSEE TITANS": "TEN", "TITANS": "TEN", "TEN": "TEN",
    "WASHINGTON COMMANDERS": "WAS", "COMMANDERS": "WAS", "WAS": "WAS", "WSH": "WAS",
}


def resolve_team_abbrev(team_str: str) -> str:
    cleaned = (team_str or "").strip().upper()
    return TEAM_NAME_TO_ABBR.get(cleaned, cleaned[:3])


def generate_vacated_opportunity_note(position: str, backup_name: str, rank: int) -> str:
    pos = position.upper().strip()
    if pos == "RB":
        return f"Primary beneficiary of vacated early-down carries & red-zone volume if starter is sidelined."
    elif pos in ("WR", "WR1", "WR2", "WR3", "SLOT_WR"):
        return f"Expands to high-volume target progression and 2-WR/3-WR set route participation."
    elif pos == "TE":
        return f"Assumes inline snaps and high-leverage red-zone target share."
    elif pos == "QB":
        return f"Takes over first-team reps under center with full pass-funnel responsibility."
    return f"Next designated athlete on official team depth chart hierarchy."


class PlayerInjuryReport(BaseModel):
    athlete_id: int
    name: str
    position: str
    team: str
    status: str  # ACTIVE, QUESTIONABLE, OUT, DOUBTFUL, IR
    headline: str | None = None
    notes: str | None = None
    date: str | None = None
    backup_athlete_name: str | None = None
    backup_athlete_id: int | None = None
    backup_slot: str | None = None
    vacated_opportunity_note: str | None = None

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

    @property
    def practice_trend(self) -> str | None:
        """Determines practice trajectory (e.g., Upward, Setback, Consecutive DNP, Full)."""
        text = f"{self.headline or ''} {self.notes or ''}".lower()
        if not text.strip():
            return None
        if "setback" in text or "downgrade" in text or ("dnp" in text and "after" in text and ("limited" in text or "full" in text)):
            return "SETBACK (DNP)"
        if "did not practice friday" in text or "missed friday" in text or "held out friday" in text:
            return "FRIDAY DNP"
        if "upgraded" in text or ("full" in text and "after" in text and ("limited" in text or "dnp" in text)):
            return "UPWARD (➔ FP)"
        if "progressed" in text or "trending up" in text:
            return "PROGRESSING (LP ➔ FP)"
        if "all week" in text:
            if "full" in text or "practiced" in text:
                return "FULL ALL WEEK"
            if "missed" in text or "did not" in text or "held out" in text:
                return "CONSECUTIVE DNP"
        ps = self.practice_status
        if ps == "FULL":
            return "FULL PARTICIPANT"
        elif ps == "LIMITED":
            return "LIMITED PARTICIPANT"
        elif ps == "DNP":
            return "DNP (DID NOT PRACTICE)"
        return None

    @property
    def decoy_risk(self) -> str | None:
        """Flags high decoy risk for soft-tissue injuries with non-full practice participation."""
        st = self.status.upper()
        if st not in ("QUESTIONABLE", "ACTIVE"):
            return None
        text = f"{self.headline or ''} {self.notes or ''}".lower()
        soft_tissue = ["hamstring", "groin", "calf", "quad", "oblique", "turf toe", "ankle sprain"]
        if not any(k in text for k in soft_tissue):
            return None
        ps = self.practice_status
        if ps == "DNP" or "setback" in text or "friday dnp" in text:
            return "HIGH"
        if ps == "LIMITED" or ps is None:
            return "MODERATE"
        if ps == "FULL":
            return "LOW"
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

    async def enrich_beneficiaries(
        self,
        injuries: list[PlayerInjuryReport],
    ) -> list[PlayerInjuryReport]:
        """Resolves depth chart direct backups/beneficiaries for injured starters."""
        from src.adapters.nfl.depthchart_client import nfl_depthchart_client

        for inj in injuries:
            if inj.position.upper() in ("QB", "RB", "WR", "TE") and (inj.is_out or "QUESTIONABLE" in inj.status.upper()):
                team_abbr = resolve_team_abbrev(inj.team)
                try:
                    chart = await nfl_depthchart_client.fetch_team_depth_chart(team_abbr)
                    if chart:
                        next_up = chart.get_next_man_up(inj.name, inj.position)
                        if next_up:
                            inj.backup_athlete_name = next_up.get("display_name")
                            inj.backup_athlete_id = next_up.get("athlete_id")
                            inj.backup_slot = next_up.get("slot")
                            inj.vacated_opportunity_note = generate_vacated_opportunity_note(
                                inj.position,
                                inj.backup_athlete_name or "Backup",
                                next_up.get("rank", 2),
                            )
                except Exception as e:
                    logger.debug(f"Failed to resolve next man up for {inj.name}: {e}")
        return injuries

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
