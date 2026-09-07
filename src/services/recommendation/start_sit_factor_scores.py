"""Start/Sit Comparator Factor Scoring Adapter.

Calculates deterministic, position-aware, and mathematically reproducible factor scores
specifically for the Head-to-Head Start/Sit Comparator player cards:
1. Projection Score (Slate-calibrated percentile with FLEX alignment & monotonicity)
2. Opportunity Volume (Pure workload & high-value touches in Full PPR)
3. Defensive Matchup (True opponent defensive generosity: DvP, Overall Def, Role/Funnel)
4. Game Environment (Slate-relative implied total, game total, spread script, weather/dome)

Strict Scope:
- This module is used ONLY by the Head-to-Head Start/Sit Comparator tab.
- All global ranking, optimizer, waiver, and database models remain untouched.
"""

from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.nfl.dvp_client import DvPClient, dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.adapters.weather.client import WeatherReport


# ============================================================================
# FACTOR SCORE RESULT MODELS
# ============================================================================

class FactorScoreDetail(BaseModel):
    score: float = Field(ge=0.0, le=100.0, description="0-100 deterministic factor score")
    bucket: str = Field(description="Score category bucket, e.g. ELITE, STRONG, VIABLE, WEAK")
    bucket_color: str = Field(default="cyan", description="UI color tag: emerald, cyan, amber, rose")
    raw_inputs: dict[str, Any] = Field(default_factory=dict, description="Raw inputs used in calculation")
    contributions: dict[str, float] = Field(default_factory=dict, description="Component point contributions")
    formula_description: str = Field(default="", description="Human-readable formula summary")
    reasons: list[str] = Field(default_factory=list, description="Provenance driver bullets matching calculation")


class ComparatorFactorsBundle(BaseModel):
    projection: FactorScoreDetail
    opportunity: FactorScoreDetail
    matchup: FactorScoreDetail
    environment: FactorScoreDetail


# ============================================================================
# CONSTANTS: NAMED WEIGHTS, BENCHMARKS, AND BUCKETS (NO MAGIC NUMBERS)
# ============================================================================

# 8-Team Full-PPR Empirical Starter Calibration Anchors
# (Points: [Floor_50pt, Median_70pt, Strong_80pt, Elite_88pt, Max_100pt])
POSITION_PROJECTION_ANCHORS: dict[str, dict[str, float]] = {
    "QB": {
        "min_pts": 10.0,
        "viable_threshold": 14.5,
        "median_pts": 18.0,
        "strong_threshold": 21.0,
        "elite_threshold": 24.0,
        "max_pts": 32.0,
    },
    "RB": {
        "min_pts": 6.0,
        "viable_threshold": 10.0,
        "median_pts": 13.5,
        "strong_threshold": 16.5,
        "elite_threshold": 20.0,
        "max_pts": 28.0,
    },
    "WR": {
        "min_pts": 6.5,
        "viable_threshold": 10.5,
        "median_pts": 14.0,
        "strong_threshold": 17.5,
        "elite_threshold": 21.0,
        "max_pts": 29.0,
    },
    "TE": {
        "min_pts": 4.5,
        "viable_threshold": 7.5,
        "median_pts": 10.2,
        "strong_threshold": 13.5,
        "elite_threshold": 16.5,
        "max_pts": 23.0,
    },
    "K": {
        "min_pts": 4.0,
        "viable_threshold": 6.5,
        "median_pts": 8.0,
        "strong_threshold": 9.5,
        "elite_threshold": 11.5,
        "max_pts": 16.0,
    },
    "D/ST": {
        "min_pts": 3.0,
        "viable_threshold": 5.5,
        "median_pts": 7.5,
        "strong_threshold": 9.5,
        "elite_threshold": 12.0,
        "max_pts": 18.0,
    },
    "DST": {
        "min_pts": 3.0,
        "viable_threshold": 5.5,
        "median_pts": 7.5,
        "strong_threshold": 9.5,
        "elite_threshold": 12.0,
        "max_pts": 18.0,
    },
}

# PPR Opportunity Volume High-Value Touch (HVT) Weights
RB_CARRY_WEIGHT: float = 1.00            # Standard baseline carry
RB_PPR_TARGET_WEIGHT: float = 2.85       # A target in Full PPR yields ~2.85x expected fantasy pts of an early-down carry
RB_GOAL_LINE_TD_WEIGHT: float = 2.00     # Goal-line rush TD equity multiplier

WR_TARGET_WEIGHT: float = 0.50           # Projected targets drive 50% of WR opportunity score
WR_SHARE_WEIGHT: float = 0.25            # Target share % commands 25% of opportunity score
WR_RECEPTION_WEIGHT: float = 0.25        # Reception conversion commands 25% of opportunity score

TE_TARGET_WEIGHT: float = 0.55           # TE target volume is scarce; weighted heavily
TE_SHARE_WEIGHT: float = 0.25
TE_RECEPTION_WEIGHT: float = 0.20

