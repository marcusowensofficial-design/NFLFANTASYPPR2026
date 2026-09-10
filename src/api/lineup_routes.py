"""API routes for lineup optimization, starting lineup diffs, and close call detection."""

import asyncio
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.espn.client import ESPNClient
from src.adapters.espn.constants import RosterSlot, SLOT_NAME_MAP
from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.adapters.weather.client import weather_client
from src.core.config import settings
from src.db.models import LeagueModel, MatchupModel, PlayerModel, RosterEntryModel, TeamModel
from src.db.session import get_db
from src.services.espn_sync import ESPNSyncService
from src.services.optimizer.lineup_optimizer import (
    CloseCallPair,
    OptimizedLineupResult,
    SlotAssignment,
    lineup_optimizer,
)
from src.services.recommendation.scoring_engine import (
    StartSitEvaluation,
    scoring_engine,
)

router = APIRouter(prefix="/api/lineup", tags=["Lineup"])


class LineupMoveItem(BaseModel):
    player_id: int
    player_name: str
    position: str
    from_slot_id: int
    from_slot_name: str
    to_slot_id: int
    to_slot_name: str
    net_gain: float
    start_score: float


class PreFlightPushPreview(BaseModel):
    team_id: int
    team_name: str
    moves_count: int
    moves: list[LineupMoveItem]
    can_push_to_espn: bool
    status_message: str


class LineupPushRequest(BaseModel):
    team_id: int
    confirm: bool = False
    selected_moves: list[dict[str, Any]] = Field(default_factory=list)
    mode: str = "BALANCED"
    projection_source: str = "MODEL"
    custom_starter_ids: list[int] | None = None


