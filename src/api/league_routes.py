import logging
from collections import defaultdict
from datetime import datetime
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models import LeagueModel, MatchupModel, PlayerModel, RosterEntryModel, TeamModel
from src.db.session import get_db
from src.services.espn_sync import ESPNSyncService
from src.services.optimizer.lineup_optimizer import SLOT_ORDER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/league", tags=["League"])


class SyncResponse(BaseModel):
    success: bool
    message: str
    league_id: int | None = None
    last_synced_at: datetime | None = None
    teams_count: int = 0


class TeamResponse(BaseModel):
    id: int
    league_id: int
    name: str
    abbrev: str
    primary_owner: str | None
    is_user_team: bool
    division_id: int
    record: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    win_pct: float = 0.0
    rank: int = 1
    points_for: float
    points_against: float
    live_points_for: float = 0.0
    live_points_against: float = 0.0
    live_projected_points_for: float = 0.0
    starter_count: int
    bench_count: int


class MatchupResponseItem(BaseModel):
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
    home_actual: float = 0.0
    away_actual: float = 0.0
    home_projected: float = 0.0
    away_projected: float = 0.0
    winner: str | None = None



class RosterPlayerResponse(BaseModel):
    entry_id: str
    player_id: int
    id: int | None = None
    full_name: str
    position: str
    pro_team: str
    lineup_slot_id: int
    slot_name: str
    is_starter: bool
    injury_status: str
    injured: bool
    projected_points: float
    actual_points: float
    lineup_locked: bool
    is_final: bool = False
    game_status: str = "UPCOMING"
    effective_points: float = 0.0
    fp_injury_note: str | None = None
    fp_start_sit_grade: str | None = None
    fp_pos_rank: str | None = None
    fp_tier: int | None = None
    projected_points_espn: float = 0.0
    projected_points_fp: float = 0.0
    projected_points_sleeper: float = 0.0
    projected_points_model: float = 0.0
    projected_points_consensus: float = 0.0



class PlayerDirectoryItem(BaseModel):
    id: int
    full_name: str
    position: str
    pro_team: str
    projected_points: float
    injury_status: str
    team_id: int | None = None
    team_name: str | None = None
    team_abbrev: str | None = None
    is_user_team: bool = False
    is_starter: bool = False
    is_free_agent: bool = True
    slot_name: str | None = None



class TeamRosterResponse(BaseModel):
    team_id: int
    team_name: str
    abbrev: str
    is_user_team: bool
    starters_count: int
    bench_count: int
    total_projected_points: float
    total_actual_points: float = 0.0
    total_effective_points: float = 0.0
    roster: list[RosterPlayerResponse]
    bench_slots_count: int = 7
    ir_slots_count: int = 1


class LeagueSummaryResponse(BaseModel):
    id: int
    season: int
    name: str
    size: int
    current_week: int
    is_ppr: bool
    reception_points: float
    roster_slots: dict[str, int]
    user_team_id: int | None
    last_synced_at: datetime | None
    teams: list[TeamResponse]


