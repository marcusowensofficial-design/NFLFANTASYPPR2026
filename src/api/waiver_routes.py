from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.adapters.weather.client import weather_client
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel
from src.db.session import get_db
from src.services.recommendation.scoring_engine import (
    StartSitEvaluation,
    scoring_engine,
)
from src.services.waiver.scanner import (
    WaiverAnalysisResult,
    WaiverUpgradeRecommendation,
    waiver_scanner,
)

router = APIRouter(prefix="/api/waiver", tags=["Waiver Wire"])


@router.get("/upgrades", response_model=WaiverAnalysisResult)
async def get_waiver_upgrades(
    team_id: int | None = Query(default=None, description="Optional team ID (defaults to user team)"),
    db: Session = Depends(get_db),
) -> WaiverAnalysisResult:
    """Scan available unowned players and return high-impact lineup upgrades and streaming options with live context."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No league data found. Sync ESPN first.")

    target_team_id = team_id or league.user_team_id or 1

    # Get user roster players
    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
        )
    ).all()

    # Fetch live NFL schedule (current and next week) and injuries concurrently in parallel
    target_next_week = league.current_week + 1
    nfl_games, next_week_games, injuries_by_athlete = await asyncio.gather(
        nfl_schedule_client.fetch_week_schedule(season=league.season, week=league.current_week),
        nfl_schedule_client.fetch_week_schedule(season=league.season, week=target_next_week),
        nfl_injuries_client.fetch_injuries(),
    )

    home_teams = {g.home_team for g in nfl_games if g.home_team and g.home_team != "UNK"}
    weather_reports = await asyncio.gather(*(weather_client.get_stadium_weather(ht) for ht in home_teams))
    weather_by_home_team = dict(zip(home_teams, weather_reports))

    games_by_team = {}
    weather_by_team = {}
    for g in nfl_games:
        games_by_team[g.home_team] = g
        games_by_team[g.away_team] = g
        w = weather_by_home_team.get(g.home_team)
        weather_by_team[g.home_team] = w
        weather_by_team[g.away_team] = w

    user_evals: list[StartSitEvaluation] = []
    league_size = league.size or 8
    for _, p in entries:
        game = games_by_team.get(p.pro_team)
        weather = weather_by_team.get(p.pro_team)
        injury = injuries_by_athlete.get(p.id)
        ev = scoring_engine.evaluate_player(
            p,
            nfl_game=game,
            injury_report=injury,
            weather=weather,
            league_size=league_size,
        )
        user_evals.append(ev)

    return waiver_scanner.scan_upgrades(
        db=db,
        league_id=league.id,
        user_team_id=target_team_id,
        user_roster_evaluations=user_evals,
        games_by_team=games_by_team,
        injuries_by_athlete=injuries_by_athlete,
        weather_by_team=weather_by_team,
        league_size=league_size,
        current_week=league.current_week,
        next_week_games=next_week_games,
    )


@router.get("/consensus-board")
def get_consensus_waiver_board(
    team_id: int | None = Query(default=None, description="Optional team ID"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the full 2026 Week 3 Internet Expert Consensus Waiver Board with live league availability."""
    from src.services.waiver.expert_consensus_service import expert_consensus_service
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raw = expert_consensus_service.load_consensus_data()
        return {"season": 2026, "week": 3, "positions": raw.get("positions", {}), "positional_needs": []}

    target_team_id = team_id or league.user_team_id or 1
    expert_consensus_service.ensure_consensus_players_in_db(db)

    # Get user roster
    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
        )
    ).all()
    user_evals = [scoring_engine.evaluate_player(p, league_size=league.size or 8) for _, p in entries]

    # Query all rostered players in league to guarantee zero taken players in recommendations
    rostered_rows = db.execute(
        select(PlayerModel.id, PlayerModel.full_name, PlayerModel.pro_team, PlayerModel.position)
        .join(RosterEntryModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(RosterEntryModel.league_id == league.id)
    ).all()
    rostered_pids = {r[0] for r in rostered_rows}
    rostered_names = {r[1].lower().replace(".", "").replace("'", "").strip() for r in rostered_rows if r[1]}
    rostered_names_clean = {
        r[1].lower().replace(".", "").replace("'", "").replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", "").strip()
        for r in rostered_rows if r[1]
    }
    rostered_names.update(rostered_names_clean)
    rostered_dst_teams = {r[2].upper() for r in rostered_rows if r[3] and r[3].upper() in ("D/ST", "DST") and r[2]}

    needs = expert_consensus_service.analyze_team_positional_needs(
        user_roster_evaluations=user_evals,
        league_size=league.size or 8,
        rostered_names=rostered_names,
        rostered_pids=rostered_pids,
        rostered_dst_teams=rostered_dst_teams,
    )
    board = expert_consensus_service.get_consensus_board_with_availability(db, league.id, target_team_id, needs)

    return {
        "success": True,
        "season": 2026,
        "week": league.current_week,
        "positional_needs": [n.model_dump() for n in needs],
        "positions": {pos: [p.model_dump() for p in players] for pos, players in board.items()},
        "consensus_board": {pos: [p.model_dump() for p in players] for pos, players in board.items()},
    }

