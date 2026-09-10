"""Institutional PFF Advanced Scouting, WR vs CB, Trench Warfare & Composite Defense Service."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PFF_SEED_PATH = Path(__file__).resolve().parents[3] / "data" / "pff_scouting_2026.json"


class PFFCornerback(BaseModel):
    name: str
    role: str  # LWR, RWR, SLOT, SHADOW
    grade: float  # Coverage grade (0-100)
    is_shadow: bool = False
    targets_per_route: float = 0.18
    catch_rate: float = 0.60
    fpts_per_route: float = 0.28
    is_backup_replacement: bool = False
    original_starter_name: str | None = None
    injury_note: str | None = None


class PFFTeamScouting(BaseModel):
    team: str
    team_name: str
    cornerbacks: dict[str, PFFCornerback]
    backup_cornerbacks: dict[str, dict[str, Any]]
    offensive_line: dict[str, Any]
    defensive_line_front: dict[str, Any]


class PFFTrenchMatchup(BaseModel):
    off_team: str
    def_team: str
    is_home: bool = False
    pass_block_grade: float
    pass_rush_grade: float
    run_block_grade: float
    run_defense_grade: float
    pass_protection_edge: float
    run_push_edge: float
    pass_protection_tier: str  # CLEAN_POCKET, NEUTRAL_PRESSURE, HEAVY_COLLAPSE
    run_push_tier: str  # POWER_LANES, NEUTRAL_PUSH, STUFFED_FRONT
    key_matchup_note: str
    pressure_prob_pct: float
    stuffed_run_prob_pct: float


class PFFCompositeDefenseRecord(BaseModel):
    team: str
    team_name: str
    pass_defense_pff_grade: float
    run_defense_pff_grade: float
    pass_rush_pff_grade: float
    overall_def_grade: float
    dvp_pass_rank: int = 16
    dvp_rush_rank: int = 16
    composite_pass_score: float = 50.0  # 0 to 100
    composite_rush_score: float = 50.0
    pass_tier: str = "NEUTRAL"  # SHUTDOWN, TOUGH, NEUTRAL, VULNERABLE, BURNABLE
    rush_tier: str = "NEUTRAL"  # BRICK_WALL, STOUT, NEUTRAL, SOFT, FUNNEL
    key_disruptors: list[str] = Field(default_factory=list)
    key_corners: list[str] = Field(default_factory=list)
    secondary_injury_alert: str | None = None
    tactical_verdict: str = ""


class PFFScoutingService:
    """Institutional service integrating PFF grades, live injury overrides, and trench metrics."""

    def __init__(self, seed_path: Path = PFF_SEED_PATH) -> None:
        self.seed_path = seed_path
        self._data: dict[str, Any] = {}
        self._load_seed()

    def _load_seed(self) -> None:
        try:
            if self.seed_path.exists():
                with open(self.seed_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f).get("teams", {})
                logger.info(f"Loaded PFF scouting baseline for {len(self._data)} teams.")
            else:
                logger.warning(f"PFF seed file not found at {self.seed_path}")
        except Exception as e:
            logger.error(f"Error loading PFF seed data: {e}")
            self._data = {}

    def get_team_scouting(self, team: str) -> dict[str, Any] | None:
        t = (team or "").strip().upper()
        return self._data.get(t)

    def get_active_cb_room(
        self,
        team: str,
        inactive_player_names: set[str] | None = None,
    ) -> dict[str, PFFCornerback]:
        """Returns the team's active cornerback room (outside1, outside2, slot),

        automatically promoting backups and applying live injury overrides if
        starters are inactive.
        """
        t = (team or "").strip().upper()
        team_data = self._data.get(t)
        inactives = {n.lower().strip() for n in (inactive_player_names or set())}

        if not team_data:
            # Generic fallback
            return {
                "outside1": PFFCornerback(name="Primary Outside CB", role="LWR", grade=70.0),
                "outside2": PFFCornerback(name="Secondary Outside CB", role="RWR", grade=68.0),
                "slot": PFFCornerback(name="Nickel Slot CB", role="SLOT", grade=69.0),
            }

        raw_cbs = team_data.get("cornerbacks", {})
        backups = team_data.get("backup_cornerbacks", {})

        result: dict[str, PFFCornerback] = {}

        # 1. Outside 1
        o1 = raw_cbs.get("outside1", {})
        o1_name = o1.get("name", "CB1")
        if o1_name.lower().strip() in inactives:
            # Promote outside backup
            bk = backups.get("outside_backup", {"name": "Backup Cornerback", "grade": 60.0})
            result["outside1"] = PFFCornerback(
                name=bk.get("name", "Backup CB"),
                role="LWR",
                grade=float(bk.get("grade", 60.0)),
                is_shadow=False,
                targets_per_route=0.23,
                catch_rate=0.68,
                fpts_per_route=0.38,
                is_backup_replacement=True,
                original_starter_name=o1_name,
                injury_note=f"Promoted after {o1_name} ruled OUT",
            )
        else:
            result["outside1"] = PFFCornerback(
                name=o1.get("name", "CB1"),
                role=o1.get("role", "LWR"),
                grade=float(o1.get("grade", 72.0)),
                is_shadow=bool(o1.get("is_shadow", False)),
                targets_per_route=float(o1.get("targets_per_route", 0.18)),
                catch_rate=float(o1.get("catch_rate", 0.60)),
                fpts_per_route=float(o1.get("fpts_per_route", 0.28)),
            )

        # 2. Outside 2
        o2 = raw_cbs.get("outside2", {})
        o2_name = o2.get("name", "CB2")
        if o2_name.lower().strip() in inactives:
            bk = backups.get("outside_backup", {"name": "Secondary Backup CB", "grade": 61.0})
            result["outside2"] = PFFCornerback(
                name=bk.get("name", "Backup CB2"),
                role="RWR",
                grade=float(bk.get("grade", 61.0)),
                is_shadow=False,
                targets_per_route=0.24,
                catch_rate=0.69,
                fpts_per_route=0.40,
                is_backup_replacement=True,
                original_starter_name=o2_name,
                injury_note=f"Promoted after {o2_name} ruled OUT",
            )
        else:
            result["outside2"] = PFFCornerback(
                name=o2.get("name", "CB2"),
                role=o2.get("role", "RWR"),
                grade=float(o2.get("grade", 69.0)),
                is_shadow=False,
                targets_per_route=float(o2.get("targets_per_route", 0.20)),
                catch_rate=float(o2.get("catch_rate", 0.62)),
                fpts_per_route=float(o2.get("fpts_per_route", 0.31)),
            )

        # 3. Slot CB
        slot = raw_cbs.get("slot", {})
        slot_name = slot.get("name", "Nickel CB")
        if slot_name.lower().strip() in inactives:
            bk = backups.get("slot_backup", {"name": "Backup Nickel CB", "grade": 62.0})
            result["slot"] = PFFCornerback(
                name=bk.get("name", "Backup Slot CB"),
                role="SLOT",
                grade=float(bk.get("grade", 62.0)),
                is_shadow=False,
                targets_per_route=0.22,
                catch_rate=0.67,
                fpts_per_route=0.35,
                is_backup_replacement=True,
                original_starter_name=slot_name,
                injury_note=f"Promoted after {slot_name} ruled OUT",
            )
        else:
            result["slot"] = PFFCornerback(
                name=slot.get("name", "Nickel CB"),
                role="SLOT",
                grade=float(slot.get("grade", 72.0)),
                is_shadow=False,
                targets_per_route=float(slot.get("targets_per_route", 0.18)),
                catch_rate=float(slot.get("catch_rate", 0.60)),
                fpts_per_route=float(slot.get("fpts_per_route", 0.27)),
            )

        # 4. Safety (Middle of Field / TE defender)
        safety = raw_cbs.get("safety", {})
        safety_name = safety.get("name", "Safety")
        if safety_name.lower().strip() in inactives:
            bk = backups.get("safety_backup", {"name": "Backup Safety", "grade": 60.0})
            result["safety"] = PFFCornerback(
                name=bk.get("name", "Backup Safety"),
                role="FS",
                grade=float(bk.get("grade", 60.0)),
                is_shadow=False,
                targets_per_route=0.20,
                catch_rate=0.68,
                fpts_per_route=0.32,
                is_backup_replacement=True,
                original_starter_name=safety_name,
                injury_note=f"Promoted after {safety_name} ruled OUT",
            )
        else:
            result["safety"] = PFFCornerback(
                name=safety.get("name", "Safety"),
                role=safety.get("role", "SS"),
                grade=float(safety.get("grade", 78.0)),
                is_shadow=False,
            )

        return result

    def get_trench_matchup(self, off_team: str, def_team: str, is_home: bool = False) -> PFFTrenchMatchup:
        """Evaluates Offensive Line vs Defensive Front 7 Trench Mismatch."""
        ot = (off_team or "").strip().upper()
        dt = (def_team or "").strip().upper()

        off_data = self._data.get(ot, {})
        def_data = self._data.get(dt, {})

        oline = off_data.get("offensive_line", {"pass_block_grade": 70.0, "run_block_grade": 70.0})
        dfront = def_data.get("defensive_line_front", {"pass_rush_grade": 72.0, "run_defense_grade": 72.0, "pressure_rate_pct": 32.0, "stuffed_run_pct": 19.0})

        pass_block = float(oline.get("pass_block_grade", 70.0))
        run_block = float(oline.get("run_block_grade", 70.0))
        pass_rush = float(dfront.get("pass_rush_grade", 72.0))
        run_defense = float(dfront.get("run_defense_grade", 72.0))

        # Home field advantage tweak (+1.5 to home unit)
        if is_home:
            pass_block += 1.5
            run_block += 1.5
        else:
            pass_rush += 1.5
            run_defense += 1.5

        pass_edge = round(pass_block - pass_rush, 1)
        run_edge = round(run_block - run_defense, 1)

        # Classify pass protection tier
        if pass_edge >= 6.0:
            pass_tier = "CLEAN_POCKET"
            pass_note = f"{ot} O-Line ({pass_block:.1f}) provides clean pocket against {dt} pass rush ({pass_rush:.1f}). High QB efficiency & deep passing time."
        elif pass_edge <= -6.0:
            pass_tier = "HEAVY_COLLAPSE"
            pass_note = f"⚠️ TRENCH ALARM: {dt} defensive front ({pass_rush:.1f}) holds overwhelming edge over {ot} pass blocking ({pass_block:.1f}). Expect quick pressures & checkdowns."
        else:
            pass_tier = "NEUTRAL_PRESSURE"
            pass_note = f"Balanced trench matchup ({pass_edge:+.1f} edge). Standard pocket time expected."

        # Classify run push tier
        if run_edge >= 6.0:
            run_tier = "POWER_LANES"
            run_note = f"Dominant run blocking edge (+{run_edge:.1f}). Expect generous yards before contact and red-zone goal-line push."
        elif run_edge <= -6.0:
            run_tier = "STUFFED_FRONT"
            run_note = f"Stout run front ({run_defense:.1f}). Expect low yards before contact; running back must create on own."
        else:
            run_tier = "NEUTRAL_PUSH"
            run_note = f"Competitive run front battle ({run_edge:+.1f} push edge)."

        tactical_summary = f"{pass_note} | {run_note}"

        base_pressure = float(dfront.get("pressure_rate_pct", 32.0))
        adj_pressure = max(18.0, min(50.0, base_pressure - (pass_edge * 0.8)))

        base_stuffed = float(dfront.get("stuffed_run_pct", 19.0))
        adj_stuffed = max(10.0, min(35.0, base_stuffed - (run_edge * 0.7)))

        return PFFTrenchMatchup(
            off_team=ot,
            def_team=dt,
            is_home=is_home,
            pass_block_grade=round(pass_block, 1),
            pass_rush_grade=round(pass_rush, 1),
            run_block_grade=round(run_block, 1),
            run_defense_grade=round(run_defense, 1),
            pass_protection_edge=pass_edge,
            run_push_edge=run_edge,
            pass_protection_tier=pass_tier,
            run_push_tier=run_tier,
            key_matchup_note=tactical_summary,
            pressure_prob_pct=round(adj_pressure, 1),
            stuffed_run_prob_pct=round(adj_stuffed, 1),
        )

    def get_composite_defense_matrix(
        self,
        dvp_pass_ranks: dict[str, int] | None = None,
        dvp_rush_ranks: dict[str, int] | None = None,
        inactive_map: dict[str, set[str]] | None = None,
    ) -> list[PFFCompositeDefenseRecord]:
        """Calculates 32-team composite defense ranking combining PFF film grades,

        DvP ranks, and real-time secondary inactives.
        """
        records: list[PFFCompositeDefenseRecord] = []
        pass_ranks = dvp_pass_ranks or {}
        rush_ranks = dvp_rush_ranks or {}
        inactives_by_team = inactive_map or {}

        for team_abbr, tdata in self._data.items():
            team_name = tdata.get("team_name", team_abbr)
            raw_cbs = tdata.get("cornerbacks", {})
            dfront = tdata.get("defensive_line_front", {})

            # Check for key secondary inactives
            team_inactives = inactives_by_team.get(team_abbr, set())
            active_cbs = self.get_active_cb_room(team_abbr, team_inactives)

            # Average active CB grades
            cb_grades = [active_cbs["outside1"].grade, active_cbs["outside2"].grade, active_cbs["slot"].grade]
            pass_def_grade = sum(cb_grades) / len(cb_grades)
            run_def_grade = float(dfront.get("run_defense_grade", 72.0))
            pass_rush_grade = float(dfront.get("pass_rush_grade", 72.0))
            overall_grade = (pass_def_grade * 0.45) + (run_def_grade * 0.30) + (pass_rush_grade * 0.25)

            # DvP rankings (1 = stingiest defense, 32 = softest defense)
            p_dvp = pass_ranks.get(team_abbr, 16)
            r_dvp = rush_ranks.get(team_abbr, 16)

            # Invert DvP so 100 = best defense, 0 = worst defense
            dvp_pass_score = (33 - p_dvp) / 32.0 * 100.0
            dvp_rush_score = (33 - r_dvp) / 32.0 * 100.0

            # Composite Score: 60% PFF Film Grade + 40% DvP Production
            comp_pass = round((pass_def_grade * 0.60) + (dvp_pass_score * 0.40), 1)
            comp_rush = round((run_def_grade * 0.60) + (dvp_rush_score * 0.40), 1)

            # Categorize tiers
            if comp_pass >= 78.0:
                pass_tier = "SHUTDOWN"
            elif comp_pass >= 70.0:
                pass_tier = "TOUGH"
            elif comp_pass >= 63.0:
                pass_tier = "NEUTRAL"
            elif comp_pass >= 55.0:
                pass_tier = "VULNERABLE"
            else:
                pass_tier = "BURNABLE"

            if comp_rush >= 78.0:
                rush_tier = "BRICK_WALL"
            elif comp_rush >= 70.0:
                rush_tier = "STOUT"
            elif comp_rush >= 63.0:
                rush_tier = "NEUTRAL"
            elif comp_rush >= 55.0:
                rush_tier = "SOFT"
            else:
                rush_tier = "FUNNEL"

            # Inactive alert detection
            injury_alerts = []
            for role_key, cb in active_cbs.items():
                if cb.is_backup_replacement and cb.original_starter_name:
                    injury_alerts.append(f"{cb.original_starter_name} (OUT)")
            injury_alert_str = ", ".join(injury_alerts) if injury_alerts else None

            # Key personnel
            key_disruptors = list(dfront.get("key_disruptors", []))
            key_corners = [active_cbs["outside1"].name, active_cbs["slot"].name]

            # Tactical verdict
            if pass_tier in ("BURNABLE", "VULNERABLE") and rush_tier in ("BRICK_WALL", "STOUT"):
                verdict = f"PASS FUNNEL DEFENSE: Elite run-stoppers force opponents into heavy passing script vs vulnerable secondary."
            elif rush_tier in ("SOFT", "FUNNEL") and pass_tier in ("SHUTDOWN", "TOUGH"):
                verdict = f"RUN FUNNEL DEFENSE: Lockdown perimeter corners funnel high offensive touch volume to opposing running backs."
            elif pass_tier == "SHUTDOWN" and rush_tier == "BRICK_WALL":
                verdict = f"NO-FLY ZONE: Elite across all phases. Fade offensive projections and temper ceiling expectations."
            elif pass_tier == "BURNABLE" and rush_tier == "SOFT":
                verdict = f"GREEN LIGHT SMASH SPOT: Porous across both air and ground. Premier DFS stacking target."
            else:
                verdict = f"BALANCED UNIT: Matchup tracks individual talent differentials."

            records.append(
                PFFCompositeDefenseRecord(
                    team=team_abbr,
                    team_name=team_name,
                    pass_defense_pff_grade=round(pass_def_grade, 1),
                    run_defense_pff_grade=round(run_def_grade, 1),
                    pass_rush_pff_grade=round(pass_rush_grade, 1),
                    overall_def_grade=round(overall_grade, 1),
                    dvp_pass_rank=p_dvp,
                    dvp_rush_rank=r_dvp,
                    composite_pass_score=comp_pass,
                    composite_rush_score=comp_rush,
                    pass_tier=pass_tier,
                    rush_tier=rush_tier,
                    key_disruptors=key_disruptors,
                    key_corners=key_corners,
                    secondary_injury_alert=injury_alert_str,
                    tactical_verdict=verdict,
                )
            )

        # Sort by overall defense grade descending
        records.sort(key=lambda r: r.overall_def_grade, reverse=True)
        return records


pff_scouting_service = PFFScoutingService()
