"""Pydantic schemas for parsing and validating ESPN Fantasy API responses."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from src.adapters.espn.constants import (
    NFL_TEAM_MAP,
    POSITION_ID_MAP,
    SLOT_NAME_MAP,
    RosterSlot,
    StatSource,
)


class ItemizedStatLine(BaseModel):
    """Structured breakdown of itemized passing, rushing, receiving, kicking, and D/ST stats."""
    pass_att: float = 0.0
    pass_cmp: float = 0.0
    pass_yds: float = 0.0
    pass_td: float = 0.0
    pass_int: float = 0.0
    rush_att: float = 0.0
    rush_yds: float = 0.0
    rush_td: float = 0.0
    targets: float = 0.0
    receptions: float = 0.0
    rec_yds: float = 0.0
    rec_td: float = 0.0
    fg_made: float = 0.0
    pat_made: float = 0.0
    sacks: float = 0.0
    turnovers: float = 0.0
    def_td: float = 0.0
    pts_allowed: float = 0.0
    calculated_ppr: float = 0.0

    @classmethod
    def from_espn_stats(cls, stats_dict: dict[str, float]) -> "ItemizedStatLine":
        def g(key: int | str, default: float = 0.0) -> float:
            k_str = str(key)
            val = stats_dict.get(k_str)
            if val is None and k_str.isdigit():
                val = stats_dict.get(str(int(k_str)))
            try:
                return round(float(val), 2) if val is not None else default
            except (ValueError, TypeError):
                return default

        pass_att = g(0)
        pass_cmp = g(1)
        pass_yds = g(3)
        pass_td = g(4)
        pass_int = g(20)

        rush_att = g(23)
        rush_yds = g(24)
        rush_td = g(25)

        targets = g(58)
        receptions = g(53)
        rec_yds = g(42)
        rec_td = g(43)

        fg_made = round(g(74) + g(77) + g(80), 2)
        pat_made = g(86)

        sacks = g(99)
        turnovers = round(g(105) + g(106), 2)
        def_td = g(107)
        pts_allowed = g(89)

        # True mathematical Full-PPR formula
        calc_ppr = (
            (pass_yds * 0.04) + (pass_td * 4.0) - (pass_int * 2.0)
            + (rush_yds * 0.1) + (rush_td * 6.0)
            + (receptions * 1.0) + (rec_yds * 0.1) + (rec_td * 6.0)
            + (fg_made * 3.0) + (pat_made * 1.0)
            + (sacks * 1.0) + (turnovers * 2.0) + (def_td * 6.0)
        )

        return cls(
            pass_att=pass_att,
            pass_cmp=pass_cmp,
            pass_yds=pass_yds,
            pass_td=pass_td,
            pass_int=pass_int,
            rush_att=rush_att,
            rush_yds=rush_yds,
            rush_td=rush_td,
            targets=targets,
            receptions=receptions,
            rec_yds=rec_yds,
            rec_td=rec_td,
            fg_made=fg_made,
            pat_made=pat_made,
            sacks=sacks,
            turnovers=turnovers,
            def_td=def_td,
            pts_allowed=pts_allowed,
            calculated_ppr=round(calc_ppr, 2),
        )


class ESPNAthleteStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stat_source_id: int = Field(alias="statSourceId")
    scoring_period_id: int = Field(alias="scoringPeriodId")
    applied_total: float = Field(default=0.0, alias="appliedTotal")
    applied_stats: dict[str, float] = Field(default_factory=dict, alias="stats")

    @property
    def itemized(self) -> ItemizedStatLine:
        return ItemizedStatLine.from_espn_stats(self.applied_stats)


class ESPNAthlete(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    full_name: str = Field(alias="fullName")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    pro_team_id: int = Field(default=0, alias="proTeamId")
    default_position_id: int = Field(default=0, alias="defaultPositionId")
    eligible_slots: list[int] = Field(default_factory=list, alias="eligibleSlots")
    injury_status: str | None = Field(default="ACTIVE", alias="injuryStatus")
    injured: bool = Field(default=False)
    stats: list[ESPNAthleteStats] = Field(default_factory=list)
    rankings: dict[str, Any] = Field(default_factory=dict)

    @property
    def pro_team(self) -> str:
        return NFL_TEAM_MAP.get(self.pro_team_id, "UNK")

    @property
    def position(self) -> str:
        return POSITION_ID_MAP.get(self.default_position_id, "UNK")

    def get_projection_for_week(self, week: int) -> float:
        for s in self.stats:
            if s.stat_source_id == StatSource.PROJECTED and s.scoring_period_id == week:
                return round(s.applied_total, 2)
        return 0.0

    def get_itemized_projection_for_week(self, week: int) -> ItemizedStatLine | None:
        for s in self.stats:
            if s.stat_source_id == StatSource.PROJECTED and s.scoring_period_id == week:
                return s.itemized
        return None

    def get_consensus_rank_for_week(self, week: int) -> float | None:
        period_ranks = self.rankings.get(str(week), [])
        for r in period_ranks:
            if isinstance(r, dict) and r.get("averageRank"):
                return float(r["averageRank"])
        return None

    def get_actual_for_week(self, week: int) -> float:
        for s in self.stats:
            if s.stat_source_id == StatSource.ACTUAL and s.scoring_period_id == week:
                return round(s.applied_total, 2)
        return 0.0



class ESPNPlayerPoolEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    player: ESPNAthlete
    status: str | None = Field(default=None)  # FREEAGENT, WAIVERS, ONTEAM
    lineup_locked: bool = Field(default=False, alias="lineupLocked")


class ESPNRosterEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    player_id: int = Field(alias="playerId")
    lineup_slot_id: int = Field(alias="lineupSlotId")
    injury_status: str | None = Field(default=None, alias="injuryStatus")
    player_pool_entry: ESPNPlayerPoolEntry | None = Field(default=None, alias="playerPoolEntry")

    @property
    def slot_name(self) -> str:
        return SLOT_NAME_MAP.get(self.lineup_slot_id, f"SLOT_{self.lineup_slot_id}")

    @property
    def is_starter(self) -> bool:
        return self.lineup_slot_id not in (RosterSlot.BENCH, RosterSlot.IR)


class ESPNRoster(BaseModel):
    model_config = ConfigDict(extra="ignore")
    applied_stat_total: float = Field(default=0.0, alias="appliedStatTotal")
    entries: list[ESPNRosterEntry] = Field(default_factory=list)


class ESPNTeamRecordOverall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = Field(default=0.0, alias="pointsFor")
    points_against: float = Field(default=0.0, alias="pointsAgainst")


class ESPNTeamRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    overall: ESPNTeamRecordOverall = Field(default_factory=ESPNTeamRecordOverall)


class ESPNTeam(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    name: str | None = None
    location: str | None = ""
    nickname: str | None = ""
    abbrev: str = ""
    division_id: int = Field(default=0, alias="divisionId")
    primary_owner: str | None = Field(default=None, alias="primaryOwner")
    owners: list[str] = Field(default_factory=list)
    roster: ESPNRoster | None = None
    record: ESPNTeamRecord | None = None

    @property
    def full_name(self) -> str:
        if self.name and self.name.strip():
            return self.name.strip()
        loc = self.location or ""
        nick = self.nickname or ""
        combined = f"{loc} {nick}".strip()
        return combined or f"Team {self.id}"



class ESPNRosterSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lineup_slot_counts: dict[str, int] = Field(default_factory=dict, alias="lineupSlotCounts")
    position_limits: dict[str, int] = Field(default_factory=dict, alias="positionLimits")

    @property
    def parsed_slot_counts(self) -> dict[str, int]:
        """Convert string slot ID keys into human-readable slot names."""
        result: dict[str, int] = {}
        for slot_id_str, count in self.lineup_slot_counts.items():
            try:
                slot_id = int(slot_id_str)
                name = SLOT_NAME_MAP.get(slot_id, f"SLOT_{slot_id}")
                if count > 0:
                    result[name] = count
            except ValueError:
                result[slot_id_str] = count
        return result


class ESPNScoringItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stat_id: int = Field(alias="statId")
    points: float = Field(default=0.0)


class ESPNScoringSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scoring_items: list[dict[str, Any]] = Field(default_factory=list, alias="scoringItems")

    @property
    def is_ppr(self) -> bool:
        """Check if receptions (statId 53) award >= 1.0 point."""
        for item in self.scoring_items:
            if item.get("statId") == 53:
                return float(item.get("points", 0)) >= 1.0
        return False

    @property
    def reception_points(self) -> float:
        for item in self.scoring_items:
            if item.get("statId") == 53:
                return float(item.get("points", 0))
        return 0.0


class ESPNLeagueSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = "ESPN Fantasy League"
    size: int = 8
    roster_settings: ESPNRosterSettings = Field(default_factory=ESPNRosterSettings, alias="rosterSettings")
    scoring_settings: ESPNScoringSettings = Field(default_factory=ESPNScoringSettings, alias="scoringSettings")


class ESPNMember(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    display_name: str | None = Field(default=None, alias="displayName")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")

    @property
    def full_name(self) -> str:
        name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return name or self.display_name or self.id


class ESPNMatchupTeam(BaseModel):
    model_config = ConfigDict(extra="ignore")
    team_id: int = Field(default=0, alias="teamId")
    total_points: float = Field(default=0.0, alias="totalPoints")
    total_points_live: float | None = Field(default=None, alias="totalPointsLive")


class ESPNMatchup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    matchup_period_id: int = Field(default=1, alias="matchupPeriodId")
    home: ESPNMatchupTeam | None = None
    away: ESPNMatchupTeam | None = None
    winner: str | None = Field(default="UNDECIDED")


class ESPNLeagueResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    season_id: int = Field(alias="seasonId")
    scoring_period_id: int = Field(default=1, alias="scoringPeriodId")
    current_matchup_period: int = Field(default=1, alias="currentMatchupPeriod")
    settings: ESPNLeagueSettings | None = None
    teams: list[ESPNTeam] = Field(default_factory=list)
    members: list[ESPNMember] = Field(default_factory=list)
    schedule: list[ESPNMatchup] = Field(default_factory=list)
    status: dict[str, Any] = Field(default_factory=dict)



# Clean High-Level Domain Summaries for the UI / CLI
class TeamSummary(BaseModel):
    id: int
    name: str
    abbrev: str
    owner: str | None
    record: str
    points_for: float
    starter_count: int
    bench_count: int


class MatchupSummary(BaseModel):
    id: str
    league_id: int
    season: int
    week: int
    matchup_id: int
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    home_team_abbrev: str
    away_team_abbrev: str
    home_score: float
    away_score: float
    home_projected: float = 0.0
    away_projected: float = 0.0
    winner: str | None = None


class LeagueSummary(BaseModel):
    league_id: int
    season: int
    name: str
    size: int
    current_week: int
    is_ppr: bool
    reception_points: float
    roster_slots: dict[str, int]
    teams: list[TeamSummary]

