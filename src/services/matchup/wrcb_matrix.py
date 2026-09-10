"""WR vs CB Matchup and Shadow Coverage Matrix (PFF-Style Advanced Secondary Analytics).

Analyzes wide receiver route alignment (LWR, RWR, Slot) against opposing cornerback depth
charts, coverage grades, shadow tracking, and matchup advantage ratings.
"""

import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CornerbackProfile(BaseModel):
    name: str
    team: str
    slot_role: str  # "LWR", "RWR", "SLOT", "SHADOW"
    coverage_grade: float  # 0 to 100 (85+ Elite, 70-84 Above Average, 60-69 Vulnerable, <60 Burnable)
    is_shadow: bool = False
    targets_per_route_allowed: float = 0.18
    fpts_per_route_allowed: float = 0.28
    catch_rate_allowed: float = 0.62
    is_backup_replacement: bool = False
    original_starter_name: str | None = None
    injury_note: str | None = None


class WRAlignmentProfile(BaseModel):
    pct_slot: float = 0.25
    pct_wide: float = 0.75
    target_share: float = 0.22
    route_win_rate: float = 0.72


class WRCBMatchupAnalysis(BaseModel):
    player_id: int
    full_name: str
    position: str = "WR"
    pro_team: str
    opponent: str
    projected_points: float
    alignment: WRAlignmentProfile
    primary_cb: CornerbackProfile
    secondary_cb: CornerbackProfile | None = None
    slot_cb: CornerbackProfile | None = None
    is_shadow_projected: bool = False
    advantage_score: float = 0.0  # -30.0% to +30.0%
    advantage_rating: str  # SHADOW_LOCKDOWN, TOUGH_PERIMETER, NEUTRAL, FAVORABLE, SLOT_MISMATCH, MAJOR_ADVANTAGE
    tactical_takeaway: str
    is_user_rostered: bool = False
    is_user_starter: bool = False


