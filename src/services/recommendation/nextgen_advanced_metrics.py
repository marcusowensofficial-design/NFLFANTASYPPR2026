"""Next-Gen Positional Quantitative Metrics Engine.

Provides high-signal, non-noisy quantitative modeling across all positions:
1. Expected Fantasy Points (xFP) & Fantasy Points Over Expected (FPOE):
   - Computes expected fantasy value of opportunities based on field position, down, distance, and air yards.
   - Detects 'Coiled Spring' positive regression candidates (high xFP, negative FPOE) and 'Mirage' sell/fade candidates.
2. Scheme & Defensive Coverage Shell Matching (Man vs Zone, MOFC vs MOFO):
   - Receiver TPRR/YPRR vs Zone and Man cross-referenced with opponent defensive shell rates.
   - Boosts slot receivers & TEs vs Middle-Field Open (MOFO - Cover 2/4/6); boosts boundary X/Z alphas vs Middle-Field Closed (MOFC - Cover 1/3) & Cover 0 blitz.
3. QB Pressure Response & Ball Redistribution:
   - Scramble rate % under pressure (Josh Allen, Lamar Jackson) driving rushing ceiling.
   - Checkdown rate % to RB under pressure (Jared Goff, Patrick Mahomes) driving RB receiving floor.
   - Pressure-to-Sack (P2S) rates driving D/ST sack and turnover expectancy.
4. Goal-Line Package Distribution & High-Value Touch (HVT) Equity:
   - Inside-the-5 carry and touch shares by personnel grouping (11 vs 12 vs Jumbo).
   - Red-zone target shares for tight ends in multi-TE heavy formations.
"""

from dataclasses import dataclass, field
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class XFPCalculationResult:
    """Expected Fantasy Points output separating volume opportunity from realized variance."""
    xfp_ppr: float
    xfp_half_ppr: float
    realized_ppr: float
    realized_half_ppr: float
    fpoe_ppr: float  # Realized - xFP (>0 is running hot/fluke; <0 is coiled spring buy)
    fpoe_half_ppr: float
    regression_signal: str  # "COILED_SPRING_BUY", "NEUTRAL_FAIR_VALUE", "MIRAGE_FADE_CANDIDATE"
    opportunity_tier: str


