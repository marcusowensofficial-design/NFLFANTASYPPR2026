import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.adapters.weather.client import weather_client
from src.db.models import LeagueModel, PlayerModel, RosterEntryModel, UserSettingsModel
from src.db.session import get_db
from src.services.recommendation.comparator import ComparisonResult, player_comparator
from src.services.recommendation.start_sit_factor_scores import (
    calculate_comparator_factors_for_evaluation,
)
from src.services.recommendation.scoring_engine import (
    ScoringWeights,
    StartSitEvaluation,
    scoring_engine,
    sort_factor_reasons,
)
from src.services.trade.trade_analyzer import (
    ConsolidationTradeAnalysisResult,
    trade_analyzer,
)

router = APIRouter(prefix="/api/recommendation", tags=["Recommendation"])


class CompareRequest(BaseModel):
    player_ids: list[int] = Field(min_length=2, max_length=4, description="List of 2 to 4 player IDs to compare")
    mode: str = Field(default="BALANCED", description="Strategy mode: BALANCED, CEILING, or FLOOR")
    projection_source: str = Field(default="MODEL", description="Projection source: MODEL, FANTASYPROS, SLEEPER, ESPN, or CONSENSUS")


class ScoringSettings(BaseModel):
    league_size: int = 8
    weights: ScoringWeights