# 32 NFL Team Cornerback Depth Charts (CB1, CB2, Slot CB)
NFL_CB_DEPTH_CHARTS: dict[str, dict[str, CornerbackProfile]] = {
    "DEN": {
        "outside1": CornerbackProfile(name="Patrick Surtain II", team="DEN", slot_role="SHADOW", coverage_grade=92.5, is_shadow=True, targets_per_route_allowed=0.12, fpts_per_route_allowed=0.16, catch_rate_allowed=0.48),
        "outside2": CornerbackProfile(name="Riley Moss", team="DEN", slot_role="RWR", coverage_grade=74.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.29, catch_rate_allowed=0.61),
        "slot": CornerbackProfile(name="Ja'Quan McMillian", team="DEN", slot_role="SLOT", coverage_grade=76.5, is_shadow=False, targets_per_route_allowed=0.17, fpts_per_route_allowed=0.25, catch_rate_allowed=0.59),
    },
    "NYJ": {
        "outside1": CornerbackProfile(name="Sauce Gardner", team="NYJ", slot_role="LWR", coverage_grade=91.0, is_shadow=True, targets_per_route_allowed=0.13, fpts_per_route_allowed=0.18, catch_rate_allowed=0.50),
        "outside2": CornerbackProfile(name="D.J. Reed", team="NYJ", slot_role="RWR", coverage_grade=82.5, is_shadow=False, targets_per_route_allowed=0.17, fpts_per_route_allowed=0.24, catch_rate_allowed=0.57),
        "slot": CornerbackProfile(name="Michael Carter II", team="NYJ", slot_role="SLOT", coverage_grade=80.0, is_shadow=False, targets_per_route_allowed=0.16, fpts_per_route_allowed=0.23, catch_rate_allowed=0.58),
    },
    "CHI": {
        "outside1": CornerbackProfile(name="Jaylon Johnson", team="CHI", slot_role="SHADOW", coverage_grade=90.0, is_shadow=True, targets_per_route_allowed=0.13, fpts_per_route_allowed=0.19, catch_rate_allowed=0.51),
        "outside2": CornerbackProfile(name="Tyrique Stevenson", team="CHI", slot_role="RWR", coverage_grade=69.0, is_shadow=False, targets_per_route_allowed=0.21, fpts_per_route_allowed=0.33, catch_rate_allowed=0.64),
        "slot": CornerbackProfile(name="Kyler Gordon", team="CHI", slot_role="SLOT", coverage_grade=77.0, is_shadow=False, targets_per_route_allowed=0.16, fpts_per_route_allowed=0.24, catch_rate_allowed=0.58),
    },
    "KC": {
        "outside1": CornerbackProfile(name="Trent McDuffie", team="KC", slot_role="SHADOW", coverage_grade=88.5, is_shadow=True, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.21, catch_rate_allowed=0.54),
        "outside2": CornerbackProfile(name="Nazeeh Johnson", team="KC", slot_role="RWR", coverage_grade=69.5, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.31, catch_rate_allowed=0.63),
        "slot": CornerbackProfile(name="Chamarri Conner", team="KC", slot_role="SLOT", coverage_grade=71.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.62),
    },
    "BAL": {
        "outside1": CornerbackProfile(name="Marlon Humphrey", team="BAL", slot_role="SHADOW", coverage_grade=86.0, is_shadow=True, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.22, catch_rate_allowed=0.55),
        "outside2": CornerbackProfile(name="Nate Wiggins", team="BAL", slot_role="RWR", coverage_grade=74.5, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.29, catch_rate_allowed=0.60),
        "slot": CornerbackProfile(name="Arthur Maulet", team="BAL", slot_role="SLOT", coverage_grade=68.0, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.32, catch_rate_allowed=0.65),
    },
    "CLE": {
        "outside1": CornerbackProfile(name="Denzel Ward", team="CLE", slot_role="SHADOW", coverage_grade=88.0, is_shadow=True, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.20, catch_rate_allowed=0.52),
        "outside2": CornerbackProfile(name="Martin Emerson Jr.", team="CLE", slot_role="RWR", coverage_grade=74.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.30, catch_rate_allowed=0.60),
        "slot": CornerbackProfile(name="Greg Newsome II", team="CLE", slot_role="SLOT", coverage_grade=75.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.59),
    },
    "NE": {
        "outside1": CornerbackProfile(name="Christian Gonzalez", team="NE", slot_role="SHADOW", coverage_grade=87.5, is_shadow=True, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.20, catch_rate_allowed=0.53),
        "outside2": CornerbackProfile(name="Jonathan Jones", team="NE", slot_role="RWR", coverage_grade=71.0, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.32, catch_rate_allowed=0.63),
        "slot": CornerbackProfile(name="Marcus Jones", team="NE", slot_role="SLOT", coverage_grade=72.5, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.28, catch_rate_allowed=0.61),
    },
    "PIT": {
        "outside1": CornerbackProfile(name="Joey Porter Jr.", team="PIT", slot_role="SHADOW", coverage_grade=85.0, is_shadow=True, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.22, catch_rate_allowed=0.53),
        "outside2": CornerbackProfile(name="Donte Jackson", team="PIT", slot_role="RWR", coverage_grade=72.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.30, catch_rate_allowed=0.61),
        "slot": CornerbackProfile(name="Beanie Bishop Jr.", team="PIT", slot_role="SLOT", coverage_grade=64.0, is_shadow=False, targets_per_route_allowed=0.22, fpts_per_route_allowed=0.38, catch_rate_allowed=0.68),
    },
    "HOU": {
        "outside1": CornerbackProfile(name="Derek Stingley Jr.", team="HOU", slot_role="LWR", coverage_grade=88.0, is_shadow=False, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.21, catch_rate_allowed=0.52),
        "outside2": CornerbackProfile(name="Kamari Lassiter", team="HOU", slot_role="RWR", coverage_grade=75.5, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.28, catch_rate_allowed=0.59),
        "slot": CornerbackProfile(name="Jalen Pitre", team="HOU", slot_role="SLOT", coverage_grade=73.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.61),
    },
    "PHI": {
        "outside1": CornerbackProfile(name="Quinyon Mitchell", team="PHI", slot_role="LWR", coverage_grade=82.5, is_shadow=False, targets_per_route_allowed=0.16, fpts_per_route_allowed=0.24, catch_rate_allowed=0.56),
        "outside2": CornerbackProfile(name="Darius Slay", team="PHI", slot_role="RWR", coverage_grade=78.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.59),
        "slot": CornerbackProfile(name="Cooper DeJean", team="PHI", slot_role="SLOT", coverage_grade=81.5, is_shadow=False, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.22, catch_rate_allowed=0.56),
    },
    "DET": {
        "outside1": CornerbackProfile(name="Terrion Arnold", team="DET", slot_role="LWR", coverage_grade=73.5, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.31, catch_rate_allowed=0.63),
        "outside2": CornerbackProfile(name="Carlton Davis III", team="DET", slot_role="RWR", coverage_grade=74.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.30, catch_rate_allowed=0.61),
        "slot": CornerbackProfile(name="Brian Branch", team="DET", slot_role="SLOT", coverage_grade=85.0, is_shadow=False, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.20, catch_rate_allowed=0.55),
    },
    "BUF": {
        "outside1": CornerbackProfile(name="Christian Benford", team="BUF", slot_role="LWR", coverage_grade=84.5, is_shadow=False, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.23, catch_rate_allowed=0.55),
        "outside2": CornerbackProfile(name="Rasul Douglas", team="BUF", slot_role="RWR", coverage_grade=80.0, is_shadow=False, targets_per_route_allowed=0.17, fpts_per_route_allowed=0.26, catch_rate_allowed=0.58),
        "slot": CornerbackProfile(name="Taron Johnson", team="BUF", slot_role="SLOT", coverage_grade=85.5, is_shadow=False, targets_per_route_allowed=0.14, fpts_per_route_allowed=0.21, catch_rate_allowed=0.56),
    },
    "DAL": {
        "outside1": CornerbackProfile(name="DaRon Bland", team="DAL", slot_role="LWR", coverage_grade=82.0, is_shadow=False, targets_per_route_allowed=0.17, fpts_per_route_allowed=0.25, catch_rate_allowed=0.57),
        "outside2": CornerbackProfile(name="Trevon Diggs", team="DAL", slot_role="RWR", coverage_grade=79.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.28, catch_rate_allowed=0.58),
        "slot": CornerbackProfile(name="Jourdan Lewis", team="DAL", slot_role="SLOT", coverage_grade=72.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.29, catch_rate_allowed=0.62),
    },
    "SF": {
        "outside1": CornerbackProfile(name="Charvarius Ward", team="SF", slot_role="LWR", coverage_grade=83.0, is_shadow=False, targets_per_route_allowed=0.16, fpts_per_route_allowed=0.24, catch_rate_allowed=0.56),
        "outside2": CornerbackProfile(name="Isaac Yiadom", team="SF", slot_role="RWR", coverage_grade=71.0, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.31, catch_rate_allowed=0.62),
        "slot": CornerbackProfile(name="Deommodore Lenoir", team="SF", slot_role="SLOT", coverage_grade=80.0, is_shadow=False, targets_per_route_allowed=0.16, fpts_per_route_allowed=0.23, catch_rate_allowed=0.57),
    },
    "TEN": {
        "outside1": CornerbackProfile(name="L'Jarius Sneed", team="TEN", slot_role="SHADOW", coverage_grade=85.0, is_shadow=True, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.22, catch_rate_allowed=0.54),
        "outside2": CornerbackProfile(name="Chidobe Awuzie", team="TEN", slot_role="RWR", coverage_grade=72.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.30, catch_rate_allowed=0.61),
        "slot": CornerbackProfile(name="Roger McCreary", team="TEN", slot_role="SLOT", coverage_grade=74.0, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.60),
    },
    "WSH": {
        "outside1": CornerbackProfile(name="Benjamin St-Juste", team="WSH", slot_role="LWR", coverage_grade=61.0, is_shadow=False, targets_per_route_allowed=0.24, fpts_per_route_allowed=0.42, catch_rate_allowed=0.69),
        "outside2": CornerbackProfile(name="Noah Igbinoghene", team="WSH", slot_role="RWR", coverage_grade=60.0, is_shadow=False, targets_per_route_allowed=0.25, fpts_per_route_allowed=0.44, catch_rate_allowed=0.71),
        "slot": CornerbackProfile(name="Mike Sainristil", team="WSH", slot_role="SLOT", coverage_grade=68.5, is_shadow=False, targets_per_route_allowed=0.20, fpts_per_route_allowed=0.31, catch_rate_allowed=0.64),
    },
    "CAR": {
        "outside1": CornerbackProfile(name="Jaycee Horn", team="CAR", slot_role="SHADOW", coverage_grade=84.0, is_shadow=True, targets_per_route_allowed=0.15, fpts_per_route_allowed=0.23, catch_rate_allowed=0.54),
        "outside2": CornerbackProfile(name="Michael Jackson", team="CAR", slot_role="RWR", coverage_grade=64.0, is_shadow=False, targets_per_route_allowed=0.22, fpts_per_route_allowed=0.37, catch_rate_allowed=0.67),
        "slot": CornerbackProfile(name="Troy Hill", team="CAR", slot_role="SLOT", coverage_grade=63.0, is_shadow=False, targets_per_route_allowed=0.23, fpts_per_route_allowed=0.39, catch_rate_allowed=0.68),
    },
    "ARI": {
        "outside1": CornerbackProfile(name="Sean Murphy-Bunting", team="ARI", slot_role="LWR", coverage_grade=67.0, is_shadow=False, targets_per_route_allowed=0.21, fpts_per_route_allowed=0.34, catch_rate_allowed=0.65),
        "outside2": CornerbackProfile(name="Starling Thomas V", team="ARI", slot_role="RWR", coverage_grade=62.0, is_shadow=False, targets_per_route_allowed=0.24, fpts_per_route_allowed=0.41, catch_rate_allowed=0.69),
        "slot": CornerbackProfile(name="Garrett Williams", team="ARI", slot_role="SLOT", coverage_grade=71.0, is_shadow=False, targets_per_route_allowed=0.19, fpts_per_route_allowed=0.28, catch_rate_allowed=0.62),
    },
    "NYG": {
        "outside1": CornerbackProfile(name="Deonte Banks", team="NYG", slot_role="SHADOW", coverage_grade=69.0, is_shadow=True, targets_per_route_allowed=0.21, fpts_per_route_allowed=0.34, catch_rate_allowed=0.64),
        "outside2": CornerbackProfile(name="Cor'Dale Flott", team="NYG", slot_role="RWR", coverage_grade=63.0, is_shadow=False, targets_per_route_allowed=0.23, fpts_per_route_allowed=0.38, catch_rate_allowed=0.67),
        "slot": CornerbackProfile(name="Dru Phillips", team="NYG", slot_role="SLOT", coverage_grade=71.5, is_shadow=False, targets_per_route_allowed=0.18, fpts_per_route_allowed=0.27, catch_rate_allowed=0.61),
    },
}

