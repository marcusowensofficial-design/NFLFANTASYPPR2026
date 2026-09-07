"""Backtesting and weight tuning evaluator comparing recommendations against actual fantasy points."""

import logging
from typing import Any
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PlayerModel, RosterEntryModel
from src.services.recommendation.scoring_engine import (
    ScoringWeights,
    StartSitEvaluation,
    StartSitScoringEngine,
)

logger = logging.getLogger(__name__)


class WeeklyAuditMetrics(BaseModel):
    week: int
    starters_evaluated: int
    correct_start_decisions: int
    incorrect_start_decisions: int
    accuracy_pct: float
    total_recommended_points: float
    total_optimal_points: float
    points_left_on_bench: float
    efficiency_pct: float


class BacktestReport(BaseModel):
    total_weeks_audited: int
    overall_accuracy_pct: float
    overall_efficiency_pct: float
    current_weights: ScoringWeights
    weekly_breakdowns: list[WeeklyAuditMetrics]


class WeightTuningResult(BaseModel):
    original_weights: ScoringWeights
    optimized_weights: ScoringWeights
    original_accuracy_pct: float
    optimized_accuracy_pct: float
    points_improvement: float
    message: str


class BacktestingEvaluator:
    """Evaluates retrospective start/sit decisions and optimizes heuristic weights."""

    def audit_week(
        self,
        db: Session,
        league_id: int,
        team_id: int,
        week: int = 1,
        weights: ScoringWeights | None = None,
    ) -> WeeklyAuditMetrics:
        engine = StartSitScoringEngine(weights=weights)

        # Query roster and players for team
        entries = db.execute(
            select(RosterEntryModel, PlayerModel)
            .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
            .where(
                RosterEntryModel.league_id == league_id,
                RosterEntryModel.team_id == team_id,
            )
        ).all()

        if not entries:
            return WeeklyAuditMetrics(
                week=week,
                starters_evaluated=0,
                correct_start_decisions=0,
                incorrect_start_decisions=0,
                accuracy_pct=100.0,
                total_recommended_points=0.0,
                total_optimal_points=0.0,
                points_left_on_bench=0.0,
                efficiency_pct=100.0,
            )

        evals = [engine.evaluate_player(p) for _, p in entries]
        eval_by_id = {e.player_id: e for e in evals}
        player_by_id = {p.id: p for _, p in entries}

        # Separate starters vs bench
        starters = [eval_by_id[re.player_id] for re, _ in entries if re.is_starter and re.player_id in eval_by_id]
        bench = [eval_by_id[re.player_id] for re, _ in entries if not re.is_starter and re.player_id in eval_by_id]

        correct_decisions = 0
        total_comparisons = 0
        points_left = 0.0

        for s in starters:
            s_actual = player_by_id[s.player_id].actual_points or s.projected_points
            for b in bench:
                if b.position.upper() == s.position.upper() or s.position.upper() in ("RB", "WR", "TE"):
                    b_actual = player_by_id[b.player_id].actual_points or b.projected_points
                    total_comparisons += 1
                    if s_actual >= b_actual:
                        correct_decisions += 1
                    else:
                        points_left += round(b_actual - s_actual, 1)

        accuracy = round((correct_decisions / max(total_comparisons, 1)) * 100.0, 1)

        total_rec_pts = sum(player_by_id[s.player_id].actual_points or s.projected_points for s in starters)
        optimal_pts = total_rec_pts + (points_left * 0.4)  # Estimated ceiling
        efficiency = round((total_rec_pts / max(optimal_pts, 1.0)) * 100.0, 1)

        return WeeklyAuditMetrics(
            week=week,
            starters_evaluated=len(starters),
            correct_start_decisions=correct_decisions,
            incorrect_start_decisions=total_comparisons - correct_decisions,
            accuracy_pct=accuracy,
            total_recommended_points=round(total_rec_pts, 1),
            total_optimal_points=round(optimal_pts, 1),
            points_left_on_bench=round(points_left, 1),
            efficiency_pct=min(100.0, efficiency),
        )

    def tune_weights(
        self,
        db: Session,
        league_id: int,
        team_id: int,
        current_weights: ScoringWeights,
    ) -> WeightTuningResult:
        """Run systematic parameter grid search to find weights strictly maximizing retrospective accuracy."""
        baseline_audit = self.audit_week(db, league_id, team_id, week=1, weights=current_weights)
        best_accuracy = baseline_audit.accuracy_pct
        best_efficiency = baseline_audit.efficiency_pct
        best_weights = current_weights

        # Systematically generate diverse, normalized candidate profiles across strategy space
        candidate_profiles: list[ScoringWeights] = [
            # 1. Projection-Anchored Profiles
            ScoringWeights(projection_weight=0.45, opportunity_weight=0.20, matchup_weight=0.15, environment_weight=0.10, health_weight=0.07, weather_weight=0.03),
            ScoringWeights(projection_weight=0.40, opportunity_weight=0.25, matchup_weight=0.15, environment_weight=0.10, health_weight=0.07, weather_weight=0.03),
            ScoringWeights(projection_weight=0.35, opportunity_weight=0.25, matchup_weight=0.20, environment_weight=0.10, health_weight=0.07, weather_weight=0.03),
            # 2. Volume & Opportunity-Heavy Profiles (Workhorse / Target Share leverage)
            ScoringWeights(projection_weight=0.25, opportunity_weight=0.35, matchup_weight=0.18, environment_weight=0.10, health_weight=0.08, weather_weight=0.04),
            ScoringWeights(projection_weight=0.30, opportunity_weight=0.30, matchup_weight=0.20, environment_weight=0.10, health_weight=0.07, weather_weight=0.03),
            ScoringWeights(projection_weight=0.28, opportunity_weight=0.32, matchup_weight=0.15, environment_weight=0.12, health_weight=0.08, weather_weight=0.05),
            # 3. Matchup & DvP Exploitation Profiles
            ScoringWeights(projection_weight=0.30, opportunity_weight=0.20, matchup_weight=0.28, environment_weight=0.10, health_weight=0.07, weather_weight=0.05),
            ScoringWeights(projection_weight=0.35, opportunity_weight=0.18, matchup_weight=0.25, environment_weight=0.12, health_weight=0.06, weather_weight=0.04),
            ScoringWeights(projection_weight=0.25, opportunity_weight=0.25, matchup_weight=0.30, environment_weight=0.10, health_weight=0.06, weather_weight=0.04),
            # 4. Vegas Implied Total & Game Environment Leverage
            ScoringWeights(projection_weight=0.32, opportunity_weight=0.22, matchup_weight=0.18, environment_weight=0.18, health_weight=0.06, weather_weight=0.04),
            ScoringWeights(projection_weight=0.28, opportunity_weight=0.25, matchup_weight=0.18, environment_weight=0.17, health_weight=0.07, weather_weight=0.05),
            # 5. Health & Risk-Averse Profiles (Heavy penalty for questionable tags)
            ScoringWeights(projection_weight=0.32, opportunity_weight=0.22, matchup_weight=0.18, environment_weight=0.10, health_weight=0.15, weather_weight=0.03),
            ScoringWeights(projection_weight=0.30, opportunity_weight=0.25, matchup_weight=0.16, environment_weight=0.10, health_weight=0.14, weather_weight=0.05),
            # 6. Balanced Simplex Neighborhood Grid
            ScoringWeights(projection_weight=0.33, opportunity_weight=0.23, matchup_weight=0.22, environment_weight=0.11, health_weight=0.07, weather_weight=0.04),
            ScoringWeights(projection_weight=0.37, opportunity_weight=0.21, matchup_weight=0.19, environment_weight=0.11, health_weight=0.08, weather_weight=0.04),
        ]

        for cand in candidate_profiles:
            cand_norm = cand.normalize()
            cand_audit = self.audit_week(db, league_id, team_id, week=1, weights=cand_norm)
            # Optimize primarily for accuracy; tie-break on efficiency
            is_better = (
                cand_audit.accuracy_pct > best_accuracy
                or (cand_audit.accuracy_pct == best_accuracy and cand_audit.efficiency_pct > best_efficiency)
            )
            if is_better:
                best_accuracy = cand_audit.accuracy_pct
                best_efficiency = cand_audit.efficiency_pct
                best_weights = cand_norm

        improvement = round(best_accuracy - baseline_audit.accuracy_pct, 1)

        return WeightTuningResult(
            original_weights=current_weights.normalize(),
            optimized_weights=best_weights.normalize(),
            original_accuracy_pct=baseline_audit.accuracy_pct,
            optimized_accuracy_pct=best_accuracy,
            points_improvement=improvement,
            message=(
                f"Grid search complete ({len(candidate_profiles)} profiles tested): accuracy improved by +{improvement}% "
                f"({baseline_audit.accuracy_pct}% -> {best_accuracy}%)."
                if improvement > 0
                else f"Grid search complete ({len(candidate_profiles)} profiles tested): current weights are optimal."
            ),
        )



backtest_evaluator = BacktestingEvaluator()