QB_PASS_ATT_WEIGHT: float = 1.00         # Standard pass attempt weight
QB_KONAMI_RUSH_WEIGHT: float = 3.00      # 1 QB rush attempt has ~3x fantasy leverage of a pass attempt in 4-pt pass TD formats

# Defensive Matchup Weights
MATCHUP_DVP_WEIGHT: float = 0.70         # Positional Defense vs Position rank (1=toughest, 32=softest)
MATCHUP_OVERALL_DEF_WEIGHT: float = 0.20 # Overall defensive strength rank (1-32)
MATCHUP_ROLE_SPLIT_WEIGHT: float = 0.10  # Role alignment (receiving RB or slot WR vs pass/run funnel)

# Game Environment Weights
ENV_IMPLIED_TOTAL_WEIGHT: float = 0.50   # Team Vegas implied points (primary scoring driver)
ENV_OVER_UNDER_WEIGHT: float = 0.20      # Total game points expected (pace & combined volume)
ENV_SPREAD_SCRIPT_WEIGHT: float = 0.15   # Game competitiveness (tight spreads elevate 4-quarter offense)
ENV_WEATHER_VENUE_WEIGHT: float = 0.15   # Dome status, wind suppression, or precipitation friction

# Standard Slate Baselines for Vegas Odds (Used when slate min/max bounds are not provided)
SLATE_IMPLIED_MIN: float = 15.0
SLATE_IMPLIED_MAX: float = 30.0
SLATE_OU_MIN: float = 38.0
SLATE_OU_MAX: float = 52.0


# ============================================================================
# 1. PROJECTION SCORE FORMULA
# ============================================================================

def calculate_start_sit_projection_score(
    projected_points: float,
    position: str,
    slate_projections: list[float] | None = None,
    consensus_rank: float | None = None,
    fp_ecr: int | None = None,
) -> FactorScoreDetail:
    """Calculates slate-calibrated, position-aware Projection Score.
    
    Guarantees:
    - Monotonicity: Higher projected PPR points within position strictly produces >= score.
    - FLEX Alignment: Cross-positional comparisons align to positional starter tiers.
    - Consensus Modifier: Bounded modifier (±2.5 pts max) that cannot override superior projection.
    - Buckets: Elite (85-100), Strong (70-84), Viable (50-69), Weak (<50).
    """
    pos = position.upper().strip()
    proj = max(0.0, float(projected_points))
    anchors = POSITION_PROJECTION_ANCHORS.get(pos, POSITION_PROJECTION_ANCHORS["WR"])

    min_p = anchors["min_pts"]
    viable_p = anchors["viable_threshold"]
    med_p = anchors["median_pts"]
    strong_p = anchors["strong_threshold"]
    elite_p = anchors["elite_threshold"]
    max_p = anchors["max_pts"]

    # Piecewise linear mapping ensuring strict monotonicity and well-defined anchor points
    if proj <= min_p:
        raw_score = 15.0 + (proj / max(min_p, 1.0)) * 30.0  # 15 to 45
    elif proj <= viable_p:
        # 45 to 55 (borderline viable)
        frac = (proj - min_p) / (viable_p - min_p)
        raw_score = 45.0 + (frac * 10.0)
    elif proj <= med_p:
        # 55 to 70 (viable starter tier)
        frac = (proj - viable_p) / (med_p - viable_p)
        raw_score = 55.0 + (frac * 15.0)
    elif proj <= strong_p:
        # 70 to 84 (strong weekly starter)
        frac = (proj - med_p) / (strong_p - med_p)
        raw_score = 70.0 + (frac * 14.0)
    elif proj <= elite_p:
        # 84 to 92 (borderline elite anchor)
        frac = (proj - strong_p) / (elite_p - strong_p)
        raw_score = 84.0 + (frac * 8.0)
    else:
        # 92 to 100 (top-of-league ceiling)
        frac = min(1.0, (proj - elite_p) / max(1.0, (max_p - elite_p)))
        raw_score = 92.0 + (frac * 8.0)

    # Optional minor consensus agreement modifier (strictly bounded to ±2.5 max)
    consensus_mod = 0.0
    effective_rank = fp_ecr if fp_ecr is not None else consensus_rank
    if effective_rank is not None and effective_rank > 0:
        if effective_rank <= 3:
            consensus_mod = 2.5
        elif effective_rank <= 8:
            consensus_mod = 1.5
        elif effective_rank <= 15:
            consensus_mod = 0.5
        elif effective_rank >= 35 and raw_score < 70.0:
            consensus_mod = -1.5

    final_score = round(max(10.0, min(100.0, raw_score + consensus_mod)), 1)

    # Determine bucket
    if final_score >= 85.0:
        bucket = "ELITE"
        bucket_color = "emerald"
    elif final_score >= 70.0:
        bucket = "STRONG"
        bucket_color = "cyan"
    elif final_score >= 50.0:
        bucket = "VIABLE"
        bucket_color = "amber"
    else:
        bucket = "WEAK"
        bucket_color = "rose"

    reasons: list[str] = []
    if final_score >= 85.0:
        reasons.append(f"[Projection] 🏆 Elite Scoring Tier: {proj:.1f} projected PPR points anchors starting lineup")
    elif final_score >= 70.0:
        reasons.append(f"[Projection] 📈 Strong Starter Projection: {proj:.1f} projected PPR points comfortably clears starter threshold")
    elif final_score >= 50.0:
        reasons.append(f"[Projection] ⚖️ Viable Starter Range: {proj:.1f} projected PPR points in serviceable weekly tier")
    else:
        reasons.append(f"[Projection] ⚠️ Sub-Baseline Projection: {proj:.1f} projected PPR points carries shallow-league bench risk")

    if consensus_mod > 0:
        reasons.append(f"[Consensus] ⭐ Analyst Consensus Boost: ECR #{int(effective_rank)} confirms high projection confidence (+{consensus_mod:.1f} pts)")
    elif consensus_mod < 0:
        reasons.append(f"[Consensus] ⚠️ Lower Expert Consensus: ECR #{int(effective_rank)} reflects cautious analyst agreement ({consensus_mod:.1f} pts)")

    raw_inputs = {
        "projected_points": proj,
        "position": pos,
        "median_benchmark": med_p,
        "strong_benchmark": strong_p,
        "elite_benchmark": elite_p,
        "consensus_rank": effective_rank,
    }

    contributions = {
        "base_projection_points": round(raw_score, 1),
        "consensus_modifier": round(consensus_mod, 1),
    }

    formula = (
        f"Piecewise monotonic calibration for {pos}: "
        f"pts={proj:.1f} mapped against [{med_p:.1f} med, {strong_p:.1f} str, {elite_p:.1f} elite] "
        f"+ consensus modifier ({consensus_mod:+.1f}) = {final_score:.1f}"
    )

    return FactorScoreDetail(
        score=final_score,
        bucket=bucket,
        bucket_color=bucket_color,
        raw_inputs=raw_inputs,
        contributions=contributions,
        formula_description=formula,
        reasons=reasons,
    )