@router.post("/sync", response_model=SyncResponse)
async def sync_league_data(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Force re-sync even if local cache is fresh"),
    use_mock: bool = Query(default=False, description="Sync using mock fixture data"),
    league_id: int | None = Query(default=None, description="Optional override for league ID"),
    db: Session = Depends(get_db),
) -> SyncResponse:
    """Synchronize ESPN league data into local SQLite database."""
    sync_service = ESPNSyncService(db=db)
    success, message, league = await sync_service.sync(
        league_id=league_id,
        force=force,
        use_mock=use_mock,
    )

    if not success or not league:
        return SyncResponse(
            success=False,
            message=message,
            league_id=None,
            last_synced_at=None,
            teams_count=0,
        )

    # Automatically enrich with Sleeper & FantasyPros intelligence in background so ESPN sync returns immediately
    async def _enrich_task(lid: int, s: int, w: int):
        try:
            from src.services.sleeper_sync import sleeper_sync_service
            await sleeper_sync_service.sync_sleeper_projections(
                season=s,
                week=w,
            )
        except Exception:
            pass
        if settings.fantasypros_api_key:
            try:
                from src.services.fantasypros_sync import fantasypros_sync_service
                await fantasypros_sync_service.sync_league_intelligence(
                    league_id=lid,
                    season=s,
                    week=w,
                )
            except Exception:
                pass

    background_tasks.add_task(
        _enrich_task,
        league.id,
        league.season,
        league.current_week,
    )

    # Flush in-memory caches to guarantee 100% fresh evaluations immediately after sync
    try:
        from src.adapters.betting.props_client import vegas_props_client
        from src.adapters.nfl.injuries_client import nfl_injuries_client
        from src.adapters.nfl.schedule_client import nfl_schedule_client
        from src.adapters.weather.client import weather_client
        vegas_props_client.clear_cache()
        nfl_injuries_client.clear_cache()
        nfl_schedule_client.clear_cache()
        weather_client.clear_cache()
    except Exception:
        pass

    return SyncResponse(
        success=True,
        message=message,
        league_id=league.id,
        last_synced_at=league.last_synced_at,
        teams_count=len(league.teams),
    )



async def _background_league_sync(league_id: int):
    try:
        sync_svc = ESPNSyncService()
        await sync_svc.sync(league_id=league_id, force=True)
        logger.info(f"Auto-synchronized league {league_id} in background.")
    except Exception as e:
        logger.warning(f"Background league auto-sync failed: {e}")


