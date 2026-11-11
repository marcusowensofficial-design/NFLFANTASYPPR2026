"""Backtesting and weight tuning evaluator comparing recommendations against actual fantasy points."""

import logging
import math
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PlayerModel, RosterEntryModel, WeeklyProjectionHistoryModel
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


class SourceAccuracyMetrics(BaseModel):
    source: str
    display_name: str
    weeks_evaluated: int
    sample_size: int
    mae: float
    rmse: float
    bias: float
    corr_r: float
    coverage_10th_pct: float | None = None
    coverage_85th_pct: float | None = None
    coverage_95th_pct: float | None = None


class BacktestReport(BaseModel):
    total_weeks_audited: int
    overall_accuracy_pct: float
    overall_efficiency_pct: float
    current_weights: ScoringWeights
    weekly_breakdowns: list[WeeklyAuditMetrics]
    scoring_format: str = "HALF_PPR"
    evaluated_weeks: list[int] = Field(default_factory=list)
    source_leaderboard: list[SourceAccuracyMetrics] = Field(default_factory=list)


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
        week: int | None = None,
    ) -> WeightTuningResult:
        """Run systematic parameter grid search to find weights strictly maximizing retrospective accuracy."""
        from src.db.models import LeagueModel
        target_week = week
        if target_week is None:
            league = db.execute(select(LeagueModel).where(LeagueModel.id == league_id)).scalar_one_or_none()
            target_week = max(1, (league.current_week - 1) if (league and league.current_week) else 1)

        baseline_audit = self.audit_week(db, league_id, team_id, week=target_week, weights=current_weights)
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
            cand_audit = self.audit_week(db, league_id, team_id, week=target_week, weights=cand_norm)
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

    def build_source_leaderboard(
        self,
        db: Session,
        season: int = 2026,
        max_week: int | None = None,
        scoring_format: str = "HALF_PPR",
    ) -> tuple[list[int], list[SourceAccuracyMetrics]]:
        """Aggregate multi-week MAE, RMSE, Bias, Pearson r, and coverage across projection sources."""
        fmt = "HALF_PPR" if "HALF" in (scoring_format or "").upper() else "PPR"
        stmt = select(WeeklyProjectionHistoryModel).where(
            WeeklyProjectionHistoryModel.season == season,
            WeeklyProjectionHistoryModel.scoring_format == fmt,
            WeeklyProjectionHistoryModel.actual_pts.isnot(None),
            WeeklyProjectionHistoryModel.is_bye.is_(False),
        )
        if max_week is not None and max_week > 0:
            stmt = stmt.where(WeeklyProjectionHistoryModel.week <= max_week)

        rows = db.execute(stmt).scalars().all()
        if not rows:
            return [], []

        evaluated_weeks = sorted({int(r.week) for r in rows})
        source_specs = [
            ("ENSEMBLE", "Ensemble (Quant+XGB+Props)", "ensemble_pts", True),
            ("MODEL", "Quant Model", "quant_pts", True),
            ("XGBOOST", "XGBoost ML", "xgboost_pts", False),
            ("SLEEPER", "Sleeper", "sleeper_pts", False),
            ("CONSENSUS", "Consensus", "consensus_pts", False),
            ("FANTASYPROS", "FantasyPros", "fp_pts", False),
            ("ESPN", "ESPN", "espn_pts", False),
            ("PROPS", "Vegas Props", "props_pts", False),
        ]

        leaderboard: list[SourceAccuracyMetrics] = []
        for src_code, label, col_name, track_cov in source_specs:
            pairs: list[tuple[float, float]] = []
            weeks_seen: set[int] = set()
            cov_rows: list[tuple[float, float, float, float]] = []

            for r in rows:
                pred = float(getattr(r, col_name) or 0.0)
                act = float(r.actual_pts or 0.0)
                if pred <= 0.0:
                    continue
                if max(float(r.quant_pts or 0.0), float(r.sleeper_pts or 0.0), act) < 4.0:
                    continue
                pairs.append((pred, act))
                weeks_seen.add(int(r.week))
                if track_cov and float(r.floor_10th or 0.0) > 0.0 and float(r.ceiling_95th or 0.0) > 0.0:
                    cov_rows.append((act, float(r.floor_10th), float(r.ceiling_85th), float(r.ceiling_95th)))

            n = len(pairs)
            if n == 0:
                continue

            abs_errs = [abs(p - a) for p, a in pairs]
            sq_errs = [(p - a) ** 2 for p, a in pairs]
            diffs = [p - a for p, a in pairs]
            mae = round(sum(abs_errs) / n, 3)
            rmse = round(math.sqrt(sum(sq_errs) / n), 3)
            bias = round(sum(diffs) / n, 3)

            mean_p = sum(p for p, _ in pairs) / n
            mean_a = sum(a for _, a in pairs) / n
            cov = sum((p - mean_p) * (a - mean_a) for p, a in pairs)
            var_p = sum((p - mean_p) ** 2 for p, _ in pairs)
            var_a = sum((a - mean_a) ** 2 for _, a in pairs)
            denom = math.sqrt(var_p * var_a)
            corr_r = round(cov / denom, 3) if denom > 0 else 0.0

            cov10 = cov85 = cov95 = None
            if cov_rows:
                cn = len(cov_rows)
                cov10 = round(100.0 * sum(1 for a, f10, _, _ in cov_rows if a < f10) / cn, 1)
                cov85 = round(100.0 * sum(1 for a, _, c85, _ in cov_rows if a > c85) / cn, 1)
                cov95 = round(100.0 * sum(1 for a, _, _, c95 in cov_rows if a > c95) / cn, 1)

            leaderboard.append(
                SourceAccuracyMetrics(
                    source=src_code,
                    display_name=label,
                    weeks_evaluated=len(weeks_seen),
                    sample_size=n,
                    mae=mae,
                    rmse=rmse,
                    bias=bias,
                    corr_r=corr_r,
                    coverage_10th_pct=cov10,
                    coverage_85th_pct=cov85,
                    coverage_95th_pct=cov95,
                )
            )

        leaderboard.sort(key=lambda m: (m.mae, m.rmse))
        return evaluated_weeks, leaderboard



backtest_evaluator = BacktestingEvaluator()
