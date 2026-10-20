import json
import logging
from pathlib import Path
import re
import time
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
LOCAL_INJURIES_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "injuries_live_2026.json"


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


def parse_practice_status(text: str) -> str:
    """Parses practice progression (FULL, LIMITED, DNP, NOT_REPORTED) with negative guards."""
    if not text.strip():
        return "NOT_REPORTED"

    cleaned_text = re.sub(r"\bpractice[- ]squad\b", "", text.lower())
    tokens = set(re.findall(r"\b[a-z0-9]+\b", cleaned_text))

    has_setback = bool(
        re.search(r"(suffered|experienced|had|hit|dealt with|faced)\s+(a\s+)?setback", cleaned_text)
        or re.search(r"setback\s+(in|during|at)\s+practice", cleaned_text)
        or ("setback" in cleaned_text and "barring" not in cleaned_text and "without" not in cleaned_text)
        or "downgrade" in cleaned_text
        or "did not practice friday" in cleaned_text
        or "missed friday" in cleaned_text
        or "held out friday" in cleaned_text
    )

    is_upgraded_to_full = bool(
        re.search(r"\bupgraded\b.*\b(full|fp)\b", cleaned_text)
        or re.search(r"\b(full participant|practiced in full|full practice|practiced fully|full go)\b.*\bfriday\b", cleaned_text)
        or re.search(r"\bfriday\b.*\b(full participant|practiced in full|full practice|practiced fully|full go)\b", cleaned_text)
        or ("full" in cleaned_text and "after" in cleaned_text and ("limited" in cleaned_text or "dnp" in cleaned_text))
    )

    is_upgraded_to_limited = bool(
        re.search(r"\bupgraded\b.*\b(limited|lp)\b", cleaned_text)
        or re.search(r"\bprogressed\b.*\b(limited|lp)\b", cleaned_text)
        or re.search(r"\b(limited participant|limited practice|practiced in limited)\b.*\bfriday\b", cleaned_text)
        or re.search(r"\bfriday\b.*\b(limited participant|limited practice)\b", cleaned_text)
        or ("limited" in cleaned_text and "after" in cleaned_text and "dnp" in cleaned_text)
    )

    if not has_setback:
        if is_upgraded_to_full:
            return "FULL"
        if is_upgraded_to_limited:
            return "LIMITED"

    dnp_indicators = [
        "did not practice", "did not participate", "non-participant", "missed practice",
        "won't practice", "will not practice", "not practicing", "held out of practice",
        "held out from practice", "sidelined from practice", "unable to participate",
        "unable to practice", "hasn't practiced", "sat out practice", "sat out of practice",
        "sat out", "held out", "has not practiced"
    ]
    if (
        has_setback
        or any(ind in cleaned_text for ind in dnp_indicators)
        or "(dnp)" in cleaned_text
        or "dnp" in tokens
    ):
        return "DNP"

    limited_indicators = [
        "limited participant", "limited practice", "was limited in", "was limited at",
        "limited in practice", "limited session", "limited work", "limited basis",
        "in limited fashion", "partially participated", "individual drills",
        "listed as limited"
    ]
    is_game_action = ("action" in cleaned_text or "snaps" in cleaned_text or "yards" in cleaned_text)
    if (
        any(ind in cleaned_text for ind in limited_indicators)
        or "(lp)" in cleaned_text
        or ("lp" in tokens and not is_game_action)
        or ("limited" in cleaned_text and not is_game_action)
    ):
        return "LIMITED"

    full_indicators = [
        "full practice", "full participant", "practiced in full", "practicing in full",
        "practiced without restriction", "cleared for contact", "full go",
        "listed as full"
    ]
    if (
        any(ind in cleaned_text for ind in full_indicators)
        or "(fp)" in cleaned_text
        or "fp" in tokens
    ):
        return "FULL"

    return "NOT_REPORTED"


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
    stored_practice_status: str | None = None
    stored_practice_trend: str | None = None

    @property
    def is_playable(self) -> bool:
        return self.status.upper() in ("ACTIVE", "QUESTIONABLE") and not self.is_out

    @property
    def is_out(self) -> bool:
        st = self.status.upper()
        return (
            st in ("OUT", "DOUBTFUL", "IR", "INACTIVE", "SUSPENDED", "INJURED RESERVE", "PUP", "NFI")
            or "IR" in st
            or "RESERVE" in st
            or "PUP" in st
        )

    @property
    def practice_status(self) -> str | None:
        """Parses practice progression (FULL, LIMITED, DNP) from latest injury notes and headlines."""
        if self.stored_practice_status and self.stored_practice_status.upper() in ("FULL", "LIMITED", "DNP", "NOT_REPORTED"):
            return self.stored_practice_status.upper()

        text = f"{self.headline or ''} {self.notes or ''}".strip()
        if not text:
            return None

        status = parse_practice_status(text)
        return status if status != "NOT_REPORTED" else None

    @property
    def practice_trend(self) -> str | None:
        """Determines practice trajectory (e.g., Upward, Setback, Consecutive DNP, Full)."""
        text = f"{self.headline or ''} {self.notes or ''}".lower()
        if not text.strip():
            return self.stored_practice_trend

        # Disambiguate real setback from "barring any setbacks" or "without setbacks"
        has_setback = bool(
            re.search(r"(suffered|experienced|had|hit|dealt with|faced)\s+(a\s+)?setback", text)
            or re.search(r"setback\s+(in|during|at)\s+practice", text)
            or ("setback" in text and "barring" not in text and "without" not in text)
        )
        if has_setback or "downgrade" in text or ("dnp" in text and "after" in text and ("limited" in text or "full" in text)):
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
        return self.stored_practice_trend

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
        if ps == "LIMITED" or ps is None or ps == "NOT_REPORTED":
            return "MODERATE"
        if ps == "FULL":
            return "LOW"
        return None