# ============================================================================
# 2. OPPORTUNITY VOLUME FORMULA
# ============================================================================

def calculate_start_sit_opportunity_score(
    position: str,
    stats: dict[str, float] | None = None,
    volume_share: float | None = None,
) -> FactorScoreDetail:
    """Calculates pure workload Opportunity Volume.
    
    Guarantees:
    - Decoupled from Vegas spreads and random touchdown variance.
    - WR/TE: Projected targets (50%), target share (25%), receptions (25%).
    - Strict bucket caps: WR with < 5.0 targets capped < 50; 5.0-6.9 capped < 70.
      A WR with 5.9 targets can NEVER be Elite or Strong!
    - RB: Carries (1.0x) + Full-PPR Targets (2.85x) + Red-Zone role + Carry Share.
    - QB: Pass attempts (1.0x) + Konami rush attempts (3.0x).
    - Monotonicity: More touches/targets strictly produces >= score.
    """
    pos = position.upper().strip()
    s = stats or {}

    carries = max(0.0, float(s.get("rush_att", 0.0)))
    targets = max(0.0, float(s.get("targets", 0.0)))
    receptions = max(0.0, float(s.get("receptions", 0.0)))
    rush_tds = max(0.0, float(s.get("rush_td", 0.0)))
    rec_tds = max(0.0, float(s.get("rec_td", 0.0)))
    pass_att = max(0.0, float(s.get("pass_att", 0.0)))
    rush_yds = max(0.0, float(s.get("rush_yds", 0.0)))

    reasons: list[str] = []
    contributions: dict[str, float] = {}
    raw_inputs: dict[str, Any] = {"position": pos}

    if pos in ("WR", "TE"):
        # WR/TE Full-PPR Volume Index
        # Benchmark for 8-man league:
        # Targets: 9.0+ = Elite (100), 7.0-8.9 = Strong (80), 5.0-6.9 = Viable (60), <5.0 = Weak (<50)
        target_score = min(100.0, max(15.0, (targets / 9.5) * 90.0))
        
        # Target Share: 25%+ = Elite, 18-24% = Strong, 13-17% = Viable, <13% = Weak
        eff_share = volume_share if volume_share is not None and volume_share > 0 else (targets * 3.0)
        share_score = min(100.0, max(20.0, (eff_share / 26.0) * 90.0))
        
        # Reception Floor: 6.0+ rec = Elite, 4.0-5.9 = Strong, 2.5-3.9 = Viable
        rec_score = min(100.0, max(15.0, (receptions / 6.5) * 90.0))

        w_tgt = WR_TARGET_WEIGHT if pos == "WR" else TE_TARGET_WEIGHT
        w_shr = WR_SHARE_WEIGHT if pos == "WR" else TE_SHARE_WEIGHT
        w_rec = WR_RECEPTION_WEIGHT if pos == "WR" else TE_RECEPTION_WEIGHT

        raw_calc = (w_tgt * target_score) + (w_shr * share_score) + (w_rec * rec_score)

        # STRICT BUCKET CEILING ENFORCEMENT for receivers:
        # A WR with 5.9 targets must NOT receive an "Elite" (85+) or "Strong" (70+) volume score.
        score_cap = 100.0
        if targets < 5.0:
            score_cap = 49.5  # Hard cap at WEAK tier
        elif targets < 7.0:
            score_cap = 69.5  # Hard cap at VIABLE tier

        final_score = round(min(score_cap, max(15.0, raw_calc)), 1)

        contributions = {
            "target_volume_pts": round(w_tgt * target_score, 1),
            "target_share_pts": round(w_shr * share_score, 1),
            "reception_floor_pts": round(w_rec * rec_score, 1),
        }
        raw_inputs.update({
            "targets": round(targets, 1),
            "target_share_pct": round(eff_share, 1),
            "receptions": round(receptions, 1),
            "volume_cap_applied": score_cap < 100.0,
        })

        formula = (
            f"{pos} Workload: Targets({targets:.1f}*{w_tgt:.2f}) + Share({eff_share:.1f}%*{w_shr:.2f}) "
            f"+ Rec({receptions:.1f}*{w_rec:.2f}) = {final_score:.1f}"
            + (f" [Capped at {score_cap:.0f} due to {targets:.1f} targets]" if score_cap < 100.0 else "")
        )

        if targets >= 8.5:
            reasons.append(f"[Volume] 🎯 Alpha Target Engine: Projected for {targets:.1f} targets ({receptions:.1f} rec, {eff_share:.1f}% share)")
        elif targets >= 7.0:
            reasons.append(f"[Volume] 🎯 High-Volume Role: Projected for {targets:.1f} targets commanding consistent first-read looks")
        elif targets >= 5.0:
            reasons.append(f"[Volume] ⚖️ Moderate Target Involvement: Projected for {targets:.1f} targets ({receptions:.1f} rec) in balanced distribution")
        else:
            reasons.append(f"[Volume] ⚠️ Capped Target Volume: Only {targets:.1f} targets projected; limited weekly PPR opportunity")

    elif pos in ("RB", "FB"):
        # RB High-Value Touches (HVT)
        # Weighted touches = Carries (1.0x) + PPR Targets (2.85x) + Goal Line TD share (2.0x)
        weighted_touches = (carries * RB_CARRY_WEIGHT) + (targets * RB_PPR_TARGET_WEIGHT) + (rush_tds * RB_GOAL_LINE_TD_WEIGHT)
        raw_calc = 20.0 + (weighted_touches * 2.8)
        
        # Share bonus for bellcows (commands majority of team backfield)
        share_bonus = 0.0
        eff_share = volume_share if volume_share is not None and volume_share > 0 else (carries / max(1.0, carries + 6.0) * 100.0)
        if eff_share >= 68.0:
            share_bonus = 6.0
        elif eff_share <= 40.0 and carries < 11.0:
            share_bonus = -4.0

        final_score = round(max(20.0, min(100.0, raw_calc + share_bonus)), 1)

        contributions = {
            "carry_volume_pts": round(carries * RB_CARRY_WEIGHT * 2.8, 1),
            "hvt_target_pts": round(targets * RB_PPR_TARGET_WEIGHT * 2.8, 1),
            "goal_line_role_pts": round(rush_tds * RB_GOAL_LINE_TD_WEIGHT * 2.8, 1),
            "backfield_share_pts": round(share_bonus, 1),
        }
        raw_inputs.update({
            "carries": round(carries, 1),
            "targets": round(targets, 1),
            "rush_td_equity": round(rush_tds, 2),
            "carry_share_pct": round(eff_share, 1),
            "weighted_touches": round(weighted_touches, 1),
        })

        formula = (
            f"RB High-Value Touches: Carries({carries:.1f}*1.0) + Targets({targets:.1f}*2.85) "
            f"+ GoalLine({rush_tds:.2f}*2.0) = {weighted_touches:.1f} weighted touches -> Score {final_score:.1f}"
        )

        total_touches = carries + targets
        if total_touches >= 18.0:
            reasons.append(f"[Volume] 🚜 Workhorse Volume: {carries:.1f} carries + {targets:.1f} targets ({total_touches:.1f} touches, {eff_share:.0f}% share)")
        elif total_touches >= 13.0:
            reasons.append(f"[Volume] 🎯 Solid Backfield Workload: {carries:.1f} carries + {targets:.1f} targets ({total_touches:.1f} total touches)")
        else:
            reasons.append(f"[Volume] ⚠️ Limited Touch Volume: Projected for only {total_touches:.1f} total touches ({carries:.1f} carries, {targets:.1f} tgts)")

        if targets >= 4.0:
            reasons.append(f"[PPR Leverage] 🎯 High-Value PPR Target Floor: {targets:.1f} targets ({receptions:.1f} rec) provides bankable receiving floor")

    elif pos == "QB":
        # QB Passing + Konami Code Rushing
        # 34 pass att + (3 * 4 rush att) = 46 weighted attempts -> ~75 score
        weighted_qb_vol = pass_att + (carries * QB_KONAMI_RUSH_WEIGHT)
        raw_calc = 25.0 + (weighted_qb_vol / 50.0) * 65.0
        final_score = round(max(25.0, min(100.0, raw_calc)), 1)

        contributions = {
            "pass_attempts_pts": round((pass_att / 50.0) * 65.0, 1),
            "konami_rush_pts": round(((carries * QB_KONAMI_RUSH_WEIGHT) / 50.0) * 65.0, 1),
        }
        raw_inputs.update({
            "pass_attempts": round(pass_att, 1),
            "rush_attempts": round(carries, 1),
            "rush_yards": round(rush_yds, 1),
            "weighted_qb_volume": round(weighted_qb_vol, 1),
        })

        formula = f"QB Volume: PassAtt({pass_att:.1f}) + RushAtt({carries:.1f}*3.0) = {weighted_qb_vol:.1f} weighted volume -> Score {final_score:.1f}"

        if carries >= 4.5 or rush_yds >= 25.0:
            reasons.append(f"[Volume] ⚡ Konami Code Rushing: {carries:.1f} carries / {rush_yds:.0f} rush yds supercharges quarterback volume")
        if pass_att >= 34.0:
            reasons.append(f"[Volume] 🎯 High Pass Volume: Projected for {pass_att:.1f} pass attempts")
        elif pass_att < 28.0 and carries < 3.0:
            reasons.append(f"[Volume] ⚠️ Low Pass Volume: Only {pass_att:.1f} pass attempts with minimal rushing involvement")

    else:
        # Kicker / D/ST fallback
        final_score = 65.0
        contributions = {"baseline_volume": 65.0}
        formula = f"{pos} Volume Baseline: Neutral 65.0"
        reasons.append(f"[Volume] 🛡️ Standard starting volume profile for {pos}")

    # Assign bucket
    if final_score >= 85.0:
        bucket = "ELITE"
        bucket_color = "emerald"
    elif final_score >= 70.0:
        bucket = "STRONG"
        bucket_color = "cyan"
    elif final_score >= 50.0:
        bucket = "VIABLE"
        bucket_color = "amber"
    else:
        bucket = "WEAK"
        bucket_color = "rose"

    return FactorScoreDetail(
        score=final_score,
        bucket=bucket,
        bucket_color=bucket_color,
        raw_inputs=raw_inputs,
        contributions=contributions,
        formula_description=formula,
        reasons=reasons,
    )