class LineupPushResponse(BaseModel):
    success: bool
    message: str
    moves_executed: int
    team_id: int
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/optimal", response_model=OptimizedLineupResult)
async def get_optimal_lineup(
    team_id: int | None = Query(default=None, description="Optional team ID (defaults to user team)"),
    mode: str = Query(default="BALANCED", description="Strategy mode: BALANCED, CEILING, FLOOR, or AUTO"),
    projection_source: str = Query(default="MODEL", description="Projection source: MODEL, FANTASYPROS, SLEEPER, ESPN, or CONSENSUS"),
    opponent_projected_points: float | None = Query(default=None, description="Optional opponent projected points (auto-retrieved from matchup if omitted)"),
    db: Session = Depends(get_db),
) -> OptimizedLineupResult:
    """Run lineup optimizer for the target team and return starters, bench, and close calls."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No league data found. Sync ESPN first.")

    target_team_id = team_id or league.user_team_id or 1
    league_size = league.size or 8
    mode_val = str(getattr(mode, "default", mode) if hasattr(mode, "default") else (mode or "BALANCED"))
    proj_source_val = str(getattr(projection_source, "default", projection_source) if hasattr(projection_source, "default") else (projection_source or "MODEL")).upper().strip()

    # Auto-resolve opponent projected points & team info from live weekly matchup if not provided
    opp_proj: float | None = None
    opp_team_id: int | None = None
    opp_team_name: str | None = None
    opp_team_abbrev: str | None = None

    matchup = db.execute(
        select(MatchupModel).where(
            MatchupModel.league_id == league.id,
            MatchupModel.week == league.current_week,
            (MatchupModel.home_team_id == target_team_id) | (MatchupModel.away_team_id == target_team_id),
        )
    ).scalars().first()

    if matchup:
        opp_team_id = matchup.away_team_id if matchup.home_team_id == target_team_id else matchup.home_team_id
        opp_team = db.execute(
            select(TeamModel).where(TeamModel.id == opp_team_id, TeamModel.league_id == league.id)
        ).scalar_one_or_none()
        if opp_team:
            opp_team_name = opp_team.name
            opp_team_abbrev = opp_team.abbrev

        if isinstance(opponent_projected_points, (int, float)):
            opp_proj = float(opponent_projected_points)
        else:
            opp_starters = db.execute(
                select(PlayerModel, RosterEntryModel)
                .join(RosterEntryModel, RosterEntryModel.player_id == PlayerModel.id)
                .where(
                    RosterEntryModel.league_id == league.id,
                    RosterEntryModel.team_id == opp_team_id,
                    RosterEntryModel.is_starter == True,
                )
            ).all()
            if opp_starters:
                opp_proj = round(sum(
                    p.actual_points if (re.lineup_locked or p.actual_points > 0) else p.projected_points
                    for p, re in opp_starters
                ), 1)
    elif isinstance(opponent_projected_points, (int, float)):
        opp_proj = float(opponent_projected_points)

    team = db.execute(
        select(TeamModel).where(TeamModel.id == target_team_id, TeamModel.league_id == league.id)
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team {target_team_id} not found.")

    # Retrieve all players currently on this team's roster
    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
        )
    ).all()

    if not entries:
        raise HTTPException(status_code=404, detail="No roster players found for this team.")

    current_starter_ids = {re.player_id for re, _ in entries if re.is_starter}
    current_ir_ids = {re.player_id for re, _ in entries if re.lineup_slot_id == RosterSlot.IR or re.slot_name == "IR"}
    locked_player_ids = {re.player_id for re, _ in entries if re.lineup_locked}
    locked_starter_slot_map = {re.player_id: re.lineup_slot_id for re, _ in entries if re.lineup_locked and re.is_starter}

    # Fetch live NFL schedule and injuries concurrently in parallel
    nfl_games, injuries_by_athlete = await asyncio.gather(
        nfl_schedule_client.fetch_week_schedule(season=league.season, week=league.current_week),
        nfl_injuries_client.fetch_injuries(),
    )

    # Pre-fetch weather for all outdoor home venues in parallel
    home_teams = {g.home_team for g in nfl_games if g.home_team and g.home_team != "UNK"}
    weather_reports = await asyncio.gather(*(weather_client.get_stadium_weather(ht) for ht in home_teams))
    weather_by_home_team = dict(zip(home_teams, weather_reports))

    # Pre-compute O(1) game and weather context matrix by team
    games_by_team = {}
    weather_by_team = {}
    for g in nfl_games:
        games_by_team[g.home_team] = g
        games_by_team[g.away_team] = g
        w = weather_by_home_team.get(g.home_team)
        weather_by_team[g.home_team] = w
        weather_by_team[g.away_team] = w

    # Evaluate each player with StartSitScoringEngine using O(1) precomputed game context
    evaluations: list[StartSitEvaluation] = []
    for re, player in entries:
        game = games_by_team.get(player.pro_team)
        weather = weather_by_team.get(player.pro_team)
        injury = injuries_by_athlete.get(player.id)
        ev = scoring_engine.evaluate_player(
            player,
            nfl_game=game,
            injury_report=injury,
            weather=weather,
            mode=mode_val,
            league_size=league_size,
            projection_source=proj_source_val,
            actual_points=player.actual_points,
            lineup_locked=re.lineup_locked,
        )
        evaluations.append(ev)

    # Run optimizer
    result = lineup_optimizer.optimize_lineup(
        team_id=target_team_id,
        roster_slots_config=league.roster_slots,
        evaluations=evaluations,
        current_starter_ids=current_starter_ids,
        locked_player_ids=locked_player_ids,
        locked_starter_slot_map=locked_starter_slot_map,
        mode=mode_val,
        opponent_projected_points=opp_proj,
        opponent_team_id=opp_team_id,
        opponent_team_name=opp_team_name,
        opponent_team_abbrev=opp_team_abbrev,
        current_ir_ids=current_ir_ids,
        projection_source=proj_source_val,
    )

    return result



@router.post("/push", response_model=LineupPushResponse | PreFlightPushPreview)
async def push_lineup_to_espn(
    request: LineupPushRequest,
    db: Session = Depends(get_db),
) -> Any:
    """Pre-flight check or authenticated 1-click execution of optimal roster moves on ESPN."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found.")

    team = db.execute(
        select(TeamModel).where(TeamModel.id == request.team_id, TeamModel.league_id == league.id)
    ).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team {request.team_id} not found.")

    # Calculate optimal lineup using the requested mode and projection source
    optimal = await get_optimal_lineup(
        team_id=request.team_id,
        mode=request.mode,
        projection_source=request.projection_source,
        db=db,
    )

    # Get current roster entries to determine exact movements
    roster_entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == request.team_id,
        )
    ).all()

    entry_map = {re.player_id: (re, p) for re, p in roster_entries}

    target_slots = optimal.starters
    if request.custom_starter_ids:
        custom_id_set = set(request.custom_starter_ids)
        all_evals = {s.recommended_player.player_id: s.recommended_player for s in optimal.starters}
        all_evals.update({b.player_id: b for b in optimal.bench})
        updated_slots = []
        assigned_cids = set()
        for slot in optimal.starters:
            if slot.recommended_player.player_id in custom_id_set:
                updated_slots.append(slot)
                assigned_cids.add(slot.recommended_player.player_id)
            else:
                replacement = None
                for cid in request.custom_starter_ids:
                    if cid not in assigned_cids and cid in all_evals:
                        cand = all_evals[cid]
                        if (
                            (slot.slot_name == "FLEX" and cand.position in ("RB", "WR", "TE"))
                            or (cand.position == slot.slot_name)
                            or (slot.slot_name == "KICKER" and cand.position in ("K", "PK"))
                            or (slot.slot_name in ("DEFENSE", "DST", "D/ST") and cand.position in ("DST", "D/ST", "DEF"))
                        ):
                            replacement = cand
                            assigned_cids.add(cid)
                            break
                if replacement:
                    from copy import copy
                    slot_copy = copy(slot)
                    slot_copy.recommended_player = replacement
                    curr_pts = slot.current_starter.projected_points if slot.current_starter else 0.0
                    slot_copy.net_projected_delta = round(replacement.projected_points - curr_pts, 2)
                    updated_slots.append(slot_copy)
                else:
                    updated_slots.append(slot)
        target_slots = updated_slots

    # Find differences between current starters and recommended starters
    moves: list[LineupMoveItem] = []
    for slot in target_slots:
        rec_player = slot.recommended_player
        curr_starter = slot.current_starter

        # If the recommended player was on the bench, they must be promoted to starter
        if curr_starter and rec_player.player_id != curr_starter.player_id:
            curr_re, _ = entry_map[curr_starter.player_id]
            rec_re, _ = entry_map[rec_player.player_id]

            moves.append(
                LineupMoveItem(
                    player_id=rec_player.player_id,
                    player_name=str(rec_player.full_name),
                    position=rec_player.position,
                    from_slot_id=rec_re.lineup_slot_id,
                    from_slot_name=SLOT_NAME_MAP.get(rec_re.lineup_slot_id, "BENCH"),
                    to_slot_id=slot.slot_id,
                    to_slot_name=slot.slot_name,
                    net_gain=slot.net_projected_delta,
                    start_score=rec_player.start_score,
                )
            )
            moves.append(
                LineupMoveItem(
                    player_id=curr_starter.player_id,
                    player_name=str(curr_starter.full_name),
                    position=curr_starter.position,
                    from_slot_id=curr_re.lineup_slot_id,
                    from_slot_name=slot.slot_name,
                    to_slot_id=RosterSlot.BENCH,
                    to_slot_name="Bench",
                    net_gain=-slot.net_projected_delta,
                    start_score=curr_starter.start_score,
                )
            )

    can_push = bool(settings.espn_swid and settings.espn_s2)

    # Mode 1: Pre-Flight Review Preview
    if not request.confirm:
        msg = f"Ready to submit {len(moves)} roster moves to ESPN." if moves else "Lineup is already 100% optimal!"
        if not can_push:
            msg = "ESPN authenticated credentials (SWID / espn_s2) are missing in .env."

        return PreFlightPushPreview(
            team_id=request.team_id,
            team_name=team.name,
            moves_count=len(moves),
            moves=moves,
            can_push_to_espn=can_push,
            status_message=msg,
        )

    # Mode 2: Confirmed Execution
    if not can_push:
        raise HTTPException(
            status_code=400,
            detail="Cannot push lineup: ESPN_SWID and ESPN_S2 session cookies not configured in .env",
        )

    client = ESPNClient(
        league_id=league.id,
        season=league.season,
        swid=settings.espn_swid,
        espn_s2=settings.espn_s2,
    )

    # Use provided selected moves or all generated moves
    moves_to_execute = request.selected_moves if request.selected_moves else [
        {
            "player_id": m.player_id,
            "from_slot_id": m.from_slot_id,
            "to_slot_id": m.to_slot_id,
        }
        for m in moves
    ]

    if not moves_to_execute:
        return LineupPushResponse(
            success=True,
            message="No moves to execute; lineup is already optimal.",
            moves_executed=0,
            team_id=request.team_id,
        )

    success, message, payload = await client.execute_roster_transaction(
        team_id=request.team_id,
        moves=moves_to_execute,
        scoring_period_id=league.current_week,
        dry_run=False,
    )

    # Trigger background re-sync if successfully executed
    if success:
        sync_service = ESPNSyncService(db=db)
        await sync_service.sync(league_id=league.id, force=True)

    return LineupPushResponse(
        success=success,
        message=message,
        moves_executed=len(moves_to_execute) if success else 0,
        team_id=request.team_id,
        raw_payload=payload,
    )


