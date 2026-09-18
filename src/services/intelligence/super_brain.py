"""NFL Super Brain Intelligence Retrieval Engine.

Provides instant $O(1)$ access to encyclopedic player, team, and DFS data:
- Side-by-side [2025 Full-Season Prior] vs [2026 Realized In-Season] comparisons.
- High-Value Touches (carries inside 5, touches inside 10, targets).
- NextGen tracking: Optical Separation Score (ASS), First-Read %, TPRR, 1D/RR.
- Trench & Scheme Physics: OL/DL collision grades, coverage shells (MOFC vs MOFO), and 4th down coaching indices.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class NFLSuperBrain:
    """Master encyclopedic intelligence engine for NFL stats and DFS game theory."""

    def __init__(self, data_path: Optional[str] = None):
        if data_path:
            self.data_path = Path(data_path)
        else:
            self.data_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "encyclopedia" / "nfl_super_brain_master.json"

        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            logger.warning(f"Super brain data file {self.data_path} not found.")
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading super brain master: {e}")

    def get_player(self, name: str) -> Optional[Dict[str, Any]]:
        """Finds player dossier with fuzzy case-insensitive matching."""
        if not self._data:
            self._load()

        players = self._data.get("players", {})
        norm_query = name.lower().strip()

        # Direct match
        for p_name, profile in players.items():
            if p_name.lower() == norm_query:
                return profile

        # Substring match
        for p_name, profile in players.items():
            if norm_query in p_name.lower() or p_name.lower() in norm_query:
                return profile

        return None

    def compare_players(self, name1: str, name2: str) -> Dict[str, Any]:
        """Generates side-by-side comparison across 2025 and 2026 metrics."""
        p1 = self.get_player(name1)
        p2 = self.get_player(name2)

        if not p1 or not p2:
            return {"error": f"One or both players not found: '{name1}', '{name2}'"}

        return {
            "player_1": {
                "name": p1["name"],
                "pos": p1["pos"],
                "team": p1["team"],
                "2025_prior": p1.get("prior_2025", {}),
                "2026_in_season": p1.get("in_season_2026", {}),
            },
            "player_2": {
                "name": p2["name"],
                "pos": p2["pos"],
                "team": p2["team"],
                "2025_prior": p2.get("prior_2025", {}),
                "2026_in_season": p2.get("in_season_2026", {}),
            }
        }

    def get_team(self, team_abbrev: str) -> Optional[Dict[str, Any]]:
        """Returns complete team trench, coaching, and pace profile."""
        if not self._data:
            self._load()

        teams = self._data.get("teams", {})
        return teams.get(team_abbrev.upper().strip())


super_brain = NFLSuperBrain()