# Aliases for contractual compatibility
InjuryReport = PlayerInjuryReport


class TeamInjuries(BaseModel):
    """Container for a team's collection of active injury reports."""
    pro_team: str
    team_name: str | None = None
    last_updated: float = Field(default_factory=time.time)
    injuries: list[PlayerInjuryReport] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.injuries)

    @property
    def out_count(self) -> int:
        return sum(1 for i in self.injuries if i.is_out)

    @property
    def questionable_count(self) -> int:
        return sum(1 for i in self.injuries if "QUESTIONABLE" in i.status.upper() and not i.is_out)


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

    def _load_from_disk(self) -> dict[int, PlayerInjuryReport]:
        """Loads and parses injury reports from data/injuries_live_2026.json."""
        if not LOCAL_INJURIES_PATH.exists():
            logger.error(f"Local injury cache not found at {LOCAL_INJURIES_PATH}")
            return {}

        try:
            with open(LOCAL_INJURIES_PATH, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read/parse local injury cache from {LOCAL_INJURIES_PATH}: {e}")
            return {}

        records: list[dict[str, Any]] = []
        if isinstance(raw_data, dict):
            if "injuries" in raw_data and isinstance(raw_data["injuries"], list):
                records = raw_data["injuries"]
            else:
                for val in raw_data.values():
                    if isinstance(val, list):
                        records.extend(val)
                    elif isinstance(val, dict) and "injuries" in val:
                        records.extend(val["injuries"])
        elif isinstance(raw_data, list):
            records = raw_data

        results: dict[int, PlayerInjuryReport] = {}
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                continue
            try:
                ath_id = int(item.get("athlete_id") or 0)
                name = str(item.get("name") or "Unknown Player").strip()
                team = str(item.get("team") or "Unknown Team").strip()
                pos = str(item.get("position") or "UNK").strip()
                status_str = str(item.get("status") or "QUESTIONABLE").upper()

                if ath_id <= 0:
                    ath_id = (abs(hash(f"{name}_{team}_{idx}")) % 10_000_000) + 90_000_000

                headline = item.get("headline") or item.get("short_comment")
                notes = item.get("notes") or item.get("long_comment")
                date_str = item.get("date") or item.get("updated")
                backup_name = item.get("backup_athlete_name") or item.get("backup_player_name")
                backup_id = item.get("backup_athlete_id") or item.get("backup_player_id")
                if backup_id is not None:
                    try:
                        backup_id = int(backup_id)
                    except (ValueError, TypeError):
                        backup_id = None
                backup_slot = item.get("backup_slot")
                vacated_note = item.get("vacated_opportunity_note")
                stored_ps = item.get("practice_status")
                stored_pt = item.get("practice_trend")

                results[ath_id] = PlayerInjuryReport(
                    athlete_id=ath_id,
                    name=name,
                    position=pos,
                    team=team,
                    status=status_str,
                    headline=headline,
                    notes=notes,
                    date=date_str,
                    backup_athlete_name=backup_name,
                    backup_athlete_id=backup_id,
                    backup_slot=backup_slot,
                    vacated_opportunity_note=vacated_note,
                    stored_practice_status=stored_ps,
                    stored_practice_trend=stored_pt,
                )
            except Exception as parse_err:
                logger.debug(f"Failed to parse cached injury item {item}: {parse_err}")

        logger.info(f"Loaded {len(results)} injury reports from local disk cache ({LOCAL_INJURIES_PATH.name})")
        return results

    async def enrich_beneficiaries(
        self,
        injuries: list[PlayerInjuryReport],
    ) -> list[PlayerInjuryReport]:
        """Resolves depth chart direct backups/beneficiaries for injured starters."""
        from src.adapters.nfl.depthchart_client import nfl_depthchart_client

        ruled_out_names = {i.name for i in injuries if i.is_out}

        for inj in injuries:
            if inj.position.upper() in ("QB", "RB", "WR", "TE") and (inj.is_out or "QUESTIONABLE" in inj.status.upper()):
                team_abbr = resolve_team_abbrev(inj.team)
                try:
                    chart = await nfl_depthchart_client.fetch_team_depth_chart(team_abbr)
                    if chart:
                        next_up = chart.get_next_man_up(inj.name, inj.position, excluded_names=ruled_out_names)
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
        """Fetch all official NFL injury updates indexed by athlete ID with 5-min TTL cache and disk fallback."""
        now = time.time()
        if not force and self._cache_time > 0 and (now - self._cache_time) < self.cache_ttl:
            return self._cache

        data = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(ESPN_INJURIES_URL)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch live injuries from ESPN: {e}. Falling back to local disk cache.")

        if not data or not data.get("injuries"):
            disk_results = self._load_from_disk()
            if disk_results:
                self._cache = disk_results
                self._cache_time = now
                return disk_results
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
                        for link in (athlete.get("links") or []):
                            if not isinstance(link, dict):
                                continue
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

        if not results:
            logger.warning("ESPN returned 0 parsed injuries; falling back to local disk cache.")
            disk_results = self._load_from_disk()
            if disk_results:
                self._cache = disk_results
                self._cache_time = now
                return disk_results

        self._cache = results
        self._cache_time = now
        return results

    async def fetch_team_injuries(self, team: str, force: bool = False) -> TeamInjuries:
        """Fetch injuries filtered for a single NFL team."""
        all_inj = await self.fetch_injuries(force=force)
        team_clean = resolve_team_abbrev(team)
        matched = [i for i in all_inj.values() if resolve_team_abbrev(i.team) == team_clean]
        return TeamInjuries(pro_team=team_clean, injuries=matched)

    async def fetch_injuries_by_team(self, force: bool = False) -> dict[str, list[PlayerInjuryReport]]:
        """Returns all injuries grouped by canonical team abbreviation."""
        all_inj = await self.fetch_injuries(force=force)
        grouped: dict[str, list[PlayerInjuryReport]] = {}
        for inj in all_inj.values():
            team_abbr = resolve_team_abbrev(inj.team)
            grouped.setdefault(team_abbr, []).append(inj)
        return grouped


nfl_injuries_client = NFLInjuriesClient()