class ExpectedFantasyPointsCalculator:
    """Calculates empirical Expected Fantasy Points (xFP) for individual opportunities.
    
    Weights:
    - Target: Air yards, red-zone distance, and end-zone target equity.
      Baseline NFL median expected points per target:
      - Deep target (aDOT >= 15): 1.65 Half-PPR / 2.15 Full-PPR
      - Intermediate target (aDOT 8-14): 1.15 Half-PPR / 1.65 Full-PPR
      - Short / checkdown target (aDOT < 8): 0.78 Half-PPR / 1.28 Full-PPR
      - End-zone target: 2.35 Half-PPR / 2.85 Full-PPR
    - Carry: Distance to end-zone.
      - Carry inside the 5-yard line: 2.10 Half/Full PPR (approx 35% TD probability + yards)
      - Carry 6-10 yard line: 0.95 Half/Full PPR
      - Carry 11-20 yard line: 0.62 Half/Full PPR
      - Between the 20s carry: 0.42 Half/Full PPR
    - Pass Attempt (QB):
      - Standard pass attempt: 0.44 FP
      - Red-zone pass attempt: 0.92 FP
    """

    @staticmethod
    def calculate_player_xfp(
        targets: float,
        adot: float = 8.5,
        endzone_targets: float = 0.0,
        carries_inside_5: float = 0.0,
        carries_6_to_10: float = 0.0,
        carries_between_20s: float = 0.0,
        rush_att_qb: float = 0.0,
        pass_att_qb: float = 0.0,
        realized_ppr: float = 0.0,
        realized_half_ppr: float = 0.0,
        pos: str = "WR",
    ) -> XFPCalculationResult:
        p = pos.upper().strip()
        xfp_ppr = 0.0
        xfp_half = 0.0

        if p in ("WR", "TE"):
            # Target opportunity value
            base_targets = max(0.0, targets - endzone_targets)
            if adot >= 14.0:
                t_val_half = 1.62
                t_val_full = 2.12
            elif adot >= 8.0:
                t_val_half = 1.18
                t_val_full = 1.68
            else:
                t_val_half = 0.82
                t_val_full = 1.32

            xfp_half += (base_targets * t_val_half) + (endzone_targets * 2.35)
            xfp_ppr += (base_targets * t_val_full) + (endzone_targets * 2.85)

            # Rushing equity if any (e.g. Deebo, WR jet sweeps)
            xfp_half += (carries_between_20s * 0.42) + (carries_inside_5 * 2.10)
            xfp_ppr += (carries_between_20s * 0.42) + (carries_inside_5 * 2.10)

        elif p in ("RB", "FB"):
            # Rushing opportunity value
            xfp_rush = (
                (carries_inside_5 * 2.10)
                + (carries_6_to_10 * 0.95)
                + (carries_between_20s * 0.42)
            )
            # Receiving opportunity value
            t_val_half = 0.88
            t_val_full = 1.38
            xfp_rec_half = targets * t_val_half + (endzone_targets * 1.50)
            xfp_rec_full = targets * t_val_full + (endzone_targets * 1.50)

            xfp_half = xfp_rush + xfp_rec_half
            xfp_ppr = xfp_rush + xfp_rec_full

        elif p == "QB":
            # Passing opportunity value
            xfp_pass = pass_att_qb * 0.45
            # Rushing opportunity value (designed runs + scrambles)
            xfp_rush = (rush_att_qb * 0.72) + (carries_inside_5 * 1.85)
            xfp_half = xfp_pass + xfp_rush
            xfp_ppr = xfp_half

        else:
            xfp_half = realized_half_ppr
            xfp_ppr = realized_ppr

        xfp_ppr = round(xfp_ppr, 2)
        xfp_half = round(xfp_half, 2)
        fpoe_ppr = round(realized_ppr - xfp_ppr, 2)
        fpoe_half = round(realized_half_ppr - xfp_half, 2)

        # Classify Coiled Spring vs Mirage
        if fpoe_half <= -2.5 and xfp_half >= 10.0:
            reg_sig = "COILED_SPRING_BUY"
        elif fpoe_half >= 4.0 and xfp_half <= 8.5:
            reg_sig = "MIRAGE_FADE_CANDIDATE"
        else:
            reg_sig = "NEUTRAL_FAIR_VALUE"

        # Classify Opportunity Tier
        if xfp_half >= 16.0:
            opp_tier = "ELITE_BELLCOW_ALPHA"
        elif xfp_half >= 12.0:
            opp_tier = "HIGH_VOLUME_STARTER"
        elif xfp_half >= 7.5:
            opp_tier = "FLEX_ROTATIONAL"
        else:
            opp_tier = "PUNT_VALUATION"

        return XFPCalculationResult(
            xfp_ppr=xfp_ppr,
            xfp_half_ppr=xfp_half,
            realized_ppr=realized_ppr,
            realized_half_ppr=realized_half_ppr,
            fpoe_ppr=fpoe_ppr,
            fpoe_half_ppr=fpoe_half,
            regression_signal=reg_sig,
            opportunity_tier=opp_tier,
        )


class CoverageShellMatcher:
    """Matches receiver scheme metrics (TPRR vs Zone, TPRR vs Man) against opponent coverage shells.
    
    MOFO (Cover 2, Cover 4, Cover 6) - Two-High safeties:
    - Protects deep boundaries.
    - Yields high target and reception volume to slot receivers, tight ends, and running back checkdowns.
    
    MOFC (Cover 1, Cover 3) - Single-High safety:
    - Stacks the box and closes the middle.
    - Leaves boundary receivers in 1-on-1 isolated single coverage.
    """

    @staticmethod
    def calculate_scheme_multiplier(
        pos: str,
        slot_rate_pct: float,
        tprr_vs_zone: float,
        tprr_vs_man: float,
        opp_mofo_pct: float,
        opp_mofc_pct: float,
        opp_blitz_rate_pct: float = 20.0,
    ) -> tuple[float, str]:
        """Returns a multiplier (e.g. 0.90 to 1.15) and descriptive rationale."""
        p = pos.upper().strip()
        mult = 1.0
        reasons = []

        is_slot_heavy = slot_rate_pct >= 45.0 or p == "TE"
        is_boundary = slot_rate_pct <= 25.0 and p == "WR"

        # 1. MOFO Alignment (Buffalo 61.8%, Seattle 59.5%, NYG 58.4%)
        if opp_mofo_pct >= 55.0:
            if is_slot_heavy:
                # Slot and TE funnel
                zone_edge = max(0.0, (tprr_vs_zone - 0.20) * 0.5)
                boost = 0.08 + zone_edge
                mult += min(0.14, boost)
                reasons.append(f"High MOFO ({opp_mofo_pct:.1f}%) funnels intermediate volume to slot/TE")
            elif is_boundary:
                # Boundary receivers capped by 2-high safeties
                mult -= 0.05
                reasons.append(f"Two-high MOFO shell ({opp_mofo_pct:.1f}%) caps boundary explosive routes")

        # 2. MOFC Alignment (Carolina 63.2%, Houston 78.2%, Detroit 49.2%)
        elif opp_mofc_pct >= 50.0:
            if is_boundary:
                # 1-on-1 isolation opportunities
                man_edge = max(0.0, (tprr_vs_man - 0.22) * 0.5)
                boost = 0.07 + man_edge
                mult += min(0.12, boost)
                reasons.append(f"Single-high MOFC ({opp_mofc_pct:.1f}%) yields 1-on-1 boundary isolations")
            elif is_slot_heavy:
                # Tighter intermediate zones
                reasons.append("Single-high box concentration")

        # 3. Blitz / Cover 0 Tendency (Detroit 15.9% Blitz 0, Indianapolis 10.0%)
        if opp_blitz_rate_pct >= 12.0:
            if tprr_vs_man >= 0.25:
                mult += 0.05
                reasons.append(f"Elite separator vs blitz man coverage ({opp_blitz_rate_pct:.1f}% blitz)")

        mult = round(max(0.88, min(1.18, mult)), 3)
        reason_str = "; ".join(reasons) if reasons else "Neutral defensive coverage shell"
        return mult, reason_str


