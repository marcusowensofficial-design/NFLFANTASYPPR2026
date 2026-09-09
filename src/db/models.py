"""SQLAlchemy 2.0 ORM models for ESPN fantasy league, teams, players, rosters, and matchups."""

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.adapters.espn.constants import SLOT_NAME_MAP, RosterSlot
from src.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LeagueModel(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # ESPN League ID
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_ppr: Mapped[bool] = mapped_column(Boolean, default=True)
    reception_points: Mapped[float] = mapped_column(Float, default=1.0)
    roster_slots_json: Mapped[str] = mapped_column(Text, default="{}")
    user_team_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    teams: Mapped[list["TeamModel"]] = relationship("TeamModel", back_populates="league", cascade="all, delete-orphan")

    @property
    def roster_slots(self) -> dict[str, int]:
        try:
            return json.loads(self.roster_slots_json)
        except Exception:
            return {}

    @roster_slots.setter
    def roster_slots(self, value: dict[str, int]) -> None:
        self.roster_slots_json = json.dumps(value)


class TeamModel(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    abbrev: Mapped[str] = mapped_column(String(10), default="")
    primary_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    owners_json: Mapped[str] = mapped_column(Text, default="[]")
    is_user_team: Mapped[bool] = mapped_column(Boolean, default=False)
    division_id: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    ties: Mapped[int] = mapped_column(Integer, default=0)
    points_for: Mapped[float] = mapped_column(Float, default=0.0)
    points_against: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    league: Mapped["LeagueModel"] = relationship("LeagueModel", back_populates="teams")
    roster_entries: Mapped[list["RosterEntryModel"]] = relationship(
        "RosterEntryModel",
        back_populates="team",
        cascade="all, delete-orphan",
        primaryjoin="and_(TeamModel.id==RosterEntryModel.team_id, TeamModel.league_id==RosterEntryModel.league_id)",
    )

    @property
    def record_str(self) -> str:
        s = f"{self.wins}-{self.losses}"
        if self.ties > 0:
            s += f"-{self.ties}"
        return s

    @property
    def owners(self) -> list[str]:
        try:
            return json.loads(self.owners_json)
        except Exception:
            return []

    @owners.setter
    def owners(self, value: list[str]) -> None:
        self.owners_json = json.dumps(value)


class PlayerModel(Base):
    __tablename__ = "players"
    __table_args__ = (Index("ix_players_id_pos", "id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # ESPN Athlete ID
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    position: Mapped[str] = mapped_column(String(10), nullable=False, default="UNK")
    pro_team: Mapped[str] = mapped_column(String(10), nullable=False, default="FA")
    eligible_slots_json: Mapped[str] = mapped_column(Text, default="[]")
    injury_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    injured: Mapped[bool] = mapped_column(Boolean, default=False)
    projected_points: Mapped[float] = mapped_column(Float, default=0.0)
    actual_points: Mapped[float] = mapped_column(Float, default=0.0)
    projected_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    upcoming_schedule_json: Mapped[str] = mapped_column(Text, default="[]")
    consensus_rank: Mapped[float] = mapped_column(Float, default=999.0)
    fp_rank_ecr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fp_pos_rank: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fp_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fp_rank_ave: Mapped[float | None] = mapped_column(Float, nullable=True)
    fp_rank_std: Mapped[float | None] = mapped_column(Float, nullable=True)
    fp_start_sit_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fp_r2p_pts: Mapped[float | None] = mapped_column(Float, nullable=True)
    fp_injury_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    projected_points_espn: Mapped[float] = mapped_column(Float, default=0.0)
    projected_points_fp: Mapped[float] = mapped_column(Float, default=0.0)
    projected_points_sleeper: Mapped[float] = mapped_column(Float, default=0.0)
    projected_points_model: Mapped[float] = mapped_column(Float, default=0.0)
    projected_points_consensus: Mapped[float] = mapped_column(Float, default=0.0)
    fp_projected_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    sleeper_projected_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


    @property
    def eligible_slots(self) -> list[int]:
        try:
            return json.loads(self.eligible_slots_json)
        except Exception:
            return []

    @eligible_slots.setter
    def eligible_slots(self, value: list[int]) -> None:
        self.eligible_slots_json = json.dumps(value)

    @property
    def projected_stats(self) -> dict[str, float]:
        try:
            return json.loads(self.projected_stats_json)
        except Exception:
            return {}

    @projected_stats.setter
    def projected_stats(self, value: dict[str, float]) -> None:
        self.projected_stats_json = json.dumps(value)

    @property
    def fp_projected_stats(self) -> dict[str, float]:
        try:
            return json.loads(self.fp_projected_stats_json)
        except Exception:
            return {}

    @fp_projected_stats.setter
    def fp_projected_stats(self, value: dict[str, float]) -> None:
        self.fp_projected_stats_json = json.dumps(value)

    @property
    def sleeper_projected_stats(self) -> dict[str, float]:
        try:
            return json.loads(self.sleeper_projected_stats_json)
        except Exception:
            return {}

    @sleeper_projected_stats.setter
    def sleeper_projected_stats(self, value: dict[str, float]) -> None:
        self.sleeper_projected_stats_json = json.dumps(value)

    @property
    def upcoming_schedule(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.upcoming_schedule_json)
        except Exception:
            return []

    @upcoming_schedule.setter
    def upcoming_schedule(self, value: list[dict[str, Any]]) -> None:
        self.upcoming_schedule_json = json.dumps(value)


class RosterEntryModel(Base):
    __tablename__ = "roster_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "league_id"],
            ["teams.id", "teams.league_id"],
            ondelete="CASCADE",
        ),
        Index("ix_roster_league_team_starter", "league_id", "team_id", "is_starter"),
    )

    # Composite primary key: league_id + team_id + player_id
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    lineup_slot_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=QB, 2=RB, 20=BE, 21=IR, 23=FLEX, etc.
    is_starter: Mapped[bool] = mapped_column(Boolean, default=True)
    lineup_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    team: Mapped["TeamModel"] = relationship(
        "TeamModel",
        back_populates="roster_entries",
        primaryjoin="and_(TeamModel.id==RosterEntryModel.team_id, TeamModel.league_id==RosterEntryModel.league_id)",
    )
    player: Mapped["PlayerModel"] = relationship("PlayerModel")

    @property
    def slot_name(self) -> str:
        return SLOT_NAME_MAP.get(self.lineup_slot_id, f"SLOT_{self.lineup_slot_id}")


class MatchupModel(Base):
    __tablename__ = "matchups"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    league_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    matchup_id: Mapped[int] = mapped_column(Integer, nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, nullable=False)
    home_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_score: Mapped[float] = mapped_column(Float, default=0.0)
    winner: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HOME, AWAY, TIE, PENDING
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class SyncLogModel(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCCESS, ERROR
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserSettingsModel(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    league_size: Mapped[int] = mapped_column(Integer, default=8)
    weights_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    @property
    def weights(self) -> dict[str, float]:
        try:
            return json.loads(self.weights_json)
        except Exception:
            return {}

    @weights.setter
    def weights(self, value: dict[str, float]) -> None:
        self.weights_json = json.dumps(value)


class DefenseVsPositionModel(Base):
    __tablename__ = "defense_vs_position"
    __table_args__ = (
        Index("ix_dvp_season_week_pos", "season", "week", "position"),
        Index("ix_dvp_team_pos", "pro_team", "position"),
    )

    # Composite primary key format: {season}_{week}_{pro_team}_{position}
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pro_team: Mapped[str] = mapped_column(String(10), nullable=False)
    team_name: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[str] = mapped_column(String(10), nullable=False)  # QB, RB, WR, TE
    rank_softness: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = most generous/softest, 32 = toughest
    rank_defense: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = toughest/stingiest, 32 = softest
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="NEUTRAL")  # SMASH, FAVORABLE, NEUTRAL, TOUGH, LOCKDOWN
    tier_label: Mapped[str] = mapped_column(String(40), nullable=False, default="Neutral Matchup")
    dk_fpa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fd_fpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    vs_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    prior_season_fpa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_season_fpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    last4_fpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend: Mapped[str] = mapped_column(String(80), default="Stable")
    supporting_stats_json: Mapped[str] = mapped_column(Text, default="{}")
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=True)
    sample_games_current: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(40), default="DraftEdge")
    source_url: Mapped[str] = mapped_column(String(255), default="https://draftedge.com/nfl/nfl-defense-vs-pos/")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    @property
    def supporting_stats(self) -> dict[str, float]:
        try:
            return json.loads(self.supporting_stats_json)
        except Exception:
            return {}

    @supporting_stats.setter
    def supporting_stats(self, value: dict[str, float]) -> None:
        self.supporting_stats_json = json.dumps(value)


