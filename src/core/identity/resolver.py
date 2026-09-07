"""Canonical Player Identity Resolver mapping ESPN, GSIS/nflverse, Sleeper, and clean names."""

import csv
import io
import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any
from pydantic import BaseModel


logger = logging.getLogger(__name__)

DYNASTY_PROCESS_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
LOCAL_CROSSWALK_CACHE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "player_crosswalk.json"


def normalize_name(name: str) -> str:
    """Normalize player name: lowercase, strip punctuation, remove suffixes (Jr, Sr, II, III)."""
    if not name:
        return ""
    cleaned = name.lower().strip()
    # Strip periods, apostrophes, hyphens
    cleaned = re.sub(r"[\.']", "", cleaned)
    cleaned = re.sub(r"[-]", " ", cleaned)
    # Strip suffixes
    cleaned = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class CanonicalPlayer(BaseModel):
    canonical_id: str
    espn_id: int | None = None
    gsis_id: str | None = None
    sleeper_id: str | None = None
    full_name: str
    normalized_name: str
    position: str
    team: str


class PlayerIdentityResolver:
    """Cross-references player IDs across ESPN, NFL/nflverse, and Sleeper."""

    def __init__(self):
        self._by_espn_id: dict[int, CanonicalPlayer] = {}
        self._by_gsis_id: dict[str, CanonicalPlayer] = {}
        self._by_sleeper_id: dict[str, CanonicalPlayer] = {}
        self._by_name_pos: dict[str, CanonicalPlayer] = {}
        self._initialized = False

    def sync_crosswalk(self, timeout: float = 6.0) -> bool:
        """Download latest DynastyProcess crosswalk and cache to local JSON file."""
        try:
            req = urllib.request.Request(
                DYNASTY_PROCESS_URL,
                headers={"User-Agent": "ApexFantasyAssistant/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8")

            reader = csv.DictReader(io.StringIO(content))
            mapped_players: list[dict[str, Any]] = []

            for row in reader:
                pos = (row.get("position") or "").strip().upper()
                if pos not in ("QB", "RB", "WR", "TE", "K", "FB", "D/ST", "DST"):
                    continue

                espn_raw = (row.get("espn_id") or "").strip()
                gsis_raw = (row.get("gsis_id") or "").strip()
                sleeper_raw = (row.get("sleeper_id") or "").strip()
                name = (row.get("name") or "").strip()

                espn_id: int | None = None
                if espn_raw and espn_raw.isdigit():
                    espn_id = int(espn_raw)

                if not espn_id and not gsis_raw and not sleeper_raw:
                    continue
                if not name:
                    continue

                cid = f"CAN_{espn_id}" if espn_id else f"CAN_GSIS_{gsis_raw}"
                cp_dict = {
                    "canonical_id": cid,
                    "espn_id": espn_id,
                    "gsis_id": gsis_raw if gsis_raw and gsis_raw != "NA" else None,
                    "sleeper_id": sleeper_raw if sleeper_raw and sleeper_raw != "NA" else None,
                    "full_name": name,
                    "normalized_name": normalize_name(name),
                    "position": "D/ST" if pos in ("DST", "DEF") else pos,
                    "team": (row.get("team") or "FA").strip().upper(),
                }
                mapped_players.append(cp_dict)

            if mapped_players:
                LOCAL_CROSSWALK_CACHE.parent.mkdir(parents=True, exist_ok=True)
                with open(LOCAL_CROSSWALK_CACHE, "w", encoding="utf-8") as f:
                    json.dump(mapped_players, f)
                logger.info(f"Successfully synced and cached {len(mapped_players)} player crosswalk identities.")
                return True
        except Exception as e:
            logger.warning(f"Could not sync player crosswalk from DynastyProcess: {e}")
        return False

    def initialize(self) -> None:
        """Load crosswalk from local cache or online source."""
        if self._initialized:
            return

        # 1. Attempt to load local JSON cache first
        if LOCAL_CROSSWALK_CACHE.exists():
            try:
                with open(LOCAL_CROSSWALK_CACHE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    cp = CanonicalPlayer.model_validate(item)
                    self._register(cp)
                self._initialized = True
                logger.info(f"Loaded {len(self._by_espn_id)} player mappings from local cache.")
                return
            except Exception as e:
                logger.warning(f"Could not load local player crosswalk cache: {e}")

        # 2. Attempt online download and populate cache
        synced = self.sync_crosswalk()
        if synced and LOCAL_CROSSWALK_CACHE.exists():
            try:
                with open(LOCAL_CROSSWALK_CACHE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    cp = CanonicalPlayer.model_validate(item)
                    self._register(cp)
                self._initialized = True
                return
            except Exception:
                pass

        # 3. Fallback to core 2026 starter list when offline
        self._load_core_2026_baseline()
        self._initialized = True


    def _register(self, cp: CanonicalPlayer) -> None:
        if cp.espn_id:
            self._by_espn_id[cp.espn_id] = cp
        if cp.gsis_id:
            self._by_gsis_id[cp.gsis_id] = cp
        if cp.sleeper_id:
            self._by_sleeper_id[cp.sleeper_id] = cp

        def _should_replace(existing: CanonicalPlayer | None, new_p: CanonicalPlayer) -> bool:
            if existing is None:
                return True
            # Prefer player with real ESPN / Sleeper ID
            existing_score = (2 if existing.espn_id else 0) + (1 if existing.sleeper_id else 0) + (1 if existing.team not in ("FA", "FA*") else 0)
            new_score = (2 if new_p.espn_id else 0) + (1 if new_p.sleeper_id else 0) + (1 if new_p.team not in ("FA", "FA*") else 0)
            return new_score > existing_score

        key = f"{cp.normalized_name}_{cp.position.upper()}"
        if _should_replace(self._by_name_pos.get(key), cp):
            self._by_name_pos[key] = cp

        if not hasattr(self, "_by_name"):
            self._by_name = {}
        if _should_replace(self._by_name.get(cp.normalized_name), cp):
            self._by_name[cp.normalized_name] = cp

    def resolve(
        self,
        espn_id: int | None = None,
        gsis_id: str | None = None,
        sleeper_id: str | None = None,
        name: str | None = None,
        position: str | None = None,
        team: str | None = None,
    ) -> CanonicalPlayer | None:
        """Resolve player by ID hierarchy or normalized name + position."""
        if not self._initialized:
            self.initialize()

        if espn_id and espn_id in self._by_espn_id:
            return self._by_espn_id[espn_id]
        if gsis_id and gsis_id in self._by_gsis_id:
            return self._by_gsis_id[gsis_id]
        if sleeper_id and sleeper_id in self._by_sleeper_id:
            return self._by_sleeper_id[sleeper_id]

        if name:
            norm_name = normalize_name(name)
            if position:
                key = f"{norm_name}_{position.upper()}"
                if key in self._by_name_pos:
                    return self._by_name_pos[key]
            if hasattr(self, "_by_name") and norm_name in self._by_name:
                return self._by_name[norm_name]

        # If not found, synthesize on-the-fly canonical player
        if espn_id and name:
            canonical = CanonicalPlayer(
                canonical_id=f"CAN_{espn_id}",
                espn_id=espn_id,
                full_name=name,
                normalized_name=normalize_name(name),
                position=position or "UNK",
                team=team or "FA",
            )
            self._register(canonical)
            return canonical

        return None

    def _load_core_2026_baseline(self) -> None:
        """Load curated baseline of 2026 fantasy stars."""
        baseline = [
            ("4426348", "00-0039912", "10222", "Jayden Daniels", "QB", "WSH"),
            ("4361579", "00-0038120", "9221", "Bijan Robinson", "RB", "ATL"),
            ("4241457", "00-0038562", "9226", "Jahmyr Gibbs", "RB", "DET"),
            ("4362628", "00-0036963", "7523", "Amon-Ra St. Brown", "WR", "DET"),
            ("4430878", "00-0039910", "11632", "Marvin Harrison Jr.", "WR", "ARI"),
            ("4430027", "00-0039889", "11628", "Brock Bowers", "TE", "LV"),
            ("4426515", "00-0039891", "11635", "Malik Nabers", "WR", "NYG"),
            ("4374302", "00-0038564", "9228", "De'Von Achane", "RB", "MIA"),
            ("4258183", "00-0037240", "8138", "Drake London", "WR", "ATL"),
            ("4242335", "00-0038668", "10444", "Brandon Aubrey", "K", "DAL"),
            ("3918298", "00-0033873", "4046", "Patrick Mahomes", "QB", "KC"),
            ("4040715", "00-0034796", "4881", "Lamar Jackson", "QB", "BAL"),
            ("4046675", "00-0034844", "5012", "Saquon Barkley", "RB", "PHI"),
            ("4242214", "00-0036322", "6797", "Justin Jefferson", "WR", "MIN"),
            ("4362629", "00-0036961", "7564", "Ja'Marr Chase", "WR", "CIN"),
            ("4240589", "00-0036900", "7553", "CeeDee Lamb", "WR", "DAL"),
            ("4361529", "00-0038400", "9224", "Puka Nacua", "WR", "LAR"),
            ("4426384", "00-0039918", "11630", "Caleb Williams", "QB", "CHI"),
            ("4241389", "00-0038102", "8136", "Garrett Wilson", "WR", "NYJ"),
            ("4360438", "00-0038599", "9225", "Sam LaPorta", "TE", "DET"),
            ("3117251", "00-0033045", "3678", "Christian McCaffrey", "RB", "SF"),
            ("4429013", "00-0039908", "11634", "Rome Odunze", "WR", "CHI"),
            ("4038941", "00-0034857", "4984", "Josh Allen", "QB", "BUF"),
            ("4241474", "00-0037844", "8150", "Kyren Williams", "RB", "LAR"),
            ("4361411", "00-0038538", "9229", "Trey McBride", "TE", "ARI"),
        ]

        for espn, gsis, sleeper, name, pos, tm in baseline:
            cp = CanonicalPlayer(
                canonical_id=f"CAN_{espn}",
                espn_id=int(espn),
                gsis_id=gsis,
                sleeper_id=sleeper,
                full_name=name,
                normalized_name=normalize_name(name),
                position=pos,
                team=tm,
            )
            self._register(cp)


# Singleton instance
player_resolver = PlayerIdentityResolver()
