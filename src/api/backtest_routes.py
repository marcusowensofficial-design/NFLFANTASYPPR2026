"""API routes for backtesting audits and automated model weight tuning."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import LeagueModel
from src.db.session import get_db
from src.services.backtesting.evaluator import (
    BacktestReport,
    WeightTuningResult,
    backtest_evaluator,
)
from src.services.recommendation.scoring_engine import scoring_engine

router = APIRouter(prefix="/api/backtest", tags=["Backtesting"])


@router.get("/report", response_model=BacktestReport)
def get_backtest_report(
    team_id: int | None = Query(default=None, description="Optional team ID (defaults to user team)"),
    db: Session = Depends(get_db),
) -> BacktestReport:
    """Run retrospective accuracy audit on completed weeks."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No league data found in database.")

    target_team = team_id or league.user_team_id or 1
    metrics = backtest_evaluator.audit_week(
        db=db,
        league_id=league.id,
        team_id=target_team,
        week=league.current_week,
        weights=scoring_engine.weights,
    )

    return BacktestReport(
        total_weeks_audited=1,
        overall_accuracy_pct=metrics.accuracy_pct,
        overall_efficiency_pct=metrics.efficiency_pct,
        current_weights=scoring_engine.weights,
        weekly_breakdowns=[metrics],
    )


@router.post("/tune", response_model=WeightTuningResult)
def run_weight_tuning(
    team_id: int | None = Query(default=None, description="Optional team ID (defaults to user team)"),
    db: Session = Depends(get_db),
) -> WeightTuningResult:
    """Run weight tuning optimizer to maximize retrospective start/sit accuracy."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No league data found in database.")

    target_team = team_id or league.user_team_id or 1
    return backtest_evaluator.tune_weights(
        db=db,
        league_id=league.id,
        team_id=target_team,
        current_weights=scoring_engine.weights,
    )