# Generic fallback profile for teams not explicitly detailed above
DEFAULT_FALLBACK_CB_ROOM: dict[str, CornerbackProfile] = {
    "outside1": CornerbackProfile(name="Primary Outside CB", team="UNK", slot_role="LWR", coverage_grade=72.0, is_shadow=False),
    "outside2": CornerbackProfile(name="Secondary Outside CB", team="UNK", slot_role="RWR", coverage_grade=68.0, is_shadow=False),
    "slot": CornerbackProfile(name="Slot Nickel CB", team="UNK", slot_role="SLOT", coverage_grade=70.0, is_shadow=False),
}

# Wide Receiver Route Alignment Profiles
KNOWN_WR_ALIGNMENTS: dict[str, WRAlignmentProfile] = {
    "ceedee lamb": WRAlignmentProfile(pct_slot=0.55, pct_wide=0.45, target_share=0.29, route_win_rate=0.82),
    "amon-ra st. brown": WRAlignmentProfile(pct_slot=0.62, pct_wide=0.38, target_share=0.28, route_win_rate=0.84),
    "tyreek hill": WRAlignmentProfile(pct_slot=0.38, pct_wide=0.62, target_share=0.28, route_win_rate=0.85),
    "justin jefferson": WRAlignmentProfile(pct_slot=0.26, pct_wide=0.74, target_share=0.30, route_win_rate=0.88),
    "ja'marr chase": WRAlignmentProfile(pct_slot=0.22, pct_wide=0.78, target_share=0.28, route_win_rate=0.86),
    "malik nabers": WRAlignmentProfile(pct_slot=0.24, pct_wide=0.76, target_share=0.31, route_win_rate=0.83),
    "nico collins": WRAlignmentProfile(pct_slot=0.20, pct_wide=0.80, target_share=0.27, route_win_rate=0.85),
    "drake london": WRAlignmentProfile(pct_slot=0.18, pct_wide=0.82, target_share=0.26, route_win_rate=0.80),
    "marvin harrison jr.": WRAlignmentProfile(pct_slot=0.16, pct_wide=0.84, target_share=0.25, route_win_rate=0.79),
    "garrett wilson": WRAlignmentProfile(pct_slot=0.28, pct_wide=0.72, target_share=0.27, route_win_rate=0.81),
    "a.j. brown": WRAlignmentProfile(pct_slot=0.19, pct_wide=0.81, target_share=0.28, route_win_rate=0.86),
    "puka nacua": WRAlignmentProfile(pct_slot=0.35, pct_wide=0.65, target_share=0.27, route_win_rate=0.83),
    "chris godwin": WRAlignmentProfile(pct_slot=0.58, pct_wide=0.42, target_share=0.24, route_win_rate=0.81),
    "cooper kupp": WRAlignmentProfile(pct_slot=0.52, pct_wide=0.48, target_share=0.26, route_win_rate=0.80),
    "rashee rice": WRAlignmentProfile(pct_slot=0.56, pct_wide=0.44, target_share=0.26, route_win_rate=0.83),
    "jaxon smith-njigba": WRAlignmentProfile(pct_slot=0.68, pct_wide=0.32, target_share=0.22, route_win_rate=0.79),
    "jaylen waddle": WRAlignmentProfile(pct_slot=0.32, pct_wide=0.68, target_share=0.22, route_win_rate=0.80),
    "devonta smith": WRAlignmentProfile(pct_slot=0.34, pct_wide=0.66, target_share=0.22, route_win_rate=0.81),
    "zay flowers": WRAlignmentProfile(pct_slot=0.36, pct_wide=0.64, target_share=0.25, route_win_rate=0.80),
    "tank dell": WRAlignmentProfile(pct_slot=0.30, pct_wide=0.70, target_share=0.20, route_win_rate=0.78),
    "brian thomas jr.": WRAlignmentProfile(pct_slot=0.14, pct_wide=0.86, target_share=0.22, route_win_rate=0.79),
    "terry mclaurin": WRAlignmentProfile(pct_slot=0.18, pct_wide=0.82, target_share=0.25, route_win_rate=0.81),
    "dj moore": WRAlignmentProfile(pct_slot=0.26, pct_wide=0.74, target_share=0.24, route_win_rate=0.80),
    "george pickens": WRAlignmentProfile(pct_slot=0.12, pct_wide=0.88, target_share=0.25, route_win_rate=0.79),
    "dk metcalf": WRAlignmentProfile(pct_slot=0.15, pct_wide=0.85, target_share=0.24, route_win_rate=0.81),
    "tee higgins": WRAlignmentProfile(pct_slot=0.16, pct_wide=0.84, target_share=0.23, route_win_rate=0.80),
    "ladd mcconkey": WRAlignmentProfile(pct_slot=0.65, pct_wide=0.35, target_share=0.23, route_win_rate=0.80),
    "khalil shakir": WRAlignmentProfile(pct_slot=0.72, pct_wide=0.28, target_share=0.19, route_win_rate=0.83),
    "wan'dale robinson": WRAlignmentProfile(pct_slot=0.75, pct_wide=0.25, target_share=0.21, route_win_rate=0.78),
    "courtland sutton": WRAlignmentProfile(pct_slot=0.18, pct_wide=0.82, target_share=0.23, route_win_rate=0.76),
    "amari cooper": WRAlignmentProfile(pct_slot=0.18, pct_wide=0.82, target_share=0.24, route_win_rate=0.80),
    "keon coleman": WRAlignmentProfile(pct_slot=0.14, pct_wide=0.86, target_share=0.18, route_win_rate=0.75),
    "jerry jeudy": WRAlignmentProfile(pct_slot=0.38, pct_wide=0.62, target_share=0.20, route_win_rate=0.76),
    "rome odunze": WRAlignmentProfile(pct_slot=0.20, pct_wide=0.80, target_share=0.19, route_win_rate=0.76),
}