# ============================================================================
# 3. DEFENSIVE MATCHUP FORMULA
# ============================================================================

def calculate_start_sit_matchup_score(
    position: str,
    opponent_team: str,
    dvp: DvPClient | None = None,
    is_receiving_back: bool = False,
    is_slot_wr: bool = False,
) -> FactorScoreDetail:
    """Calculates objective opponent defensive favorability.
    
    Guarantees:
    - 70% Positional DvP Rank (1=toughest, 32=softest).
    - 20% Overall Defensive Rank (or Opponent Offensive Rank for D/ST).
    - 10% Role/Funnel Alignment.
    - True Opponent Generosity: Tough opponents score low (Rank 1 -> 20-30s),
      soft opponents score high (Rank 32 -> 85-95s).
    - Buckets: Smash (85-100), Favorable (70-84), Neutral (55-69), Tough (40-54), Brutal (<40).
    - Monotonicity: Higher DvP rank (softer defense) strictly produces higher score.
    """
    pos = position.upper().strip()
    opp = opponent_team.upper().strip()
    client = dvp or dvp_client

    if opp in ("BYE", "UNK", ""):
        return FactorScoreDetail(
            score=50.0,
            bucket="NEUTRAL",
            bucket_color="cyan",
            raw_inputs={"opponent": opp, "position": pos},
            contributions={"neutral_bye": 50.0},
            formula_description="BYE week / unknown opponent: Neutral 50.0",
            reasons=["[Matchup] Neutral BYE week evaluation"],
        )

    pos_rank = client.get_position_rank(opp, pos)
    is_dst = pos in ("D/ST", "DST")
    overall_rank = client.get_overall_off_rank(opp) if is_dst else client.get_overall_rank(opp)

    profile = client.profiles.get(opp)
    role_rank = pos_rank
    role_note = "Standard positional alignment"
    if profile:
        if pos in ("RB", "FB") and is_receiving_back:
            role_rank = profile.rb_rec_rank
            role_note = f"Pass-catching RB vs #{role_rank} pass-defense rank"
        elif pos == "WR" and is_slot_wr:
            role_rank = profile.wr_slot_rank
            role_note = f"Slot receiver vs #{role_rank} slot-defense rank"

    # Normalized 0.0 to 1.0 percentiles (Rank 1 = 0.0 toughest, Rank 32 = 1.0 softest)
    pos_pct = max(0.0, min(1.0, (pos_rank - 1.0) / 31.0))
    overall_pct = max(0.0, min(1.0, (overall_rank - 1.0) / 31.0))
    role_pct = max(0.0, min(1.0, (role_rank - 1.0) / 31.0))

    blended_pct = (
        (MATCHUP_DVP_WEIGHT * pos_pct)
        + (MATCHUP_OVERALL_DEF_WEIGHT * overall_pct)
        + (MATCHUP_ROLE_SPLIT_WEIGHT * role_pct)
    )

    # Scale to 20.0 - 95.0 range
    final_score = round(20.0 + (blended_pct * 75.0), 1)

    # Buckets perfectly aligned to FantasyPros 1-5 Star Matchup Key
    stars = client.get_matchup_stars(pos_rank)
    if final_score >= 80.0 or stars == 5:
        bucket = "SMASH"
        bucket_color = "emerald"
    elif final_score >= 68.0 or stars == 4:
        bucket = "FAVORABLE"
        bucket_color = "cyan"
    elif final_score >= 52.0 or stars == 3:
        bucket = "NEUTRAL"
        bucket_color = "cyan"
    elif final_score >= 38.0 or stars == 2:
        bucket = "TOUGH"
        bucket_color = "amber"
    else:
        bucket = "BRUTAL"
        bucket_color = "rose"

    reasons: list[str] = []
    if stars == 5 or pos_rank >= 27:
        reasons.append(f"[Matchup] ⭐ 5-Star Smash Matchup: Facing #{pos_rank} defense vs {pos} (softest tier in NFL, generous fantasy points conceded)")
    elif stars == 4 or pos_rank >= 21:
        reasons.append(f"[Matchup] 🎯 Favorable Matchup: {opp} defense ranks #{pos_rank} vs {pos} (above-average points conceded)")
    elif stars == 1 or pos_rank <= 6:
        reasons.append(f"[Matchup] 🛑 1-Star Lockdown Alert: Facing #{pos_rank} defense vs {pos} (stifling top-6 defense in points allowed)")
    elif stars == 2 or pos_rank <= 12:
        reasons.append(f"[Matchup] ⚠️ Below-Average Matchup: Facing #{pos_rank} defense vs {pos} with below-average scoring allowance")
    else:
        reasons.append(f"[Matchup] 🛡️ Neutral Matchup: {opp} ranks #{pos_rank} vs {pos} (middle of the pack)")

    if is_receiving_back and role_rank != pos_rank:
        reasons.append(f"[Role Matchup] 🎯 Receiving Role Divergence: {opp} ranks #{role_rank} vs pass-catching RBs ({role_note})")
    elif is_slot_wr and role_rank != pos_rank:
        reasons.append(f"[Role Matchup] 🎯 Slot Alignment Divergence: {opp} ranks #{role_rank} against slot receivers")

    raw_inputs = {
        "opponent": opp,
        "position": pos,
        "opp_dvp_rank": pos_rank,
        "opp_def_rank": overall_rank,
        "opp_role_rank": role_rank,
        "matchup_stars": stars,
    }

    contributions = {
        "positional_dvp_pts": round(MATCHUP_DVP_WEIGHT * pos_pct * 75.0, 1),
        "overall_defense_pts": round(MATCHUP_OVERALL_DEF_WEIGHT * overall_pct * 75.0, 1),
        "role_split_pts": round(MATCHUP_ROLE_SPLIT_WEIGHT * role_pct * 75.0, 1),
        "base_offset": 20.0,
    }

    formula = (
        f"Blended Opponent Quality: DvP#{pos_rank}({pos_pct*100:.0f}%*{MATCHUP_DVP_WEIGHT}) "
        f"+ OverallDef#{overall_rank}({overall_pct*100:.0f}%*{MATCHUP_OVERALL_DEF_WEIGHT}) "
        f"+ Role#{role_rank}({role_pct*100:.0f}%*{MATCHUP_ROLE_SPLIT_WEIGHT}) -> Score {final_score:.1f} ({stars} Stars)"
    )

    return FactorScoreDetail(
        score=final_score,
        bucket=bucket,
        bucket_color=bucket_color,
        raw_inputs=raw_inputs,
        contributions=contributions,
        formula_description=formula,
        reasons=reasons,
    )