@router.post("/compare", response_model=ComparisonResult)
async def compare_players(payload: CompareRequest, db: Session = Depends(get_db)) -> ComparisonResult:
    """Compare 2 to 4 players side-by-side with full factor breakdown, live weather, injuries, and close-call detection."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    season = league.season if league else 2026
    week = league.current_week if league else 1
    league_size = league.size if league else 8

    players = db.execute(
        select(PlayerModel).where(PlayerModel.id.in_(payload.player_ids))
    ).scalars().all()

    if len(players) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Found only {len(players)} valid players in database out of requested IDs.",
        )

    # Fetch live schedule, injuries, and weather in parallel
    nfl_games, injuries_by_athlete = await asyncio.gather(
        nfl_schedule_client.fetch_week_schedule(season=season, week=week),
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

    evaluations: list[StartSitEvaluation] = []
    player_dict = {p.id: p for p in players}
    for pid in payload.player_ids:
        p = player_dict.get(pid)
        if not p:
            continue
        game = games_by_team.get(p.pro_team)
        weather = weather_by_team.get(p.pro_team)
        injury = injuries_by_athlete.get(p.id)
        ev = scoring_engine.evaluate_player(
            p,
            nfl_game=game,
            injury_report=injury,
            weather=weather,
            mode=payload.mode,
            league_size=league_size,
            projection_source=payload.projection_source,
        )

        # Apply Start/Sit Comparator specific factor calibrations and transparency
        factors = calculate_comparator_factors_for_evaluation(ev, nfl_game=game, weather=weather)
        ev.components.projection_score = factors.projection.score
        ev.components.opportunity_score = factors.opportunity.score
        ev.components.matchup_score = factors.matchup.score
        ev.components.environment_score = factors.environment.score
        ev.comparator_factors = factors.model_dump()

        # Recalculate ev.start_score from the calibrated factors for complete mathematical truth
        w = scoring_engine.weights
        calibrated_composite = (
            w.projection_weight * factors.projection.score
            + w.opportunity_weight * factors.opportunity.score
            + w.matchup_weight * factors.matchup.score
            + w.environment_weight * factors.environment.score
            + w.health_weight * ev.components.health_score
            + w.weather_weight * ev.components.weather_score
        )
        mode_upper = payload.mode.upper()
        if mode_upper == "CEILING":
            calibrated_composite = (calibrated_composite * 0.40) + (ev.ceiling_score * 0.60)
        elif mode_upper == "FLOOR":
            calibrated_composite = (calibrated_composite * 0.40) + (ev.floor_score * 0.60)
        ev.start_score = round(max(0.0, min(100.0, calibrated_composite)), 1)

        # Harmonize positive/negative evaluation drivers with the 4 factor scores
        factor_reasons = (
            factors.projection.reasons
            + factors.opportunity.reasons
            + factors.matchup.reasons
            + factors.environment.reasons
        )
        for fr in factor_reasons:
            if any(k in fr for k in ("[Projection]", "[Volume]", "[PPR Leverage]", "[Matchup]", "[Environment]", "[Weather]")):
                if any(warn in fr for warn in ("⚠️", "🛑", "Low", "Capped", "Sub-Baseline", "Below-Average", "Trench Slog")):
                    if fr not in ev.reasons_negative:
                        ev.reasons_negative.insert(0, fr)
                else:
                    if fr not in ev.reasons_positive:
                        ev.reasons_positive.insert(0, fr)

        def _dedupe_reasons(lst: list[str]) -> list[str]:
            seen = set()
            out = []
            for item in lst:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

        ev.reasons_positive = sort_factor_reasons(_dedupe_reasons(ev.reasons_positive))
        ev.reasons_negative = sort_factor_reasons(_dedupe_reasons(ev.reasons_negative))

        evaluations.append(ev)

    return player_comparator.compare(evaluations)


@router.get("/weights", response_model=ScoringWeights)
def get_weights(db: Session = Depends(get_db)) -> ScoringWeights:
    """Retrieve current Start/Sit scoring weights."""
    row = db.execute(select(UserSettingsModel).where(UserSettingsModel.id == 1)).scalar_one_or_none()
    if row and row.weights:
        scoring_engine.weights = ScoringWeights(**row.weights).normalize()
    return scoring_engine.weights


@router.post("/weights", response_model=ScoringWeights)
def update_weights(new_weights: ScoringWeights, db: Session = Depends(get_db)) -> ScoringWeights:
    """Update Start/Sit scoring weights and persist to database."""
    scoring_engine.weights = new_weights.normalize()
    row = db.execute(select(UserSettingsModel).where(UserSettingsModel.id == 1)).scalar_one_or_none()
    if not row:
        row = UserSettingsModel(id=1, league_size=scoring_engine.league_size, weights_json=scoring_engine.weights.model_dump_json())
        db.add(row)
    else:
        row.weights_json = scoring_engine.weights.model_dump_json()
    db.commit()
    return scoring_engine.weights


@router.get("/settings", response_model=ScoringSettings)
def get_settings(db: Session = Depends(get_db)) -> ScoringSettings:
    """Retrieve current Start/Sit scoring settings and league size calibration."""
    row = db.execute(select(UserSettingsModel).where(UserSettingsModel.id == 1)).scalar_one_or_none()
    if row:
        scoring_engine.league_size = row.league_size
        if row.weights:
            scoring_engine.weights = ScoringWeights(**row.weights).normalize()
    return ScoringSettings(
        league_size=scoring_engine.league_size,
        weights=scoring_engine.weights,
    )


@router.post("/settings", response_model=ScoringSettings)
def update_settings(settings: ScoringSettings, db: Session = Depends(get_db)) -> ScoringSettings:
    """Update Start/Sit scoring settings including league size calibration and persist to database."""
    scoring_engine.league_size = settings.league_size
    scoring_engine.weights = settings.weights.normalize()

    row = db.execute(select(UserSettingsModel).where(UserSettingsModel.id == 1)).scalar_one_or_none()
    if not row:
        row = UserSettingsModel(id=1, league_size=settings.league_size, weights_json=settings.weights.model_dump_json())
        db.add(row)
    else:
        row.league_size = settings.league_size
        row.weights_json = settings.weights.model_dump_json()
    db.commit()

    return ScoringSettings(
        league_size=scoring_engine.league_size,
        weights=scoring_engine.weights,
    )


@router.get("/trades/consolidation", response_model=ConsolidationTradeAnalysisResult)
async def get_consolidation_trades(
    league_id: int | None = None,
    team_id: int | None = None,
    league_size: int | None = None,
    db: Session = Depends(get_db),
) -> ConsolidationTradeAnalysisResult:
    """Analyze and generate high-leverage 2-for-1 consolidation trades for 8-man leagues."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found. Sync ESPN first.")

    target_league_id = league_id or league.id
    target_team_id = team_id or league.user_team_id or 1
    eff_league_size = league_size or league.size or 8

    # Retrieve user's roster
    entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == target_league_id,
            RosterEntryModel.team_id == target_team_id,
        )
    ).all()

    if not entries:
        raise HTTPException(status_code=404, detail=f"No roster entries found for team {target_team_id}.")

    # Fetch schedule context
    nfl_games = await nfl_schedule_client.fetch_week_schedule(season=league.season, week=league.current_week)
    games_by_team = {g.home_team: g for g in nfl_games}
    for g in nfl_games:
        games_by_team[g.away_team] = g

    user_evals = [
        scoring_engine.evaluate_player(
            player,
            nfl_game=games_by_team.get(player.pro_team),
            league_size=eff_league_size,
        )
        for _, player in entries
    ]

    return trade_analyzer.analyze_consolidation_trades(
        db=db,
        league_id=target_league_id,
        user_team_id=target_team_id,
        user_roster_evaluations=user_evals,
        league_size=eff_league_size,
    )