from src.services.matchup.pff_service import pff_scouting_service


class WRCBAnalyzer:
    """Evaluates WR route alignments vs opposing CB personnel to detect shadow lockdown & slot mismatches."""

    def get_cb_room(
        self, opp_team: str, inactive_player_names: set[str] | None = None
    ) -> dict[str, CornerbackProfile]:
        team = opp_team.upper().strip()
        pff_room = pff_scouting_service.get_active_cb_room(team, inactive_player_names=inactive_player_names)
        if pff_room:
            result: dict[str, CornerbackProfile] = {}
            for k, v in pff_room.items():
                result[k] = CornerbackProfile(
                    name=v.name,
                    team=team,
                    slot_role=v.role,
                    coverage_grade=v.grade,
                    is_shadow=v.is_shadow,
                    targets_per_route_allowed=v.targets_per_route,
                    fpts_per_route_allowed=v.fpts_per_route,
                    catch_rate_allowed=v.catch_rate,
                    is_backup_replacement=v.is_backup_replacement,
                    original_starter_name=v.original_starter_name,
                    injury_note=v.injury_note,
                )
            return result
        return NFL_CB_DEPTH_CHARTS.get(team, DEFAULT_FALLBACK_CB_ROOM)

    def get_wr_alignment(self, player_name: str) -> WRAlignmentProfile:
        norm = player_name.lower().strip()
        if norm in KNOWN_WR_ALIGNMENTS:
            return KNOWN_WR_ALIGNMENTS[norm]
        # Search substring
        for k, v in KNOWN_WR_ALIGNMENTS.items():
            if k in norm or norm in k:
                return v
        return WRAlignmentProfile()

    def analyze_matchup(
        self,
        player_id: int,
        full_name: str,
        pro_team: str,
        opponent: str,
        projected_points: float,
        is_user_rostered: bool = False,
        is_user_starter: bool = False,
        inactive_player_names: set[str] | None = None,
    ) -> WRCBMatchupAnalysis:
        cb_room = self.get_cb_room(opponent, inactive_player_names=inactive_player_names)
        alignment = self.get_wr_alignment(full_name)

        outside1 = cb_room.get("outside1", DEFAULT_FALLBACK_CB_ROOM["outside1"])
        outside2 = cb_room.get("outside2", DEFAULT_FALLBACK_CB_ROOM["outside2"])
        slot_cb = cb_room.get("slot", DEFAULT_FALLBACK_CB_ROOM["slot"])

        # Determine if opponent shadows with CB1
        is_shadow_projected = False
        primary_cb = outside1

        if outside1.is_shadow and alignment.target_share >= 0.22:
            # Shadow CB travels with WR1 unless WR plays predominantly in the slot (>60%)
            if alignment.pct_slot >= 0.60:
                is_shadow_projected = False
                primary_cb = slot_cb
            else:
                is_shadow_projected = True
                primary_cb = outside1
        elif alignment.pct_slot >= 0.50:
            # Heavy slot receiver faces nickel corner predominantly
            primary_cb = slot_cb
        else:
            # Perimeter receiver splits between outside1 and outside2
            primary_cb = outside1

        # Calculate Advantage Delta
        # Baseline CB coverage grade is 70.0. If CB is 90+, -20% advantage. If CB is 60, +10% advantage.
        cb_grade = primary_cb.coverage_grade
        wr_skill_boost = (alignment.target_share - 0.20) * 50.0  # +5% for alpha targets

        # Base advantage score (positive = favorable to WR, negative = favorable to CB)
        raw_delta = (70.0 - cb_grade) * 1.1 + wr_skill_boost

        if is_shadow_projected and cb_grade >= 86.0:
            raw_delta -= 10.0  # Severe penalty for elite shadow coverage

        # Slot vulnerability boost
        if alignment.pct_slot >= 0.45 and slot_cb.coverage_grade <= 70.0:
            raw_delta += 8.0  # Slot mismatch bonus against burnable nickel corner

        advantage_score = round(max(-30.0, min(30.0, raw_delta)), 1)

        # Categorize Rating
        if is_shadow_projected and advantage_score <= -10.0:
            advantage_rating = "SHADOW_LOCKDOWN"
            tactical_takeaway = (
                f"⚠️ SHADOW ALERT: Projected shadow coverage by {outside1.name} (Coverage Grade: {outside1.coverage_grade:.1f}). "
                f"Significant ceiling reduction; expect contested targets and lower efficiency."
            )
        elif advantage_score <= -6.0:
            advantage_rating = "TOUGH_PERIMETER"
            tactical_takeaway = (
                f"Tough matchup against {primary_cb.name} (Grade: {primary_cb.coverage_grade:.1f}). "
                f"Secondary allows only {primary_cb.fpts_per_route_allowed:.2f} FP/route. High difficulty index."
            )
        elif alignment.pct_slot >= 0.45 and slot_cb.coverage_grade <= 70.0:
            advantage_rating = "SLOT_MISMATCH"
            tactical_takeaway = (
                f"🔥 SLOT MISMATCH: {full_name} ({alignment.pct_slot*100:.0f}% slot rate) runs directly into {slot_cb.name} "
                f"(Grade: {slot_cb.coverage_grade:.1f}, {slot_cb.catch_rate_allowed*100:.0f}% catch rate allowed). Prime PPR volume opportunity."
            )
        elif advantage_score >= 8.0:
            advantage_rating = "MAJOR_ADVANTAGE"
            tactical_takeaway = (
                f"⭐ MAJOR MISMATCH: Clear talent advantage over {primary_cb.name} (Grade: {primary_cb.coverage_grade:.1f}). "
                f"Opposing secondary is vulnerable ({primary_cb.fpts_per_route_allowed:.2f} FP/route allowed). High ceiling spot."
            )
        elif advantage_score >= 3.0:
            advantage_rating = "FAVORABLE"
            tactical_takeaway = (
                f"Favorable individual matchup against {primary_cb.name}. Route win rate favors {full_name} for above-average target efficiency."
            )
        elif primary_cb.is_backup_replacement:
            advantage_rating = "MAJOR_ADVANTAGE" if advantage_score >= 5.0 else "FAVORABLE"
            tactical_takeaway = (
                f"🎯 BACKUP CB TARGET: {full_name} draws backup corner {primary_cb.name} (PFF Grade: {primary_cb.coverage_grade:.1f}) "
                f"after starter {primary_cb.original_starter_name} was ruled OUT. High-value target funnel!"
            )
        else:
            advantage_rating = "NEUTRAL"
            tactical_takeaway = (
                f"Neutral coverage matchup vs {primary_cb.name} ({primary_cb.coverage_grade:.1f} Grade). Expected production tracks baseline projections."
            )

        return WRCBMatchupAnalysis(
            player_id=player_id,
            full_name=full_name,
            position="WR",
            pro_team=pro_team,
            opponent=opponent,
            projected_points=projected_points,
            alignment=alignment,
            primary_cb=primary_cb,
            secondary_cb=outside2 if primary_cb != outside2 else outside1,
            slot_cb=slot_cb,
            is_shadow_projected=is_shadow_projected,
            advantage_score=advantage_score,
            advantage_rating=advantage_rating,
            tactical_takeaway=tactical_takeaway,
            is_user_rostered=is_user_rostered,
            is_user_starter=is_user_starter,
        )


wrcb_analyzer = WRCBAnalyzer()
