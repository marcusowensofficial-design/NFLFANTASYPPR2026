"""NFL Positional Outcome Distribution & Monte Carlo Percentile Engine.

Models realistic right-tail ceiling outcomes, floor projections, and boom/bust probabilities
for NFL fantasy and DFS scoring. GPP tournaments are won by 85th and 95th percentile right-tail
outcomes, not by mean point projections.
"""

from typing import Any, Dict, Optional
import numpy as np
from pydantic import BaseModel
import scipy.stats as stats


class QuantDistributionResult(BaseModel):
    mean: float
    floor_10th: float
    median_50th: float
    ceiling_85th: float
    ceiling_95th: float
    boom_probability_25pt: float
    bust_probability_6pt: float
    variance_cv: float
    distribution_type: str


class PositionalDistributionEngine:
    """Parametric distribution model calibrated against historical NFL DFS outcome variances."""

    # Baseline Coefficient of Variation (std_dev / mean) by position & archetype
    CV_REGIMES = {
        "QB": {
            "DUAL_THREAT": 0.36,
            "POCKET": 0.30,
            "DEFAULT": 0.32,
        },
        "RB": {
            "TRUE_BELLCOW": 0.40,
            "COMMITTEE_LEAD": 0.48,
            "PASSING_DOWN": 0.52,
            "DEFAULT": 0.45,
        },
        "WR": {
            "ALPHA_TARGET_MONSTER": 0.46,
            "VERTICAL_FIELD_STRETCHER": 0.65,
            "SLOT_VACUUM": 0.42,
            "DEFAULT": 0.52,
        },
        "TE": {
            "ALPHA_RECEIVING_TE": 0.48,
            "INLINE_BLOCKING_TD_DEPENDENT": 0.68,
            "DEFAULT": 0.55,
        },
        "DST": {
            "ELITE_SACK_TURNOVER": 0.62,
            "DEFAULT": 0.70,
        },
        "K": {
            "DOME_HIGH_OPPORTUNITY": 0.38,
            "DEFAULT": 0.44,
        },
    }

    @classmethod
    def get_cv(cls, pos: str, archetype: Optional[str] = None) -> float:
        clean_pos = (pos or "").upper().strip()
        regime = cls.CV_REGIMES.get(clean_pos, {"DEFAULT": 0.45})
        if archetype and archetype.upper() in regime:
            return regime[archetype.upper()]
        return regime.get("DEFAULT", 0.45)

    @classmethod
    def calculate_distribution(
        cls,
        pos: str,
        projected_mean: float,
        archetype: Optional[str] = None,
        adot: Optional[float] = None,
        hvt_share: Optional[float] = None,
    ) -> QuantDistributionResult:
        """Calculates exact 10th, 50th, 85th, and 95th percentiles plus boom/bust probabilities.

        Args:
            pos: Position (QB, RB, WR, TE, DST, K)
            projected_mean: Mean projected fantasy points (Half-PPR or PPR)
            archetype: Optional archetype string for CV refinement
            adot: Optional Average Depth of Target (elevates WR variance)
            hvt_share: Optional High-Value Touch share (tightens RB floor)
        """
        clean_pos = (pos or "FLEX").upper().strip()
        mean = max(0.1, float(projected_mean))

        cv = cls.get_cv(clean_pos, archetype)

        # Micro-adjust CV based on aDOT or HVT
        if clean_pos == "WR" and adot is not None and adot > 13.0:
            cv = min(0.75, cv + 0.08)  # High aDOT increases right-tail boom potential
        elif clean_pos == "RB" and hvt_share is not None and hvt_share > 0.65:
            cv = max(0.35, cv - 0.05)  # Consolidated goal-line touches stabilize floor

        std = mean * cv

        # Position-specific parametric distribution family
        if clean_pos in ("QB", "K"):
            # Normal distribution (additive passing yards, field goals)
            dist = stats.norm(loc=mean, scale=std)
            dist_name = "NORMAL"

            floor_10 = max(0.0, float(dist.ppf(0.10)))
            med_50 = float(dist.ppf(0.50))
            ceil_85 = float(dist.ppf(0.85))
            ceil_95 = float(dist.ppf(0.95))

            # Survival function (1 - CDF) for P(X >= 25.0)
            boom_prob = float(dist.sf(25.0))
            bust_prob = float(dist.cdf(6.0))

        elif clean_pos in ("RB", "DST"):
            # Lognormal distribution (multi-TD spikes, right-skewed)
            # Parametrization: s = sigma, scale = exp(mu)
            sigma = np.sqrt(np.log(1 + cv ** 2))
            scale = mean / np.sqrt(1 + cv ** 2)
            dist = stats.lognorm(s=sigma, scale=scale)
            dist_name = "LOGNORMAL"

            floor_10 = max(0.0, float(dist.ppf(0.10)))
            med_50 = float(dist.ppf(0.50))
            ceil_85 = float(dist.ppf(0.85))
            ceil_95 = float(dist.ppf(0.95))

            boom_prob = float(dist.sf(25.0))
            bust_prob = float(dist.cdf(6.0))

        else:
            # WR / TE: Gamma distribution (compound Poisson target events & yardage)
            # Parametrization: a = k (shape) = 1 / cv^2, scale = mean * cv^2
            k = 1.0 / (cv ** 2)
            theta = mean * (cv ** 2)
            dist = stats.gamma(a=k, scale=theta)
            dist_name = "GAMMA"

            floor_10 = max(0.0, float(dist.ppf(0.10)))
            med_50 = float(dist.ppf(0.50))
            ceil_85 = float(dist.ppf(0.85))
            ceil_95 = float(dist.ppf(0.95))

            boom_prob = float(dist.sf(25.0))
            bust_prob = float(dist.cdf(6.0))

        # Enforce realistic ceiling bounds and non-negativity
        floor_10 = round(max(0.0, floor_10), 2)
        med_50 = round(max(floor_10, med_50), 2)
        ceil_85 = round(max(med_50, ceil_85), 2)
        ceil_95 = round(max(ceil_85, ceil_95), 2)
        boom_prob = round(float(np.clip(boom_prob, 0.0, 1.0)), 4)
        bust_prob = round(float(np.clip(bust_prob, 0.0, 1.0)), 4)

        return QuantDistributionResult(
            mean=round(mean, 2),
            floor_10th=floor_10,
            median_50th=med_50,
            ceiling_85th=ceil_85,
            ceiling_95th=ceil_95,
            boom_probability_25pt=boom_prob,
            bust_probability_6pt=bust_prob,
            variance_cv=round(cv, 3),
            distribution_type=dist_name,
        )


distribution_engine = PositionalDistributionEngine()