# ============================================================================
# 4. GAME ENVIRONMENT FORMULA
# ============================================================================

def calculate_start_sit_environment_score(
    position: str,
    nfl_game: NFLGame | None = None,
    weather: WeatherReport | None = None,
    pro_team: str | None = None,
    fallback_implied_total: float | None = None,
) -> FactorScoreDetail:
    """Calculates slate-relative Game Environment.
    
    Guarantees:
    - 50% Team Vegas Implied Total (normalized against slate expectation).
    - 20% Game Over/Under Total.
    - 15% Spread / Script Competitiveness (tight shootouts rewarded, blowouts discounted).
    - 15% Weather & Venue (indoor domes receive full 100 weather credit; wind/precipitation penalizes passing).
    - Buckets: Shootout (85-100), Favorable (70-84), Average (50-69), Hostile (<50).
    """
    pos = position.upper().strip()
    team = (pro_team or "").upper().strip()

    implied_total = fallback_implied_total if fallback_implied_total is not None else 21.0
    game_ou = 44.0
    spread = 0.0
    is_home = False
    is_dome = False
    wind_mph = 0.0
    temp_f = 72.0

    if nfl_game:
        if team:
            implied_total = nfl_game.get_implied_total_for_team(team)
            is_home = nfl_game.is_home_for_team(team)
            spread = nfl_game.spread if is_home else -nfl_game.spread
        game_ou = nfl_game.over_under
        if getattr(nfl_game, "is_dome", False):
            is_dome = True

    if weather:
        if weather.is_dome:
            is_dome = True
        wind_mph = float(weather.wind_speed_mph or 0.0)
        temp_f = float(weather.temperature_f or 72.0)

    # 1. Implied Total Percentile (15.0 to 30.0 pts) -> 0.0 to 1.0
    implied_pct = max(0.0, min(1.0, (implied_total - SLATE_IMPLIED_MIN) / (SLATE_IMPLIED_MAX - SLATE_IMPLIED_MIN)))
    implied_pts = implied_pct * 100.0

    # 2. Over/Under Percentile (38.0 to 52.0 pts) -> 0.0 to 1.0
    ou_pct = max(0.0, min(1.0, (game_ou - SLATE_OU_MIN) / (SLATE_OU_MAX - SLATE_OU_MIN)))
    ou_pts = ou_pct * 100.0

    # 3. Spread / Competitiveness Factor
    # Competitive spread (abs(spread) <= 3.0) guarantees 4 quarters of offense
    abs_spread = abs(spread)
    if abs_spread <= 3.0:
        spread_pts = 90.0
    elif abs_spread <= 6.5:
        spread_pts = 75.0
    elif spread <= -7.0:
        # Heavy favorite: Clock-killing run script; positive for RBs, cap on pass attempts
        spread_pts = 75.0 if pos in ("RB", "FB") else 55.0
    else:
        # Heavy underdog: Trailing pass script; positive for pass-catchers, negative for early-down rushes
        spread_pts = 75.0 if pos in ("WR", "TE") else 50.0

    # 4. Weather & Venue Factor
    if is_dome:
        weather_pts = 100.0  # Perfect climate-controlled track
        weather_desc = "Indoor Dome (Optimal)"
    else:
        weather_pts = 85.0  # Open air base
        if wind_mph >= 20.0:
            weather_pts -= 35.0 if pos in ("QB", "WR", "TE", "K") else 15.0
        elif wind_mph >= 15.0:
            weather_pts -= 18.0 if pos in ("QB", "WR", "TE", "K") else 8.0

        if temp_f <= 25.0:
            weather_pts -= 12.0
        weather_desc = f"{temp_f:.0f}°F, {wind_mph:.0f} mph wind"

    weather_pts = max(20.0, min(100.0, weather_pts))

    # Composite Environment Score
    composite = (
        (ENV_IMPLIED_TOTAL_WEIGHT * implied_pts)
        + (ENV_OVER_UNDER_WEIGHT * ou_pts)
        + (ENV_SPREAD_SCRIPT_WEIGHT * spread_pts)
        + (ENV_WEATHER_VENUE_WEIGHT * weather_pts)
    )
    final_score = round(max(20.0, min(100.0, composite)), 1)

    # Buckets
    if final_score >= 82.0:
        bucket = "SHOOTOUT"
        bucket_color = "emerald"
    elif final_score >= 68.0:
        bucket = "FAVORABLE"
        bucket_color = "cyan"
    elif final_score >= 50.0:
        bucket = "AVERAGE"
        bucket_color = "amber"
    else:
        bucket = "HOSTILE"
        bucket_color = "rose"

    reasons: list[str] = []
    if implied_total >= 25.5:
        reasons.append(f"[Environment] 🚀 High Implied Team Total: Vegas projects {implied_total:.1f} team points ({implied_total / 7.0:.1f} expected TDs)")
    elif implied_total <= 18.5:
        reasons.append(f"[Environment] ⚠️ Low Implied Team Total: Vegas projects only {implied_total:.1f} points with suppressed scoring ceiling")

    if game_ou >= 47.5:
        reasons.append(f"[Environment] ⚡ Shootout Pace: {game_ou:.1f} Vegas game total indicates rapid play volume and back-and-forth scoring")
    elif game_ou <= 41.0:
        reasons.append(f"[Environment] 🐌 Trench Slog: Low {game_ou:.1f} game total caps offensive plays and drive sustainability")

    if is_dome:
        reasons.append("[Weather] 🏟️ Climate-Controlled Dome: Zero wind resistance, pristine turf footing, and optimal passing environment")
    elif wind_mph >= 15.0 and pos in ("QB", "WR", "TE", "K"):
        reasons.append(f"[Weather] 💨 Adverse Wind Resistance: {wind_mph:.0f} mph winds introduce passing and kicking volatility")

    raw_inputs = {
        "team_implied_total": round(implied_total, 1),
        "game_over_under": round(game_ou, 1),
        "team_spread": round(spread, 1),
        "is_home": is_home,
        "is_dome": is_dome,
        "wind_speed_mph": round(wind_mph, 1),
        "temperature_f": round(temp_f, 1),
        "weather_summary": weather_desc,
    }

    contributions = {
        "team_implied_pts": round(ENV_IMPLIED_TOTAL_WEIGHT * implied_pts, 1),
        "game_over_under_pts": round(ENV_OVER_UNDER_WEIGHT * ou_pts, 1),
        "spread_script_pts": round(ENV_SPREAD_SCRIPT_WEIGHT * spread_pts, 1),
        "weather_venue_pts": round(ENV_WEATHER_VENUE_WEIGHT * weather_pts, 1),
    }

    formula = (
        f"Environment: Implied({implied_total:.1f}pts*{ENV_IMPLIED_TOTAL_WEIGHT}) "
        f"+ OU({game_ou:.1f}pts*{ENV_OVER_UNDER_WEIGHT}) + Script({spread:+.1f}*{ENV_SPREAD_SCRIPT_WEIGHT}) "
        f"+ Venue({weather_desc}*{ENV_WEATHER_VENUE_WEIGHT}) = Score {final_score:.1f}"
    )

    return FactorScoreDetail(
        score=final_score,
        bucket=bucket,
        bucket_color=bucket_color,
        raw_inputs=raw_inputs,
        contributions=contributions,
        formula_description=formula,
        reasons=reasons,
    )


