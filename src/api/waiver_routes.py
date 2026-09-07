import asyncio
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