class InactiveAlertItem(BaseModel):
    starter_id: int
    starter_name: str
    position: str
    injury_status: str
    pro_team: str
    slot_name: str = "STARTER"
    starter_proj: float = 0.0
    recommended_bench_id: int | None = None
    recommended_bench_name: str | None = None
    recommended_bench_pos: str | None = None
    recommended_bench_proj: float = 0.0
    top_waiver_id: int | None = None
    top_waiver_name: str | None = None
    top_waiver_pos: str | None = None
    top_waiver_proj: float = 0.0
    net_projected_pts: float = 0.0
    alert_message: str


class InactiveAlertsResponse(BaseModel):
    team_id: int
    has_critical_inactives: bool
    alerts_count: int
    alerts: list[InactiveAlertItem]


class EmergencyPivotRequest(BaseModel):
    team_id: int
    starter_id: int
    bench_id: int


class EmergencyPivotResponse(BaseModel):
    success: bool
    message: str
    starter_name: str
    bench_name: str
    from_slot: str
    to_slot: str
    moves_executed: int = 1


@router.get("/inactives-alert", response_model=InactiveAlertsResponse)
async def check_inactives_alert(
    team_id: int | None = Query(default=None, description="Team ID to check (defaults to user team)"),
    db: Session = Depends(get_db),
) -> InactiveAlertsResponse:
    """Pre-kickoff sweep identifying any active starting players ruled OUT, INACTIVE, or DOUBTFUL with bench replacements."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        return InactiveAlertsResponse(team_id=1, has_critical_inactives=False, alerts_count=0, alerts=[])

    target_team_id = team_id or league.user_team_id or 1
    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
        )
    ).all()

    if not entries:
        return InactiveAlertsResponse(team_id=target_team_id, has_critical_inactives=False, alerts_count=0, alerts=[])

    # Fetch live injuries
    injuries_by_athlete = await nfl_injuries_client.fetch_injuries()

    starters = [(re, p) for re, p in entries if re.is_starter]
    bench_players = [p for re, p in entries if not re.is_starter]

    critical_inactives: list[InactiveAlertItem] = []
    for re, player in starters:
        live_inj = injuries_by_athlete.get(player.id)
        raw_status = (live_inj.status if live_inj else player.injury_status or "ACTIVE").upper()

        if raw_status in ("OUT", "INACTIVE", "IR", "SUSPENDED") or (raw_status == "DOUBTFUL"):
            eligible_bench = [
                bp for bp in bench_players
                if (bp.position == player.position or re.slot_name in ("FLEX", "SUPERFLEX", "OP", "RB/WR", "WR/TE"))
                and (bp.injury_status or "ACTIVE").upper() not in ("OUT", "INACTIVE", "IR", "DOUBTFUL")
            ]
            eligible_bench.sort(key=lambda b: b.projected_points, reverse=True)
            top_sub = eligible_bench[0] if eligible_bench else None

            # Look up waiver alternative if bench has no backup
            top_waiver = None
            if not top_sub:
                all_waiver_players = db.execute(
                    select(PlayerModel)
                    .where(PlayerModel.position == player.position)
                    .order_by(PlayerModel.projected_points.desc())
                ).scalars().all()
                rostered_ids = {e.player_id for e, _ in entries}
                healthy_fa = [p for p in all_waiver_players if p.id not in rostered_ids and (p.injury_status or "ACTIVE").upper() not in ("OUT", "INACTIVE", "IR", "DOUBTFUL")]
                top_waiver = healthy_fa[0] if healthy_fa else None

            msg = (
                f"🚨 CRITICAL: Starter {player.full_name} ({player.position}) is {raw_status}."
                + (f" Replace with bench {top_sub.full_name} ({top_sub.position}, {top_sub.projected_points:.1f} pts)." if top_sub else (f" No bench backup; top waiver target is {top_waiver.full_name} ({top_waiver.projected_points:.1f} pts)." if top_waiver else " No healthy replacement found."))
            )

            critical_inactives.append(
                InactiveAlertItem(
                    starter_id=player.id,
                    starter_name=player.full_name,
                    position=player.position,
                    injury_status=raw_status,
                    pro_team=player.pro_team,
                    slot_name=re.slot_name,
                    starter_proj=player.projected_points,
                    recommended_bench_id=top_sub.id if top_sub else None,
                    recommended_bench_name=top_sub.full_name if top_sub else None,
                    recommended_bench_pos=top_sub.position if top_sub else None,
                    recommended_bench_proj=round(top_sub.projected_points, 1) if top_sub else 0.0,
                    top_waiver_id=top_waiver.id if top_waiver else None,
                    top_waiver_name=top_waiver.full_name if top_waiver else None,
                    top_waiver_pos=top_waiver.position if top_waiver else None,
                    top_waiver_proj=round(top_waiver.projected_points, 1) if top_waiver else 0.0,
                    net_projected_pts=round(top_sub.projected_points - player.projected_points, 1) if top_sub else 0.0,
                    alert_message=msg,
                )
            )

    return InactiveAlertsResponse(
        team_id=target_team_id,
        has_critical_inactives=len(critical_inactives) > 0,
        alerts_count=len(critical_inactives),
        alerts=critical_inactives,
    )


@router.post("/emergency-pivot", response_model=EmergencyPivotResponse)
async def execute_emergency_pivot(
    req: EmergencyPivotRequest,
    db: Session = Depends(get_db),
) -> EmergencyPivotResponse:
    """Execute immediate emergency bench-to-starter swap in local database."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found.")

    target_team_id = req.team_id or league.user_team_id or 1

    starter_res = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
            RosterEntryModel.player_id == req.starter_id,
        )
    ).first()

    bench_res = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
            RosterEntryModel.player_id == req.bench_id,
        )
    ).first()

    if not starter_res or not bench_res:
        raise HTTPException(status_code=404, detail="Starter or bench player entry not found for this team.")

    starter_entry, starter_player = starter_res
    bench_entry, bench_player = bench_res

    # Swap slots atomically
    orig_starter_slot_id = starter_entry.lineup_slot_id
    orig_starter_slot_name = starter_entry.slot_name

    starter_entry.lineup_slot_id = bench_entry.lineup_slot_id
    starter_entry.slot_name = bench_entry.slot_name
    starter_entry.is_starter = False

    bench_entry.lineup_slot_id = orig_starter_slot_id
    bench_entry.slot_name = orig_starter_slot_name
    bench_entry.is_starter = True

    db.commit()

    return EmergencyPivotResponse(
        success=True,
        message=f"Emergency pivot executed: Started {bench_player.full_name} in {orig_starter_slot_name} slot. {starter_player.full_name} moved to bench.",
        starter_name=starter_player.full_name,
        bench_name=bench_player.full_name,
        from_slot=orig_starter_slot_name,
        to_slot=starter_entry.slot_name,
        moves_executed=1,
    )

