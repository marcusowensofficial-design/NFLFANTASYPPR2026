"""FastAPI route handlers for League, Teams, Rosters, and Sync operations."""

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
    home_projected: float = 0.0
    away_projected: float = 0.0
    winner: str | None = None



class RosterPlayerResponse(BaseModel):
    entry_id: str
    player_id: int
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

    # Automatically enrich with FantasyPros intelligence in background so ESPN sync returns immediately
    if settings.fantasypros_api_key:
        async def _enrich_task(lid: int, s: int, w: int):
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

    return SyncResponse(
        success=True,
        message=message,
        league_id=league.id,
        last_synced_at=league.last_synced_at,
        teams_count=len(league.teams),
    )



@router.get("/summary", response_model=LeagueSummaryResponse)
def get_league_summary(db: Session = Depends(get_db)) -> LeagueSummaryResponse:
    """Retrieve full league summary with 8 teams from SQLite."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(
            status_code=404,
            detail="No league data found in SQLite. Run POST /api/league/sync or test_espn_connection.py first.",
        )

    teams_db = db.execute(
        select(TeamModel).where(TeamModel.league_id == league.id).order_by(TeamModel.id)
    ).scalars().all()

    team_responses: list[TeamResponse] = []
    for t in teams_db:
        entries = db.execute(
            select(RosterEntryModel).where(
                RosterEntryModel.league_id == league.id,
                RosterEntryModel.team_id == t.id,
            )
        ).scalars().all()

        starters = sum(1 for e in entries if e.is_starter)
        bench = sum(1 for e in entries if not e.is_starter)
        total_games = t.wins + t.losses + t.ties
        win_pct = round((t.wins + (t.ties * 0.5)) / max(total_games, 1), 3) if total_games > 0 else 0.0

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
                points_for=t.points_for,
                points_against=t.points_against,
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


@router.get("/teams", response_model=list[TeamResponse])
def get_league_teams(db: Session = Depends(get_db)) -> list[TeamResponse]:
    """List all teams in the league ordered by official standings rank."""
    summary = get_league_summary(db)
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

    # Pre-calculate team projected totals from starters
    starters = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.is_starter == True,
        )
    ).all()
    team_projections: dict[int, float] = {}
    for re, p in starters:
        team_projections[re.team_id] = team_projections.get(re.team_id, 0.0) + p.projected_points

    items: list[MatchupResponseItem] = []
    for m in matchups:
        home_t = team_map.get(m.home_team_id)
        away_t = team_map.get(m.away_team_id)
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
                home_score=round(m.home_score, 2),
                away_score=round(m.away_score, 2),
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

    for roster_entry, player in entries:
        if roster_entry.is_starter:
            total_proj += player.projected_points

        player_items.append(
            RosterPlayerResponse(
                entry_id=roster_entry.id,
                player_id=player.id,
                full_name=player.full_name,
                position=player.position,
                pro_team=player.pro_team,
                lineup_slot_id=roster_entry.lineup_slot_id,
                slot_name=roster_entry.slot_name,
                is_starter=roster_entry.is_starter,
                injury_status=player.injury_status,
                injured=player.injured,
                projected_points=player.projected_points,
                actual_points=player.actual_points,
                lineup_locked=roster_entry.lineup_locked,
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
        roster=player_items,
        bench_slots_count=bench_slots_count,
        ir_slots_count=ir_slots_count,
    )


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