def _get_league_summary_data(
    db: Session,
    background_tasks: BackgroundTasks | None = None,
) -> LeagueSummaryResponse:
    """Internal helper to retrieve full league summary with 8 teams from SQLite."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(
            status_code=404,
            detail="No league data found in SQLite. Run POST /api/league/sync or test_espn_connection.py first.",
        )

    # Auto-refresh: If league cache is stale (older than 10 minutes), queue background sync from ESPN
    sync_service = ESPNSyncService()
    if background_tasks and sync_service.is_cache_stale(league.id, max_age_minutes=10):
        background_tasks.add_task(_background_league_sync, league.id)

    teams_db = db.execute(
        select(TeamModel).where(TeamModel.league_id == league.id).order_by(TeamModel.id)
    ).scalars().all()

    # Batch query all roster entries joined with player stats to compute live actuals
    roster_rows = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(RosterEntryModel.league_id == league.id)
    ).all()

    entries_by_team: dict[int, list[RosterEntryModel]] = defaultdict(list)
    live_starters_actual: dict[int, float] = defaultdict(float)
    live_starters_effective: dict[int, float] = defaultdict(float)

    for entry, player in roster_rows:
        entries_by_team[entry.team_id].append(entry)
        if entry.is_starter:
            act = float(player.actual_points or 0.0)
            proj = float(player.projected_points or 0.0)
            is_locked = bool(entry.lineup_locked)
            live_starters_actual[entry.team_id] += act
            eff = act if (act > 0 or is_locked) else proj
            live_starters_effective[entry.team_id] += eff

    # Matchups for current week to resolve opponents
    current_matchups = db.execute(
        select(MatchupModel).where(
            MatchupModel.league_id == league.id,
            MatchupModel.week == league.current_week,
        )
    ).scalars().all()

    team_opponent_map: dict[int, int] = {}
    for m in current_matchups:
        team_opponent_map[m.home_team_id] = m.away_team_id
        team_opponent_map[m.away_team_id] = m.home_team_id

    team_responses: list[TeamResponse] = []
    for t in teams_db:
        entries = entries_by_team[t.id]
        starters = sum(1 for e in entries if e.is_starter)
        bench = sum(1 for e in entries if not e.is_starter)
        total_games = t.wins + t.losses + t.ties
        win_pct = round((t.wins + (t.ties * 0.5)) / max(total_games, 1), 3) if total_games > 0 else 0.0

        live_pf = round(live_starters_actual.get(t.id, 0.0), 2)
        opp_id = team_opponent_map.get(t.id)
        live_pa = round(live_starters_actual.get(opp_id, 0.0) if opp_id else 0.0, 2)
        live_proj_pf = round(live_starters_effective.get(t.id, 0.0), 2)

        # Cumulative Points For: Base points_for (from completed weeks) + live starter actuals
        if round(t.points_for, 2) == live_pf:
            total_pf = live_pf
        elif t.points_for == 0.0:
            total_pf = live_pf
        else:
            total_pf = round(t.points_for + live_pf, 2)

        if round(t.points_against, 2) == live_pa:
            total_pa = live_pa
        elif t.points_against == 0.0:
            total_pa = live_pa
        else:
            total_pa = round(t.points_against + live_pa, 2)

        team_responses.append(
            TeamResponse(
                id=t.id,
                league_id=t.league_id,
                name=t.name,
                abbrev=t.abbrev,
                primary_owner=t.primary_owner,
                is_user_team=t.is_user_team,
                division_id=t.division_id,
                record=t.record_str,
                wins=t.wins,
                losses=t.losses,
                ties=t.ties,
                win_pct=win_pct,
                rank=1,
                points_for=total_pf,
                points_against=total_pa,
                live_points_for=live_pf,
                live_points_against=live_pa,
                live_projected_points_for=live_proj_pf,
                starter_count=starters,
                bench_count=bench,
            )
        )

    # Sort into official fantasy standings order: Win% desc, Points For desc
    team_responses.sort(key=lambda x: (x.win_pct, x.points_for), reverse=True)
    for idx, team_resp in enumerate(team_responses):
        team_resp.rank = idx + 1

    return LeagueSummaryResponse(
        id=league.id,
        season=league.season,
        name=league.name,
        size=league.size,
        current_week=league.current_week,
        is_ppr=league.is_ppr,
        reception_points=league.reception_points,
        roster_slots=league.roster_slots,
        user_team_id=league.user_team_id,
        last_synced_at=league.last_synced_at,
        teams=team_responses,
    )


@router.get("/summary", response_model=LeagueSummaryResponse)
def get_league_summary(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> LeagueSummaryResponse:
    """Retrieve full league summary with 8 teams from SQLite."""
    return _get_league_summary_data(db=db, background_tasks=background_tasks)


@router.get("/teams", response_model=list[TeamResponse])
def get_league_teams(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> list[TeamResponse]:
    """List all teams in the league ordered by official standings rank."""
    summary = _get_league_summary_data(db=db, background_tasks=background_tasks)
    return summary.teams


@router.get("/matchups", response_model=list[MatchupResponseItem])
def get_league_matchups(
    week: int | None = Query(default=None, description="Matchup week (defaults to league current week)"),
    db: Session = Depends(get_db),
) -> list[MatchupResponseItem]:
    """Retrieve weekly head-to-head matchups, scores, and projected matchup outcomes."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found.")

    target_week = week if week is not None else league.current_week

    matchups = db.execute(
        select(MatchupModel).where(
            MatchupModel.league_id == league.id,
            MatchupModel.week == target_week,
        ).order_by(MatchupModel.matchup_id)
    ).scalars().all()

    teams = db.execute(select(TeamModel).where(TeamModel.league_id == league.id)).scalars().all()
    team_map = {t.id: t for t in teams}

    # Pre-calculate team projected totals and actual totals from starters
    starters = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.is_starter == True,
        )
    ).all()
    team_projections: dict[int, float] = {}
    team_actuals: dict[int, float] = {}
    for re, p in starters:
        act_pts = float(p.actual_points or 0.0)
        eff = act_pts if (re.lineup_locked or act_pts > 0) else float(p.projected_points or 0.0)
        team_projections[re.team_id] = team_projections.get(re.team_id, 0.0) + eff
        team_actuals[re.team_id] = team_actuals.get(re.team_id, 0.0) + act_pts

    items: list[MatchupResponseItem] = []
    for m in matchups:
        home_t = team_map.get(m.home_team_id)
        away_t = team_map.get(m.away_team_id)
        h_act = round(m.home_score if m.home_score > 0 else team_actuals.get(m.home_team_id, 0.0), 2)
        a_act = round(m.away_score if m.away_score > 0 else team_actuals.get(m.away_team_id, 0.0), 2)
        items.append(
            MatchupResponseItem(
                id=m.id,
                league_id=m.league_id,
                season=m.season,
                week=m.week,
                matchup_id=m.matchup_id,
                home_team_id=m.home_team_id,
                away_team_id=m.away_team_id,
                home_team_name=home_t.name if home_t else f"Team {m.home_team_id}",
                away_team_name=away_t.name if away_t else f"Team {m.away_team_id}",
                home_team_abbrev=home_t.abbrev if home_t else f"T{m.home_team_id}",
                away_team_abbrev=away_t.abbrev if away_t else f"T{m.away_team_id}",
                home_score=h_act,
                away_score=a_act,
                home_actual=h_act,
                away_actual=a_act,
                home_projected=round(team_projections.get(m.home_team_id, 0.0), 2),
                away_projected=round(team_projections.get(m.away_team_id, 0.0), 2),
                winner=m.winner,
            )
        )
    return items