class QBPressureRedistributor:
    """Quantifies how QB behavior transforms under defensive line pressure."""

    @staticmethod
    def calculate_redistribution(
        is_dual_threat: bool,
        scramble_rate_pressured: float,
        checkdown_rate_pressured: float,
        p2s_rate: float,
        opp_pressure_pct: float,
    ) -> dict[str, Any]:
        """Calculates adjustments to QB rushing attempts, RB checkdown targets, and D/ST sack expectation."""
        # Baseline NFL pressure rate is ~30%
        pressure_delta = (opp_pressure_pct - 30.0) / 100.0

        qb_rush_att_boost = 0.0
        rb_target_boost = 0.0
        dst_sack_boost = 0.0

        if opp_pressure_pct >= 32.0:
            if is_dual_threat and scramble_rate_pressured >= 14.0:
                # Scramble surge (e.g. Josh Allen 18.5%, Lamar 21%)
                qb_rush_att_boost = round(2.0 + (pressure_delta * 4.0), 1)
            else:
                # Pocket passer under heat checks down to backfield
                if checkdown_rate_pressured >= 18.0:
                    rb_target_boost = round(1.2 + (pressure_delta * 3.0), 1)

            # Sacks scaled by QB's individual Pressure-to-Sack (P2S) rate
            # High P2S (Caleb Williams 28%) gets sacked constantly; Low P2S (Josh Allen 12.5%) evades
            dst_sack_boost = round((p2s_rate / 15.0) * pressure_delta * 2.5, 2)

        return {
            "qb_rush_att_boost": qb_rush_att_boost,
            "rb_target_boost": rb_target_boost,
            "dst_sack_boost": max(0.0, dst_sack_boost),
        }


class GoalLinePackageEquity:
    """Calculates inside-the-5 touchdown expectancy based on personnel grouping frequencies."""

    @staticmethod
    def calculate_td_equity(
        inside_5_carry_share: float,
        gl_11_personnel_pct: float,
        gl_12_personnel_pct: float,
        gl_jumbo_pct: float,
        expected_team_tds: float,
    ) -> dict[str, float]:
        """Calculates touchdown expectation for RB bellcow vs TE2 / rotational vultures."""
        # 12 and Jumbo personnel heavily favor primary power backs and second tight ends
        rb_monopoly_boost = (gl_jumbo_pct + gl_12_personnel_pct * 0.7) / 100.0 * 0.15
        adjusted_rb_inside_5_share = min(0.95, inside_5_carry_share * (1.0 + rb_monopoly_boost))

        rb_rush_td_exp = round(adjusted_rb_inside_5_share * (expected_team_tds * 0.60), 2)
        
        # TE2 end-zone equity in 12-personnel heavy offenses (Buffalo Dawson Knox)
        te2_td_exp = round((gl_12_personnel_pct / 100.0) * 0.35 * (expected_team_tds * 0.65), 2)

        return {
            "rb_rush_td_expectancy": rb_rush_td_exp,
            "te2_endzone_td_expectancy": te2_td_exp,
            "inside_5_carry_share_calibrated": round(adjusted_rb_inside_5_share, 3),
        }
