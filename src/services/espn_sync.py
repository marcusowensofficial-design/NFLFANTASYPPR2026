import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session


from src.adapters.espn.client import ESPNClient
from src.adapters.espn.constants import RosterSlot
from src.adapters.espn.schemas import ESPNAthlete, ESPNLeagueResponse
from src.core.config import settings
from src.db.models import (
    LeagueModel,
    MatchupModel,
    PlayerModel,
    RosterEntryModel,
    SyncLogModel,
    TeamModel,
    utc_now,
)
from src.db.session import SessionLocal

logger = logging.getLogger(__name__)


_espn_sync_lock: asyncio.Lock | None = None


def _get_sync_lock() -> asyncio.Lock:
    global _espn_sync_lock
    if _espn_sync_lock is None:
        _espn_sync_lock = asyncio.Lock()
    return _espn_sync_lock


class ESPNSyncService:
    """Manages hybrid synchronization between ESPN Fantasy API and SQLite database."""

    def __init__(self, db: Session | None = None):
        self._external_db = db

    def _get_db(self) -> Session:
        return self._external_db if self._external_db is not None else SessionLocal()

    def is_cache_stale(self, league_id: int, max_age_minutes: int = 15) -> bool:
        """Returns True if league data in SQLite is missing or older than max_age_minutes."""
        db = self._get_db()
        try:
            league = db.execute(select(LeagueModel).where(LeagueModel.id == league_id)).scalar_one_or_none()
            if not league or not league.last_synced_at:
                return True
            # SQLite stores naive datetimes, compare with UTC
            last_synced = league.last_synced_at
            if last_synced.tzinfo is None:
                last_synced = last_synced.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - last_synced) > timedelta(minutes=max_age_minutes)
        finally:
            if self._external_db is None:
                db.close()

    def get_league_from_db(self, league_id: int) -> LeagueModel | None:
        """Retrieve stored league record from SQLite."""
        db = self._get_db()
        try:
            return db.execute(select(LeagueModel).where(LeagueModel.id == league_id)).scalar_one_or_none()
        finally:
            if self._external_db is None:
                db.close()

    async def sync(
        self,
        league_id: int | None = None,
        force: bool = False,
        use_mock: bool = False,
    ) -> tuple[bool, str, LeagueModel | None]:
        """Perform hybrid sync: returns cached data if fresh, or queries ESPN and updates SQLite."""
        target_league_id = league_id or settings.espn_league_id
        if not target_league_id and not use_mock:
            return False, "No ESPN_LEAGUE_ID configured in .env file.", None

        # If cache is fresh and not forced, return cached model
        if target_league_id and not force and not use_mock and not self.is_cache_stale(target_league_id):
            cached_league = self.get_league_from_db(target_league_id)
            if cached_league:
                return True, "Cache is fresh (less than 15 minutes old).", cached_league

        lock = _get_sync_lock()
        if lock.locked():
            # Another sync is in progress. Await it and return fresh cached result.
            async with lock:
                cached = self.get_league_from_db(target_league_id) if target_league_id else None
                if cached:
                    return True, f"Synchronized league '{cached.name}' via concurrent sync.", cached

        async with lock:
            # Re-check cache in case previous sync completed while waiting for lock
            if target_league_id and not force and not use_mock and not self.is_cache_stale(target_league_id):
                cached_league = self.get_league_from_db(target_league_id)
                if cached_league:
                    return True, "Cache is fresh (less than 15 minutes old).", cached_league

            return await self._execute_sync(target_league_id, force=force, use_mock=use_mock)

    async def _execute_sync(
        self,
        target_league_id: int | None,
        force: bool = False,
        use_mock: bool = False,
    ) -> tuple[bool, str, LeagueModel | None]:
        """Internal execution of ESPN sync under lock."""

        # Fetch data either from mock fixture or live ESPN
        raw_data: dict[str, Any]
        if use_mock or not target_league_id:
            mock_path = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mock_espn_league.json"
            if not mock_path.exists():
                return False, f"Mock fixture not found at {mock_path}", None
            with open(mock_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            if target_league_id:
                raw_data["id"] = target_league_id
        else:
            client = ESPNClient(
                league_id=target_league_id,
                season=settings.espn_season,
                swid=settings.espn_swid,
                espn_s2=settings.espn_s2,
            )
            try:
                raw_data = await client.fetch_league_raw()
            except Exception as e:
                logger.error(f"ESPN sync failed for league {target_league_id}: {e}")
                self._log_sync(target_league_id, status="ERROR", details=str(e))
                return False, f"ESPN API error: {e}", None

        # Parse with verified Pydantic schema
        try:
            parsed_response = ESPNLeagueResponse.model_validate(raw_data)
        except Exception as e:
            logger.exception("Failed to validate ESPN response against Pydantic schema")
            return False, f"Schema validation error: {e}", None

        # Fetch upcoming 3-week NFL schedules for all player pro teams
        from src.adapters.nfl.schedule_client import nfl_schedule_client
        pro_teams: set[str] = set()
        for t in parsed_response.teams:
            if t.roster and t.roster.entries:
                for entry in t.roster.entries:
                    if entry.player_pool_entry and entry.player_pool_entry.player:
                        pt = entry.player_pool_entry.player.pro_team
                        if pt and pt != "UNK":
                            pro_teams.add(pt)

        # Pre-warm upcoming 3-week NFL schedules in parallel
        schedule_warm_tasks = [
            nfl_schedule_client.fetch_week_schedule(
                season=parsed_response.season_id,
                week=parsed_response.scoring_period_id + offset,
            )
            for offset in range(3)
        ]
        await asyncio.gather(*schedule_warm_tasks, return_exceptions=True)

        team_schedules: dict[str, list[dict[str, Any]]] = {}
        for pt in pro_teams:
            try:
                team_schedules[pt] = await nfl_schedule_client.get_upcoming_schedule_for_team(
                    pt, current_week=parsed_response.scoring_period_id, count=3, season=parsed_response.season_id
                )
            except Exception as e:
                logger.debug(f"Failed to fetch schedule for {pt}: {e}")
                team_schedules[pt] = []


        # Fetch available free agents from ESPN for waiver wire analysis
        free_agent_athletes: list[ESPNAthlete] = []
        if not use_mock and target_league_id:
            try:
                free_agent_athletes = await client.fetch_free_agents(
                    scoring_period_id=parsed_response.scoring_period_id,
                    limit=100,
                )
                logger.info(f"Fetched {len(free_agent_athletes)} available free agents from ESPN.")
            except Exception as e:
                logger.warning(f"Failed to fetch free agents during sync: {e}")

        # Persist to SQLite
        db = self._get_db()
        try:
            league = self._persist_league_data(
                db,
                parsed_response,
                team_schedules=team_schedules,
                free_agents=free_agent_athletes,
            )
            db.commit()
            db.refresh(league)
            self._log_sync(league.id, status="SUCCESS", details=f"Synced {len(league.teams)} teams.")
            return True, f"Successfully synchronized league '{league.name}' into SQLite database.", league
        except Exception as e:
            db.rollback()
            logger.exception("Database persistence failed during ESPN sync")
            return False, f"Database error during sync: {e}", None
        finally:
            if self._external_db is None:
                db.close()

    def _persist_league_data(
        self,
        db: Session,
        data: ESPNLeagueResponse,
        team_schedules: dict[str, list[dict[str, Any]]] | None = None,
        free_agents: list[ESPNAthlete] | None = None,
    ) -> LeagueModel:
        """Insert or update League, Teams, Players, Rosters, and Matchups."""
        league = db.execute(select(LeagueModel).where(LeagueModel.id == data.id)).scalar_one_or_none()
        if not league:
            league = LeagueModel(id=data.id)
            db.add(league)

        settings_obj = data.settings
        league.name = settings_obj.name if settings_obj else f"League #{data.id}"
        league.season = data.season_id
        league.current_week = data.scoring_period_id
        league.size = settings_obj.size if settings_obj else len(data.teams)

        if settings_obj and settings_obj.roster_settings:
            league.roster_slots_json = json.dumps(settings_obj.roster_settings.parsed_slot_counts)
        if settings_obj and settings_obj.scoring_settings:
            league.is_ppr = settings_obj.scoring_settings.is_ppr
            league.reception_points = settings_obj.scoring_settings.reception_points

        league.last_synced_at = utc_now()

        # Identify User Team via SWID cookie or settings.espn_team_id
        user_swid = settings.espn_swid.strip().lower() if settings.espn_swid else None
        detected_user_team_id: int | None = None
        team_models: dict[int, TeamModel] = {}

        # Build member names dictionary
        member_names = {m.id: m.full_name for m in data.members}

        # Remove any obsolete teams that no longer exist in ESPN for this league
        valid_team_ids = {t.id for t in data.teams}
        obsolete_teams = db.execute(
            select(TeamModel).where(
                TeamModel.league_id == data.id,
                TeamModel.id.not_in(valid_team_ids),
            )
        ).scalars().all()
        for ot in obsolete_teams:
            db.delete(ot)

        # 1. First pass: find user team and upsert teams
        for t in data.teams:
            team_model = db.execute(
                select(TeamModel).where(TeamModel.id == t.id, TeamModel.league_id == data.id)
            ).scalar_one_or_none()

            if not team_model:
                team_model = TeamModel(id=t.id, league_id=data.id)
                db.add(team_model)

            team_model.name = t.full_name
            team_model.abbrev = t.abbrev
            team_model.primary_owner = member_names.get(t.primary_owner, t.primary_owner)
            team_model.owners_json = json.dumps(t.owners)
            team_model.division_id = t.division_id

            if t.record and t.record.overall:
                team_model.wins = t.record.overall.wins
                team_model.losses = t.record.overall.losses
                team_model.ties = t.record.overall.ties
                team_model.points_for = t.record.overall.points_for
                team_model.points_against = t.record.overall.points_against

            # Check if this team belongs to the user
            is_user = False
            if user_swid and any(user_swid in o.lower() for o in t.owners):
                is_user = True
            elif settings.espn_team_id == t.id:
                is_user = True

            if is_user:
                detected_user_team_id = t.id

            team_model.is_user_team = is_user
            team_models[t.id] = team_model

        # Fallback user team to Team 1 if none matched
        if detected_user_team_id is None and data.teams:
            detected_user_team_id = data.teams[0].id
            if detected_user_team_id in team_models:
                team_models[detected_user_team_id].is_user_team = True

        league.user_team_id = detected_user_team_id

        # 2. Upsert Players and Roster Entries
        for t in data.teams:
            # Clear previous roster entries for this team to prevent stale assignments
            existing_entries = db.execute(
                select(RosterEntryModel).where(
                    RosterEntryModel.league_id == data.id,
                    RosterEntryModel.team_id == t.id,
                )
            ).scalars().all()
            for ee in existing_entries:
                db.delete(ee)

            if not t.roster or not t.roster.entries:
                continue

            for entry in t.roster.entries:
                pool_entry = entry.player_pool_entry
                athlete = pool_entry.player if pool_entry else None

                # Upsert Player record if athlete data is present
                if athlete:
                    # Clean up any unrostered ghost records with the same name but different ID
                    ghost_players = db.execute(
                        select(PlayerModel).where(
                            PlayerModel.full_name == athlete.full_name,
                            PlayerModel.id != athlete.id,
                        )
                    ).scalars().all()
                    for gp in ghost_players:
                        has_roster = db.execute(
                            select(RosterEntryModel).where(RosterEntryModel.player_id == gp.id)
                        ).scalars().first()
                        if not has_roster:
                            logger.info(f"Cleaning up ghost PlayerModel {gp.id} ({gp.full_name}) superseded by {athlete.id}")
                            db.delete(gp)

                    player = db.execute(select(PlayerModel).where(PlayerModel.id == athlete.id)).scalar_one_or_none()
                    if not player:
                        player = PlayerModel(id=athlete.id)
                        db.add(player)

                    player.full_name = athlete.full_name
                    player.first_name = athlete.first_name
                    player.last_name = athlete.last_name
                    player.position = athlete.position
                    player.pro_team = athlete.pro_team
                    player.eligible_slots_json = json.dumps(athlete.eligible_slots)
                    player.injury_status = athlete.injury_status or "ACTIVE"
                    player.injured = athlete.injured
                    player.projected_points = athlete.get_projection_for_week(data.scoring_period_id)
                    player.actual_points = athlete.get_actual_for_week(data.scoring_period_id)

                    itemized = athlete.get_itemized_projection_for_week(data.scoring_period_id)
                    if itemized:
                        player.projected_stats_json = json.dumps(itemized.model_dump())
                        # If applied projection is 0 or missing, use calculated PPR
                        if player.projected_points <= 0.0 and itemized.calculated_ppr > 0.0:
                            player.projected_points = itemized.calculated_ppr
                    else:
                        player.projected_stats_json = "{}"

                    player.projected_points_espn = round(player.projected_points, 2)

                    c_rank = athlete.get_consensus_rank_for_week(data.scoring_period_id)
                    player.consensus_rank = c_rank if c_rank is not None else 999.0

                    if team_schedules and athlete.pro_team in team_schedules:
                        player.upcoming_schedule_json = json.dumps(team_schedules[athlete.pro_team])
                    else:
                        player.upcoming_schedule_json = "[]"

                # Insert Roster Entry
                entry_id = f"{data.id}_{t.id}_{entry.player_id}"
                is_starter = entry.lineup_slot_id not in (RosterSlot.BENCH, RosterSlot.IR)
                locked = pool_entry.lineup_locked if pool_entry else False

                roster_model = RosterEntryModel(
                    id=entry_id,
                    league_id=data.id,
                    team_id=t.id,
                    player_id=entry.player_id,
                    lineup_slot_id=entry.lineup_slot_id,
                    is_starter=is_starter,
                    lineup_locked=locked,
                )
                db.add(roster_model)

        # 3. Upsert Available Free Agents into PlayerModel
        if free_agents:
            for fa in free_agents:
                fa_player = db.execute(select(PlayerModel).where(PlayerModel.id == fa.id)).scalar_one_or_none()
                if not fa_player:
                    fa_player = PlayerModel(id=fa.id)
                    db.add(fa_player)

                fa_player.full_name = fa.full_name
                fa_player.first_name = fa.first_name
                fa_player.last_name = fa.last_name
                fa_player.position = fa.position
                fa_player.pro_team = fa.pro_team
                fa_player.eligible_slots_json = json.dumps(fa.eligible_slots)
                fa_player.injury_status = fa.injury_status or "ACTIVE"
                fa_player.injured = fa.injured
                fa_player.projected_points = fa.get_projection_for_week(data.scoring_period_id)
                fa_player.actual_points = fa.get_actual_for_week(data.scoring_period_id)

                fa_itemized = fa.get_itemized_projection_for_week(data.scoring_period_id)
                if fa_itemized:
                    fa_player.projected_stats_json = json.dumps(fa_itemized.model_dump())
                    if fa_player.projected_points <= 0.0 and fa_itemized.calculated_ppr > 0.0:
                        fa_player.projected_points = fa_itemized.calculated_ppr
                else:
                    fa_player.projected_stats_json = "{}"

                fa_player.projected_points_espn = round(fa_player.projected_points, 2)

                fa_rank = fa.get_consensus_rank_for_week(data.scoring_period_id)
                fa_player.consensus_rank = fa_rank if fa_rank is not None else 999.0

                if team_schedules and fa.pro_team in team_schedules:
                    fa_player.upcoming_schedule_json = json.dumps(team_schedules[fa.pro_team])
                else:
                    fa_player.upcoming_schedule_json = "[]"

        # 3b. Authoritative Live Injury Wire Reconciliation
        # Ensures breaking news (e.g. OUT designations, IR placements, practice downgrades)
        # overrides stale or delayed league platform statuses (e.g. DAY_TO_DAY).
        try:
            from pathlib import Path
            inj_file = Path(__file__).resolve().parent.parent.parent / "data" / "injuries_live_2026.json"
            if inj_file.exists():
                with open(inj_file, encoding="utf-8") as f:
                    live_json = json.load(f)
                live_injuries = live_json.get("injuries", [])
                live_by_id = {item["athlete_id"]: item for item in live_injuries if "athlete_id" in item}
                live_by_name = {item["name"].lower().strip(): item for item in live_injuries if "name" in item}
                all_db_players = db.execute(select(PlayerModel)).scalars().all()
                for p in all_db_players:
                    live_rep = live_by_id.get(p.id) or live_by_name.get(p.full_name.lower().strip())
                    if live_rep:
                        st_upper = (live_rep.get("status") or "").upper()
                        if "IR" in st_upper or "INJURED RESERVE" in st_upper:
                            p.injury_status = "INJURY_RESERVE"
                            p.injured = True
                        elif "OUT" in st_upper:
                            p.injury_status = "OUT"
                            p.injured = True
                        elif "DOUBTFUL" in st_upper:
                            p.injury_status = "DOUBTFUL"
                            p.injured = True
                        elif "QUESTIONABLE" in st_upper:
                            p.injury_status = "QUESTIONABLE"
                            p.injured = True
                        elif st_upper in ("ACTIVE", "NORMAL") and p.injury_status in ("DAY_TO_DAY", "QUESTIONABLE"):
                            hl = (live_rep.get("headline") or "").lower()
                            if "no injury designation" in hl:
                                p.injury_status = "ACTIVE"
                                p.injured = False
        except Exception as e:
            logger.debug(f"Failed to reconcile live injury wire in ESPN sync: {e}")

        # 4. Upsert Matchups / Schedule
        if data.schedule:
            for m in data.schedule:
                if not m.home or not m.away:
                    continue
                matchup_key = f"{data.id}_{data.season_id}_{m.matchup_period_id}_{m.id}"
                matchup_model = db.execute(
                    select(MatchupModel).where(MatchupModel.id == matchup_key)
                ).scalar_one_or_none()

                if not matchup_model:
                    matchup_model = MatchupModel(
                        id=matchup_key,
                        league_id=data.id,
                        season=data.season_id,
                        week=m.matchup_period_id,
                        matchup_id=m.id,
                        home_team_id=m.home.team_id,
                        away_team_id=m.away.team_id,
                    )
                    db.add(matchup_model)

                matchup_model.home_team_id = m.home.team_id
                matchup_model.away_team_id = m.away.team_id
                matchup_model.home_score = m.home.total_points
                matchup_model.away_score = m.away.total_points
                matchup_model.winner = m.winner
                matchup_model.updated_at = utc_now()

        # 5. Compute and persist live starter points into Points For (PF) and Points Against (PA)
        # ESPN's t.record.overall.points_for stays 0.0 during active weeks until official finalization.
        live_starters_by_team: dict[int, float] = defaultdict(float)
        for t in data.teams:
            if not t.roster or not t.roster.entries:
                continue
            for entry in t.roster.entries:
                if entry.lineup_slot_id not in (RosterSlot.BENCH, RosterSlot.IR):
                    p_entry = entry.player_pool_entry
                    ath = p_entry.player if p_entry else None
                    if ath:
                        act = float(ath.get_actual_for_week(data.scoring_period_id) or 0.0)
                        live_starters_by_team[t.id] += act

        team_opps: dict[int, int] = {}
        if data.schedule:
            for m in data.schedule:
                if m.matchup_period_id == data.scoring_period_id and m.home and m.away:
                    team_opps[m.home.team_id] = m.away.team_id
                    team_opps[m.away.team_id] = m.home.team_id

        for t_id, team_m in team_models.items():
            live_pf = round(live_starters_by_team.get(t_id, 0.0), 2)
            opp_id = team_opps.get(t_id)
            live_pa = round(live_starters_by_team.get(opp_id, 0.0) if opp_id else 0.0, 2)
            base_pf = team_m.points_for or 0.0
            base_pa = team_m.points_against or 0.0
            if base_pf == 0.0:
                team_m.points_for = live_pf
            if base_pa == 0.0:
                team_m.points_against = live_pa

        return league


    def _log_sync(self, league_id: int | None, status: str, details: str | None = None) -> None:
        """Record sync result to SQLite sync_logs table."""
        if not league_id:
            return
        db = self._get_db()
        try:
            log_entry = SyncLogModel(
                league_id=league_id,
                synced_at=utc_now(),
                status=status,
                details=details,
            )
            db.add(log_entry)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            if self._external_db is None:
                db.close()