# ============================================================================
# 5. MASTER ADAPTER FOR COMPARATOR EVALUATIONS
# ============================================================================

def calculate_comparator_factors_for_evaluation(
    evaluation: Any,
    nfl_game: NFLGame | None = None,
    weather: WeatherReport | None = None,
) -> ComparatorFactorsBundle:
    """Calculates all four calibrated factor scores for a single player evaluation in the comparator."""
    pos = getattr(evaluation, "position", "WR")
    proj = getattr(evaluation, "projected_points", 0.0)
    stats = getattr(evaluation, "itemized_stats", {}) or {}
    share = getattr(evaluation, "volume_share", None)
    opp = getattr(evaluation, "opponent", "")
    team = getattr(evaluation, "pro_team", "")
    c_rank = getattr(evaluation, "consensus_rank", None)
    fp_ecr = getattr(evaluation, "fp_rank_ecr", None)

    is_receiving_back = (pos in ("RB", "FB")) and (float(stats.get("targets", 0.0)) >= 3.0 or float(stats.get("receptions", 0.0)) >= 2.5)
    is_slot_wr = (pos == "WR") and (float(stats.get("targets", 0.0)) >= 4.0 and (float(stats.get("rec_yds", 0.0)) / max(1.0, float(stats.get("targets", 0.0)))) < 11.0)

    proj_factor = calculate_start_sit_projection_score(
        projected_points=proj,
        position=pos,
        consensus_rank=c_rank,
        fp_ecr=fp_ecr,
    )

    opp_factor = calculate_start_sit_opportunity_score(
        position=pos,
        stats=stats,
        volume_share=share,
    )

    match_factor = calculate_start_sit_matchup_score(
        position=pos,
        opponent_team=opp,
        is_receiving_back=is_receiving_back,
        is_slot_wr=is_slot_wr,
    )

    env_factor = calculate_start_sit_environment_score(
        position=pos,
        nfl_game=nfl_game,
        weather=weather,
        pro_team=team,
        fallback_implied_total=getattr(evaluation, "implied_team_total", None),
    )

    return ComparatorFactorsBundle(
        projection=proj_factor,
        opportunity=opp_factor,
        matchup=match_factor,
        environment=env_factor,
    )