@router.get("/teams/{team_id}/roster", response_model=TeamRosterResponse)
def get_team_roster(team_id: int, db: Session = Depends(get_db)) -> TeamRosterResponse:
    """Retrieve full roster for a specific team with player projections and slot assignments."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No league found.")

    team = db.execute(
        select(TeamModel).where(TeamModel.id == team_id, TeamModel.league_id == league.id)
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found in database.")

    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == team.league_id,
            RosterEntryModel.team_id == team.id,
        )
        .order_by(RosterEntryModel.lineup_slot_id)
    ).all()

    player_items: list[RosterPlayerResponse] = []
    total_proj = 0.0
    total_act = 0.0
    total_eff = 0.0

    for roster_entry, player in entries:
        act_pts = float(player.actual_points or 0.0)
        proj_pts = float(player.projected_points or 0.0)
        is_locked = bool(roster_entry.lineup_locked)

        if is_locked and act_pts > 0:
            g_status = "FINAL"
            eff_pts = act_pts
        elif is_locked:
            g_status = "LIVE"
            eff_pts = act_pts if act_pts > 0 else proj_pts
        elif act_pts > 0:
            g_status = "FINAL"
            eff_pts = act_pts
        else:
            g_status = "UPCOMING"
            eff_pts = proj_pts

        if roster_entry.is_starter:
            total_proj += proj_pts
            total_act += act_pts
            total_eff += eff_pts

        player_items.append(
            RosterPlayerResponse(
                entry_id=roster_entry.id,
                player_id=player.id,
                id=player.id,
                full_name=player.full_name,
                position=player.position,
                pro_team=player.pro_team,
                lineup_slot_id=roster_entry.lineup_slot_id,
                slot_name=roster_entry.slot_name,
                is_starter=roster_entry.is_starter,
                injury_status=player.injury_status,
                injured=player.injured,
                projected_points=proj_pts,
                actual_points=act_pts,
                lineup_locked=is_locked,
                is_final=(g_status == "FINAL"),
                game_status=g_status,
                effective_points=round(eff_pts, 2),
                fp_injury_note=player.fp_injury_note,
                fp_start_sit_grade=player.fp_start_sit_grade,
                fp_pos_rank=player.fp_pos_rank,
                fp_tier=player.fp_tier,
                projected_points_espn=player.projected_points_espn,
                projected_points_fp=player.projected_points_fp,
                projected_points_sleeper=player.projected_points_sleeper,
                projected_points_model=player.projected_points_model,
                projected_points_consensus=player.projected_points_consensus,
            )
        )

    # Sort roster entries strictly by canonical fantasy slot order:
    # QB -> RB -> WR -> TE -> FLEX -> SUPERFLEX -> K -> D/ST -> BE -> IR
    player_items.sort(key=lambda p: (SLOT_ORDER.get(p.slot_name.upper(), 999), -p.projected_points))

    starters_count = sum(1 for p in player_items if p.is_starter)
    bench_count = sum(1 for p in player_items if not p.is_starter and p.slot_name != "IR")
    bench_slots_count = int(league.roster_slots.get("BE", league.roster_slots.get("BENCH", 7))) if league.roster_slots else 7
    ir_slots_count = int(league.roster_slots.get("IR", 1)) if league.roster_slots else 1

    return TeamRosterResponse(
        team_id=team.id,
        team_name=team.name,
        abbrev=team.abbrev,
        is_user_team=team.is_user_team,
        starters_count=starters_count,
        bench_count=bench_count,
        total_projected_points=round(total_proj, 2),
        total_actual_points=round(total_act, 2),
        total_effective_points=round(total_eff, 2),
        roster=player_items,
        bench_slots_count=bench_slots_count,
        ir_slots_count=ir_slots_count,
    )


@router.get("/roster", response_model=TeamRosterResponse)
def get_roster_by_query(
    team_id: int = Query(..., description="Team ID to retrieve roster for"),
    db: Session = Depends(get_db),
) -> TeamRosterResponse:
    """Query parameter alias for /teams/{team_id}/roster."""
    return get_team_roster(team_id=team_id, db=db)


@router.get("/players", response_model=list[PlayerDirectoryItem])
def get_league_players(
    position: str | None = Query(default=None, description="Optional position filter (QB, RB, WR, TE, K, D/ST)"),
    db: Session = Depends(get_db),
) -> list[PlayerDirectoryItem]:
    """Retrieve all players in the league ecosystem with team ownership and status metadata."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found.")

    teams = db.execute(select(TeamModel).where(TeamModel.league_id == league.id)).scalars().all()
    team_map = {t.id: t for t in teams}

    roster_entries = db.execute(
        select(RosterEntryModel).where(RosterEntryModel.league_id == league.id)
    ).scalars().all()
    roster_by_player_id = {re.player_id: re for re in roster_entries}

    query = select(PlayerModel)
    if position:
        query = query.where(PlayerModel.position == position.upper())
    players = db.execute(query.order_by(PlayerModel.projected_points.desc())).scalars().all()

    items: list[PlayerDirectoryItem] = []
    for p in players:
        re = roster_by_player_id.get(p.id)
        if re:
            tm = team_map.get(re.team_id)
            items.append(
                PlayerDirectoryItem(
                    id=p.id,
                    full_name=p.full_name,
                    position=p.position,
                    pro_team=p.pro_team,
                    projected_points=p.projected_points,
                    injury_status=p.injury_status,
                    team_id=re.team_id,
                    team_name=tm.name if tm else f"Team {re.team_id}",
                    team_abbrev=tm.abbrev if tm else f"T{re.team_id}",
                    is_user_team=tm.is_user_team if tm else False,
                    is_starter=re.is_starter,
                    is_free_agent=False,
                    slot_name=re.slot_name,
                )
            )
        else:
            items.append(
                PlayerDirectoryItem(
                    id=p.id,
                    full_name=p.full_name,
                    position=p.position,
                    pro_team=p.pro_team,
                    projected_points=p.projected_points,
                    injury_status=p.injury_status,
                    team_id=None,
                    team_name=None,
                    team_abbrev=None,
                    is_user_team=False,
                    is_starter=False,
                    is_free_agent=True,
                    slot_name=None,
                )
            )

    return items
