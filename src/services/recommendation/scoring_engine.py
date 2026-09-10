"""Explainable Start/Sit Scoring Model with configurable heuristics and factual provenance."""

import logging
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.betting.props_client import vegas_props_client
from src.adapters.borischen.client import boris_chen_client
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.injuries_client import PlayerInjuryReport
from src.adapters.nfl.schedule_client import NFLGame
from src.adapters.weather.client import WeatherReport, weather_client
from src.db.models import PlayerModel
from src.services.matchup.vegas_gamescript import vegas_gamescript_analyzer
from src.services.matchup.wrcb_matrix import wrcb_analyzer
from src.services.matchup.dvp_service import dvp_service
from src.services.recommendation.projection_engine import quant_projection_engine

logger = logging.getLogger(__name__)


class ScoringWeights(BaseModel):
    """Configurable weights for the Start/Sit composite formula (must sum to 1.0)."""
    projection_weight: float = 0.35
    opportunity_weight: float = 0.20
    matchup_weight: float = 0.20
    environment_weight: float = 0.10
    health_weight: float = 0.10
    weather_weight: float = 0.05

    def normalize(self) -> "ScoringWeights":
        total = (
            self.projection_weight
            + self.opportunity_weight
            + self.matchup_weight
            + self.environment_weight
            + self.health_weight
            + self.weather_weight
        )
        if total <= 0:
            return ScoringWeights()
        return ScoringWeights(
            projection_weight=round(self.projection_weight / total, 3),
            opportunity_weight=round(self.opportunity_weight / total, 3),
            matchup_weight=round(self.matchup_weight / total, 3),
            environment_weight=round(self.environment_weight / total, 3),
            health_weight=round(self.health_weight / total, 3),
            weather_weight=round(self.weather_weight / total, 3),
        )


class ComponentScores(BaseModel):
    projection_score: float = 70.0
    opportunity_score: float = 70.0
    matchup_score: float = 70.0
    environment_score: float = 70.0
    health_score: float = 100.0
    weather_score: float = 100.0


class StartSitEvaluation(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    projected_points: float
    actual_points: float = 0.0
    lineup_locked: bool = False
    is_started: bool = False
    is_final: bool = False
    game_status: str = "UPCOMING"  # UPCOMING, LIVE, FINAL
    effective_points: float = 0.0
    start_score: float  # 0 to 100
    confidence: str     # HIGH, MEDIUM, LOW
    recommendation: str # STRONG START, START, TOSS-UP, BENCH, SIT
    matchup_grade: str  # FAVORABLE, NEUTRAL, TOUGH
    opponent: str
    is_home: bool
    implied_team_total: float
    injury_status: str
    weather_summary: str | None = None
    reasons_positive: list[str] = Field(default_factory=list)
    reasons_negative: list[str] = Field(default_factory=list)
    components: ComponentScores = Field(default_factory=ComponentScores)
    itemized_stats: dict[str, float] = Field(default_factory=dict)
    upcoming_schedule: list[dict[str, Any]] = Field(default_factory=list)
    consensus_rank: float | None = None
    ceiling_score: float = 0.0      # 90th percentile boom upside
    floor_score: float = 0.0        # 20th percentile bust resistance
    contingency_score: float = 0.0  # Contingent upside if starter is out
    mode: str = "BALANCED"          # BALANCED, CEILING, FLOOR
    game_date: str | None = None    # Kickoff timestamp / date string for flex timing
    live_vorp: float | None = None  # Dynamic Value Over Replacement Player vs wire
    fp_rank_ecr: int | None = None
    fp_pos_rank: str | None = None
    fp_tier: int | None = None
    fp_rank_ave: float | None = None
    fp_rank_std: float | None = None
    fp_start_sit_grade: str | None = None
    fp_r2p_pts: float | None = None
    fp_injury_note: str | None = None
    matchup_resilience: str = "MODERATE_ELASTICITY"  # MATCHUP_RESILIENT_STUD, MODERATE_ELASTICITY, MATCHUP_SENSITIVE_STREAMER
    playoff_sos_score: float = 70.0                  # 0 to 100 rating for fantasy playoff weeks (Weeks 15-17)
    playoff_sos_grade: str = "NEUTRAL"               # ELITE, FAVORABLE, NEUTRAL, TOUGH, BRUTAL
    opp_dvp_rank: int | None = None                  # 1-32 FantasyPros Consensus rank vs player position (1=toughest, 32=softest)
    opp_def_rank: int | None = None                  # 1-32 FantasyPros Consensus overall defensive rank
    opp_off_rank: int | None = None                  # 1-32 FantasyPros Consensus overall offensive rank (for D/ST vs opponent offense)
    opp_dvp_grade: str | None = None                 # FAVORABLE, NEUTRAL, TOUGH
    matchup_stars: int | None = None                 # 1-5 FantasyPros Matchup Rating Stars (1=worst, 5=best)
    dvp_source: str | None = "FantasyPros Consensus"
    volume_share: float | None = None                # Target share % (WR/TE/RB) or Carry share % (RB)
    team_projected_plays: float | None = None        # Expected team plays based on Vegas pace & total
    team_pass_att: float | None = None               # Projected team pass attempts
    team_rush_att: float | None = None               # Projected team rush attempts
    efficiency_multiplier: float | None = None       # Net % efficiency bump from DvP & weather
    proj_model: float = 0.0                          # Quant Model projection
    proj_fantasypros: float = 0.0                    # FantasyPros weekly PPR projection
    proj_sleeper: float = 0.0                        # Sleeper / RotoWire weekly PPR projection
    proj_espn: float = 0.0                           # ESPN weekly PPR projection
    proj_consensus: float = 0.0                      # Outlier-protected consensus
    projected_points_model: float = 0.0              # Direct alias for Quant Model projection
    projected_points_fp: float = 0.0                 # Direct alias for FantasyPros PPR projection
    projected_points_sleeper: float = 0.0            # Direct alias for Sleeper / RotoWire PPR projection
    projected_points_espn: float = 0.0               # Direct alias for ESPN PPR projection
    projected_points_consensus: float = 0.0          # Direct alias for Consensus projection
    active_projection_source: str = "MODEL"          # Active source (MODEL, FANTASYPROS, SLEEPER, ESPN, CONSENSUS)
    consensus_spread: float = 0.0                    # Difference between max and min projection
    consensus_agreement: str = "HIGH_AGREEMENT"      # HIGH_AGREEMENT, MODERATE, SHARP_DIVERGENCE
    fp_itemized_stats: dict[str, float] = Field(default_factory=dict)  # Itemized stats from FantasyPros
    sleeper_itemized_stats: dict[str, float] = Field(default_factory=dict)  # Itemized stats from Sleeper
    floor_points: float | None = None                # Projected fantasy points floor (20th percentile)
    model_provenance: dict[str, Any] = Field(default_factory=dict)  # Transparent breakdown of sources
    comparator_factors: dict[str, Any] | None = None  # Enriched factor transparency for Start/Sit Comparator
    wrcb_advantage_score: float | None = None        # Advantage delta % vs primary CB (-30 to +30)
    wrcb_advantage_rating: str | None = None       # SHADOW_LOCKDOWN, TOUGH_PERIMETER, NEUTRAL, FAVORABLE, SLOT_MISMATCH, MAJOR_ADVANTAGE
    wrcb_primary_cb: str | None = None             # Name of projected primary CB
    wrcb_is_shadow: bool = False                   # True if shadowed by CB1
    game_script: str | None = None                 # SHOOTOUT, FAVORITE_RUN_FUNNEL, UNDERDOG_PASS_FUNNEL, DEFENSIVE_SLUGFEST, BALANCED
    game_script_label: str | None = None           # Human readable game environment label
    props_receptions_ou: float | None = None       # Sportsbook consensus receptions O/U
    props_rec_yds_ou: float | None = None          # Sportsbook receiving yards O/U
    props_rush_yds_ou: float | None = None         # Sportsbook rushing yards O/U
    props_rush_att_ou: float | None = None         # Sportsbook rushing attempts O/U
    props_pass_yds_ou: float | None = None         # Sportsbook passing yards O/U
    props_pass_tds_ou: float | None = None         # Sportsbook passing TDs O/U
    props_anytime_td_odds: int | None = None       # Sportsbook American odds (e.g. -115)
    props_anytime_td_prob: float | None = None     # Market-implied touchdown probability
    props_implied_ppr_pts: float | None = None     # Fantasy points implied by betting lines
    props_market_sentiment: str | None = None      # HEAVY_OVER, SLIGHT_OVER, NEUTRAL, SLIGHT_UNDER
    props_sharp_notes: list[str] = Field(default_factory=list)
    props_vegas_grade: str | None = None           # VERY_ELITE, ELITE, GOOD, AVERAGE, FADE, VERY_BAD
    props_vegas_grade_label: str | None = None     # 🔥 VERY ELITE, ✨ ELITE, 👍 GOOD, etc.
    props_vegas_grade_color: str | None = None     # gold, emerald, cyan, zinc, amber, rose
    props_vegas_takeaway: str | None = None        # Actionable 1-line summary for fantasy PPR
    boris_chen_tier: int | None = None             # Boris Chen GMM tier (1 through 8)
    boris_chen_tier_label: str | None = None       # "Tier 1", "Tier 2", etc.
    boris_chen_is_dropoff: bool = False            # True if sitting right before significant tier gap
    dvp_fpa: dict[str, Any] | None = None          # DraftEdge Defense-vs-Position Fantasy Points Allowed details



# Positional average baseline fantasy points by league size
LEAGUE_SIZE_BASELINES: dict[int, dict[str, float]] = {
    8: {
        "QB": 20.5,
        "RB": 15.5,
        "WR": 16.2,
        "TE": 11.5,
        "K": 8.5,
        "D/ST": 8.0,
        "UNK": 12.0,
    },
    10: {
        "QB": 19.0,
        "RB": 14.5,
        "WR": 14.5,
        "TE": 10.2,
        "K": 8.2,
        "D/ST": 7.8,
        "UNK": 11.0,
    },
    12: {
        "QB": 17.5,
        "RB": 13.5,
        "WR": 13.5,
        "TE": 9.5,
        "K": 8.0,
        "D/ST": 7.5,
        "UNK": 10.0,
    },
}

POSITION_BASELINES: dict[str, float] = LEAGUE_SIZE_BASELINES[8]


# 2026 NFL Fantasy Playoff Opponents (Weeks 15, 16, 17) for all 32 teams
PLAYOFF_WEEKS_2026: dict[str, list[str]] = {
    "ARI": ["CAR", "LAR", "SEA"],
    "ATL": ["TB", "CAR", "NO"],
    "BAL": ["CLE", "PIT", "CIN"],
    "BUF": ["NE", "MIA", "NYJ"],
    "CAR": ["ARI", "ATL", "TB"],
    "CHI": ["MIN", "GB", "DET"],
    "CIN": ["PIT", "CLE", "BAL"],
    "CLE": ["BAL", "CIN", "PIT"],
    "DAL": ["NYG", "PHI", "WSH"],
    "DEN": ["LV", "LAC", "KC"],
    "DET": ["GB", "CHI", "MIN"],
    "GB": ["DET", "MIN", "CHI"],
    "HOU": ["TEN", "JAX", "IND"],
    "IND": ["JAX", "TEN", "HOU"],
    "JAX": ["IND", "HOU", "TEN"],
    "KC": ["LAC", "LV", "DEN"],
    "LAC": ["KC", "DEN", "LV"],
    "LAR": ["SF", "ARI", "SEA"],
    "LV": ["DEN", "KC", "LAC"],
    "MIA": ["NYJ", "BUF", "NE"],
    "MIN": ["CHI", "GB", "DET"],
    "NE": ["BUF", "NYJ", "MIA"],
    "NO": ["TB", "ATL", "CAR"],
    "NYG": ["DAL", "WSH", "PHI"],
    "NYJ": ["MIA", "NE", "BUF"],
    "PHI": ["WSH", "DAL", "NYG"],
    "PIT": ["CIN", "BAL", "CLE"],
    "SEA": ["LAR", "SF", "ARI"],
    "SF": ["SEA", "LAR", "ARI"],
    "TB": ["ATL", "NO", "CAR"],
    "TEN": ["HOU", "IND", "JAX"],
    "WSH": ["PHI", "NYG", "DAL"],
}


def calculate_playoff_sos(pro_team: str, position: str) -> tuple[float, str]:
    """Calculates composite fantasy playoff Strength of Schedule for Weeks 15-17.
    
    Returns:
        tuple[float, str]: (score 0-100, grade: ELITE | FAVORABLE | NEUTRAL | TOUGH | BRUTAL)
    """
    team = pro_team.upper().strip()
    opps = PLAYOFF_WEEKS_2026.get(team, ["VARIES", "VARIES", "VARIES"])
    scores: list[float] = []
    for opp in opps:
        s, _ = dvp_client.calculate_matchup_score(opp, position)
        scores.append(s)
    avg_score = round(sum(scores) / max(len(scores), 1), 1)
    if avg_score >= 76.0:
        grade = "ELITE"
    elif avg_score >= 71.0:
        grade = "FAVORABLE"
    elif avg_score <= 58.0:
        grade = "TOUGH"
    elif avg_score <= 52.0:
        grade = "BRUTAL"
    else:
        grade = "NEUTRAL"
    return avg_score, grade


def sort_factor_reasons(reasons: list[str]) -> list[str]:
    """Sort pro and con reasons prioritizing primary fantasy football strategic drivers:
    1. 8-Man PPR Leverage & Volume
    2. Red Zone
    3. Game Script & Funnels
    4. Matchup & Coverage
    5. Projection & Efficiency
    6. Floor/Ceiling
    7. 8-Man PPR Trap & Health
    8. Risk
    9. Weather & Consensus
    """
    priority_map = {
        "[Tactical]": 1,
        "[8-Man PPR Leverage]": 2,
        "[Volume]": 3,
        "[Red Zone]": 4,
        "[Script]": 5,
        "[Game Script]": 5,
        "[Vegas Props]": 5,
        "[Matchup]": 6,
        "[Defense]": 6,
        "[Boris Chen]": 7,
        "[Projection]": 7,
        "[Efficiency]": 8,
        "[Floor/Ceiling]": 9,
        "[Environment]": 10,
        "[Contingency]": 11,
        "[8-Man PPR Trap]": 12,
        "[Schedule]": 13,
        "[Health]": 14,
        "[Risk]": 15,
        "[Weather]": 16,
        "[Consensus]": 17,
    }

    def get_priority(text: str) -> int:
        for prefix, prio in priority_map.items():
            if text.startswith(prefix):
                return prio
        return 99

    return sorted(reasons, key=get_priority)


class StartSitScoringEngine:
    """Calculates deterministic Start/Sit composite scores with transparent factor provenance."""

    def __init__(self, weights: ScoringWeights | None = None, league_size: int = 8):
        self.weights = weights.normalize() if weights else ScoringWeights()
        self.league_size = league_size

    def evaluate_player(
        self,
        player: PlayerModel,
        nfl_game: NFLGame | None = None,
        injury_report: PlayerInjuryReport | None = None,
        weather: WeatherReport | None = None,
        mode: str = "BALANCED",
        league_size: int | None = None,
        projection_source: str = "MODEL",
        actual_points: float | None = None,
        lineup_locked: bool = False,
    ) -> StartSitEvaluation:
        eff_size = league_size or self.league_size
        baselines = LEAGUE_SIZE_BASELINES.get(eff_size, LEAGUE_SIZE_BASELINES[8])

        pos = player.position.upper()
        proj = player.projected_points
        stats = player.projected_stats or {}

        # 0. Institutional Quant Projection Engine: Macro-Micro Reconciled Ensemble
        q_proj = quant_projection_engine.calculate_player_projection(
            player, nfl_game=nfl_game, weather=weather, projection_source=projection_source
        )
        if q_proj.projected_points > 0.0:
            proj = q_proj.projected_points
            stats = q_proj.itemized_stats.model_dump()
        elif proj <= 0.0 and stats.get("calculated_ppr", 0.0) > 0.0:
            proj = float(stats["calculated_ppr"])

        pos_baseline = baselines.get(pos, 12.0)
        pos_reasons: list[str] = []
        neg_reasons: list[str] = []
        dvp_info: dict[str, Any] | None = None

        # Game Script & Environment Context
        opponent = "BYE"
        is_home = False
        implied_total = 21.0
        opp_implied = 21.0
        team_spread = 0.0
        game_over_under = 44.0

        if nfl_game:
            opponent = nfl_game.get_opponent_for_team(player.pro_team) or "BYE"
            is_home = nfl_game.is_home_for_team(player.pro_team)
            implied_total = nfl_game.get_implied_total_for_team(player.pro_team)
            team_spread = nfl_game.spread if is_home else -nfl_game.spread
            game_over_under = nfl_game.over_under
            if opponent != "BYE":
                opp_implied = nfl_game.get_implied_total_for_team(opponent)

        # 1. Mathematical Projection Component (0 to 100)
        proj_ratio = proj / max(pos_baseline, 1.0)
        proj_score = min(100.0, max(10.0, proj_ratio * 70.0))

        # FantasyPros Expert Intelligence Integration
        fp_ecr = getattr(player, "fp_rank_ecr", None)
        fp_pos = getattr(player, "fp_pos_rank", None)
        fp_tier = getattr(player, "fp_tier", None)
        fp_ave = getattr(player, "fp_rank_ave", None)
        fp_std = getattr(player, "fp_rank_std", None)
        fp_grade = getattr(player, "fp_start_sit_grade", None)
        fp_r2p = getattr(player, "fp_r2p_pts", None)
        fp_inj_note = getattr(player, "fp_injury_note", None)
        c_rank = getattr(player, "consensus_rank", 999.0) or 999.0

        if fp_ecr is not None:
            if fp_ecr <= 3:
                proj_score = min(100.0, proj_score + 5.0)
                pos_reasons.append(
                    f"[Consensus] ⭐ FantasyPros ECR #{fp_ecr} ({fp_pos or pos}) Consensus Lock • Grade {fp_grade or 'A+'}"
                )
            elif fp_ecr <= 8:
                proj_score = min(100.0, proj_score + 3.0)
                pos_reasons.append(
                    f"[Consensus] ⭐ FantasyPros ECR #{fp_ecr} ({fp_pos or pos}) Undisputed 8-Team Starter (Grade: {fp_grade or 'A'})"
                )
            elif fp_ecr <= 12:
                pos_reasons.append(f"[Consensus] ⭐ FantasyPros Top-12 Weekly Rank ({fp_pos or pos}) • Avg: #{fp_ave:.1f}")

            if fp_r2p is not None and fp_r2p >= pos_baseline * 1.15:
                pos_reasons.append(f"[Consensus] ⭐ FantasyPros expert projected output: {fp_r2p:.1f} pts")
        else:
            if c_rank <= 5.0:
                proj_score = min(100.0, proj_score + 4.0)
                pos_reasons.append(f"[Consensus] ⭐ Consensus Top-{int(c_rank)} weekly expert rank across national analysts")
            elif c_rank <= 12.0:
                pos_reasons.append(f"[Consensus] ⭐ Consensus Top-12 weekly rank (#{c_rank:.1f} PPR)")

        # FantasyPros Tier 1 Positional Anchor
        if fp_tier == 1:
            pos_reasons.append("[Consensus] 🏆 Tier 1 Positional Anchor: Consensus Tier 1 grade across national fantasy experts")
        elif fp_tier is not None and fp_tier >= 5 and eff_size <= 8 and (fp_ecr or 999) > 16:
            neg_reasons.append(f"[Consensus] ⚠️ Lower Starter Tier: Ranked in Tier {fp_tier} (fringy starting grade in shallow 8-man formats)")

        # FantasyPros Start/Sit Universal Grade Trigger
        if fp_grade in ("A+", "A") and not any("Consensus Lock" in r or "Undisputed" in r for r in pos_reasons):
            pos_reasons.append(f"[Consensus] 🌟 Universal Start Grade: Graded '{fp_grade}' by FantasyPros expert consensus")
        elif fp_grade in ("D", "D-", "F"):
            neg_reasons.append(f"[Risk] ⚠️ Unfavorable Start/Sit Grade: Rated '{fp_grade}' by FantasyPros national analyst panel")

        # Multi-Source Bayesian Ensembling Agreement / Disagreement
        if q_proj and q_proj.model_points > 0 and q_proj.fp_points > 0 and q_proj.espn_points > 0:
            if q_proj.consensus_spread <= 1.4:
                pos_reasons.append(f"[Consensus] 🎯 Multi-Source Convergence: Model, FantasyPros, and ESPN align within ±{q_proj.consensus_spread:.1f} pts (high projection fidelity)")
            elif q_proj.consensus_spread >= 4.2:
                neg_reasons.append(f"[Risk] ⚠️ Multi-Source Model Divergence: {q_proj.consensus_spread:.1f}-pt spread across projection sources indicates wide outcome range")

        if fp_inj_note:
            neg_reasons.append(f"[Health] 🏥 Beat reporter injury note: {fp_inj_note}")

        if proj >= pos_baseline * 1.25:
            pos_reasons.append(f"[Projection] 📈 High projected PPR output ({proj:.1f} pts vs {pos_baseline:.1f} positional baseline)")
        elif proj <= pos_baseline * 0.75:
            neg_reasons.append(f"[Projection] 📉 Below-average projection ({proj:.1f} pts)")

        # 2. Mathematical Opportunity / Volume Component
        rush_att = float(stats.get("rush_att", 0.0))
        rush_yds = float(stats.get("rush_yds", 0.0))
        rush_td = float(stats.get("rush_td", 0.0))
        targets = float(stats.get("targets", 0.0))
        receptions = float(stats.get("receptions", 0.0))
        rec_yds = float(stats.get("rec_yds", 0.0))
        rec_td = float(stats.get("rec_td", 0.0))
        pass_att = float(stats.get("pass_att", 0.0))
        total_tds = rush_td + rec_td

        ceiling_boost = 0.0
        floor_penalty = 0.0
        vol_share = q_proj.volume_share if q_proj else None

        if pos in ("RB", "FB"):
            # High-Value Touches (HVT): Targets (2.85x) + Goal-line TD Equity (5.0x)
            ppr_weighted_touches = (rush_att * 1.0) + (targets * 2.85) + (total_tds * 5.0)
            opp_score = min(100.0, max(20.0, 24.0 + (ppr_weighted_touches * 2.0)))

            # Game Script: Clock-killing favorite vs Trailing underdog
            if team_spread <= -5.5:
                opp_score = min(100.0, opp_score + 4.0)
                ceiling_boost += 3.0
                pos_reasons.append(f"[Script] 🏈 Favorable clock-killing run script: team favored by {abs(team_spread):.1f} pts")
            elif team_spread >= 4.5:
                if targets >= 3.5 or receptions >= 2.5:
                    pos_reasons.append(f"[Script] 🏈 Trailing checkdown script: {abs(team_spread):.1f}-pt underdog elevates pass-catching RB targets ({targets:.1f} tgts)")
                    ceiling_boost += 3.0
                elif targets < 2.0:
                    neg_reasons.append(f"[Risk] ⚠️ Negative script risk: {abs(team_spread):.1f}-pt underdog threatens early-down rush volume (only {targets:.1f} tgts)")
                    floor_penalty += 6.0

            # Workhorse volume & touch share
            if (rush_att + targets) >= 20.0:
                pos_reasons.append(f"[Volume] 🚜 Elite 20+ Touch Workhorse: Projected for {rush_att:.1f} carries + {targets:.1f} targets ({rush_att + targets:.1f} total touches) commanding primary backfield monopoly")
            elif (rush_att + targets) >= 17.0:
                pos_reasons.append(f"[Volume] 🎯 Workhorse volume: projected for {rush_att:.1f} carries + {targets:.1f} targets ({rush_att + targets:.1f} total touches)")
            elif (rush_att + targets) >= 12.0:
                pos_reasons.append(f"[Volume] 🎯 Steady workload: {rush_att:.1f} carries and {targets:.1f} targets projected")
            else:
                neg_reasons.append(f"[Volume] ⚠️ Limited touch volume: projected for {rush_att + targets:.1f} total touches")
                floor_penalty += 8.0

            # Carry share % (Bellcow vs Committee)
            if vol_share and vol_share >= 65.0:
                pos_reasons.append(f"[Volume] 🏈 Bellcow backfield share: commands {vol_share:.1f}% of projected team rushing volume")
            elif vol_share and vol_share <= 42.0 and rush_att < 11.0:
                neg_reasons.append(f"[Volume] ⚠️ Committee timeshare: capped at {vol_share:.1f}% carry share in split backfield")
                floor_penalty += 4.0

            if targets >= 4.0:
                pos_reasons.append(f"[8-Man PPR Leverage] 🎯 Elite pass-catching role: {targets:.1f} targets ({receptions:.1f} rec) provides bankable PPR floor")
                pos_reasons.append(f"[Volume] 🎯 High-value PPR receiving role: {targets:.1f} targets ({receptions:.1f} rec projected)")
                ceiling_boost += 4.0
            elif targets <= 1.0 and rush_att >= 8.0:
                neg_reasons.append(f"[8-Man PPR Trap] ⚠️ Rush-only role ({targets:.1f} tgts): Lack of receiving involvement caps full PPR utility")
                floor_penalty += 3.0

            # High-Value Touch (HVT) Target-to-Touch Ratio
            total_touches = rush_att + targets
            if total_touches >= 10.0:
                target_touch_ratio = (targets / total_touches) * 100.0
                if target_touch_ratio >= 25.0:
                    pos_reasons.append(
                        f"[8-Man PPR Leverage] 🎯 Elite Target-to-Touch Ratio: Targets account for {target_touch_ratio:.0f}% of total touches ({targets:.1f} tgts / {total_touches:.1f} touches) driving premium high-value PPR scoring"
                    )
                    ceiling_boost += 2.0
                elif target_touch_ratio <= 10.0 and targets <= 1.5:
                    neg_reasons.append(
                        f"[8-Man PPR Trap] ⚠️ Low Target-to-Touch Ratio: Only {target_touch_ratio:.0f}% of touches are targets ({targets:.1f} tgts / {rush_att:.1f} carries); heavily game-script dependent"
                    )
                    floor_penalty += 2.0

            # Ground YPC Burst vs Slog
            if rush_att >= 10.0:
                ypc = rush_yds / max(1.0, rush_att)
                if ypc >= 4.7:
                    pos_reasons.append(f"[Efficiency] ⚡ Explosive Ground Efficiency: Projected for {ypc:.1f} YPC indicating high burst & chunk-gain capability")
                    ceiling_boost += 3.0
                elif ypc < 3.6:
                    neg_reasons.append(f"[Efficiency] ⚠️ Low Ground Efficiency: Sub-3.6 projected YPC ({ypc:.1f} YPC) limits early-down rushing floor")
                    floor_penalty += 3.0

            # Goal line & red zone TD equity
            if total_tds >= 0.70:
                pos_reasons.append(f"[Red Zone] 🚨 High-value goal line role: {total_tds:.2f} projected TDs with elite red zone equity")
                ceiling_boost += 5.0
            elif total_tds <= 0.20 and rush_att >= 8.0:
                neg_reasons.append(f"[Red Zone] ⚠️ Low TD Equity: only {total_tds:.2f} projected TDs; team relies on pass-game punch-ins")
                floor_penalty += 3.0

            if targets >= 3.5 and total_tds >= 0.50:
                pos_reasons.append(f"[Red Zone] 🎯 High-Value Touch Hub: {targets:.1f} targets paired with {total_tds:.2f} projected TDs generates multi-touchdown ceiling")
                ceiling_boost += 2.0

        elif pos == "WR":
            ypt = rec_yds / max(targets, 1.0) if targets > 0 else 0.0
            weighted_targets = (targets * 9.0) + (rush_att * 3.0) + (rec_td * 8.0)
            opp_score = min(100.0, max(20.0, 20.0 + (weighted_targets * 1.12)))

            # Game Script: Underdog trailing pass volume vs Blowout pull risk
            if team_spread >= 5.0:
                opp_score = min(100.0, opp_score + 3.5)
                ceiling_boost += 4.0
                pos_reasons.append(f"[Script] 🏈 Trailing pass script leverage: {abs(team_spread):.1f}-pt underdog elevates pass volume")
            elif team_spread <= -7.5:
                neg_reasons.append(f"[Risk] ⚠️ Blowout script risk: heavy {abs(team_spread):.1f}-pt favorite risks reduced second-half passing or early pulled starters")
                floor_penalty += 4.0

            # Target share % (Alpha vs Rotational)
            if vol_share and vol_share >= 25.0:
                pos_reasons.append(f"[Volume] 🎯 Alpha Target Share: commands {vol_share:.1f}% team target share ({targets:.1f} targets)")
                pos_reasons.append(f"[8-Man PPR Leverage] 🎯 Dominant target share ({vol_share:.1f}%, {targets:.1f} tgts): Elite weekly full PPR engine")
                ceiling_boost += 4.0
            elif vol_share and vol_share <= 14.0 and targets < 5.0:
                neg_reasons.append(f"[Volume] ⚠️ Rotational target risk: low {vol_share:.1f}% target share commands limited first-read looks")
                floor_penalty += 5.0

            if targets >= 8.5:
                pos_reasons.append(f"[Volume] 🎯 Alpha target share: projected for {targets:.1f} targets ({receptions:.1f} rec)")
                ceiling_boost += 5.0
            elif targets >= 6.0:
                pos_reasons.append(f"[Volume] 🎯 Solid WR target volume: projected for {targets:.1f} targets")
            else:
                neg_reasons.append(f"[Volume] ⚠️ Low target volume: only {targets:.1f} projected targets")
                neg_reasons.append(f"[8-Man PPR Trap] ⚠️ Low target volume: Only {targets:.1f} targets projected; unviable in full PPR 8-man lineups")
                floor_penalty += 8.0

            if targets >= 5.0:
                catch_rate = (receptions / targets) * 100.0
                if catch_rate >= 72.0:
                    pos_reasons.append(f"[Efficiency] 🎯 High-Percentage Target Conversion: {catch_rate:.0f}% catch rate ({receptions:.1f} rec on {targets:.1f} tgts) provides bankable PPR floor")
                elif catch_rate < 52.0:
                    neg_reasons.append(f"[Efficiency] ⚠️ Low Target Conversion Rate: {catch_rate:.0f}% projected catch rate indicates volatile downfield target depth")

            if targets >= 7.0 and ypt < 9.5:
                pos_reasons.append(f"[Volume] 🎯 Short-Area Target Funnel: High target volume underneath ({targets:.1f} tgts, {receptions:.1f} rec) acts as steady full-PPR chain mover")
            elif ypt >= 13.5 and targets >= 4.0:
                pos_reasons.append(f"[Efficiency] 🚀 High Air-Yard Profile: {ypt:.1f} yards per target indicates high-aDOT vertical shot design")

            if ypt >= 11.5 and targets >= 4.5:
                pos_reasons.append(f"[Efficiency] ⚡ Explosive downfield target profile: {ypt:.1f} YPT indicates high air-yard ceiling")
                ceiling_boost += 4.0

            if rec_td >= 0.60:
                pos_reasons.append(f"[Red Zone] 🚨 Red zone alpha: {rec_td:.2f} projected TDs")
                ceiling_boost += 3.0
            elif rec_td <= 0.18 and targets >= 5.5:
                neg_reasons.append(f"[Red Zone] ⚠️ Capped TD Upside: only {rec_td:.2f} projected TDs despite target volume; limited end-zone usage")
                floor_penalty += 3.0

        elif pos == "TE":
            weighted_targets = (targets * 11.5) + (rec_td * 10.0)
            opp_score = min(100.0, max(20.0, 25.0 + (weighted_targets * 1.05)))
            if team_spread >= 5.0:
                opp_score = min(100.0, opp_score + 2.5)
                ceiling_boost += 3.0

            if vol_share and vol_share >= 20.0:
                pos_reasons.append(f"[Volume] 🎯 Focal point TE: commands {vol_share:.1f}% target share as top-2 option")
                ceiling_boost += 4.0

            if targets >= 6.0:
                pos_reasons.append(f"[Volume] 🎯 Elite TE target share: projected for {targets:.1f} targets ({receptions:.1f} rec)")
                ceiling_boost += 5.0
            elif targets >= 4.0:
                pos_reasons.append(f"[Volume] 🎯 Solid TE involvement: projected for {targets:.1f} targets")
            else:
                neg_reasons.append(f"[Volume] ⚠️ Low TE involvement: only {targets:.1f} projected targets")
                floor_penalty += 6.0

            if targets >= 7.0:
                pos_reasons.append(f"[8-Man PPR Leverage] 🎯 Positional Disparity Cheat Code: {targets:.1f} TE targets delivers rare high-end positional scoring punch")
            if targets >= 4.5 and (receptions / max(1.0, targets)) >= 0.72:
                pos_reasons.append(f"[Efficiency] 🎯 Intermediate Security Blanket: High {receptions / targets * 100:.0f}% catch conversion yields consistent PPR floor")

            if rec_td >= 0.50:
                pos_reasons.append(f"[Red Zone] 🚨 Red zone safety blanket: {rec_td:.2f} projected TDs")
                ceiling_boost += 3.0
            elif rec_td <= 0.15 and targets >= 4.0:
                neg_reasons.append(f"[Red Zone] ⚠️ Low red-zone conversion: only {rec_td:.2f} projected TDs")
                floor_penalty += 2.0

        elif pos == "QB":
            # Konami Code QB rushing multiplier: 1 QB rush is worth 3.5 pass attempts in PPR/4pt pass TD
            qb_volume = pass_att + (rush_att * 3.5)
            opp_score = min(100.0, max(30.0, (qb_volume / 45.0) * 82.0))

            if team_spread <= -7.5:
                neg_reasons.append(f"[Risk] ⚠️ Blowout pass cap: heavy {abs(team_spread):.1f}-pt favorite risks conservative second-half clock burning")
                floor_penalty += 4.0

            if rush_att >= 4.0 or rush_yds >= 25.0:
                rush_pts = (rush_yds * 0.1) + (rush_td * 6.0)
                pos_reasons.append(
                    f"[Volume] ⚡ Elite Konami Code rushing upside: {rush_att:.1f} carries / {rush_yds:.0f} rush yds (+{rush_pts:.1f} rushing pts)"
                )
                opp_score = min(100.0, opp_score + 4.5)
                ceiling_boost += 8.0

            if rush_td >= 0.35 or rush_att >= 6.0:
                pos_reasons.append(f"[Red Zone] 🚨 Designed Rushing & Sneak Equity: {rush_att:.1f} carries / {rush_td:.2f} projected rush TDs gives elite goal-line punch-in ceiling")
                ceiling_boost += 4.0

            if team_spread >= 6.0 and pass_att >= 33.0:
                pos_reasons.append(f"[Script] 🚀 Trailing Aerial Volume: {team_spread:.1f}-pt underdog script elevates late-game hurry-up pass attempts")

            pass_td = float(stats.get("pass_td", 0.0))
            if pass_td >= 1.85:
                pos_reasons.append(f"[Projection] 🎯 High Passing TD Ceiling: Projected for {pass_td:.2f} passing touchdowns in high-scoring offensive attack")
                ceiling_boost += 3.0

            if pass_att >= 35.0:
                pos_reasons.append(f"[Volume] 🎯 High pass volume: projected for {pass_att:.1f} attempts + {rush_att:.1f} rushes")
                ceiling_boost += 3.0
            elif pass_att < 27.0 and rush_att < 4.0:
                neg_reasons.append(f"[Volume] ⚠️ Run-heavy script with minimal rushing: only {pass_att:.1f} pass attempts projected")
                floor_penalty += 8.0

        elif pos in ("D/ST", "DST"):
            spread_factor = max(-12.0, min(14.0, -team_spread * 1.8))
            implied_factor = max(-14.0, min(14.0, (22.5 - opp_implied) * 2.2))
            opp_score = min(100.0, max(25.0, 65.0 + spread_factor + implied_factor))

            if team_spread <= -3.5:
                pos_reasons.append(f"[Script] 🏈 Favored defensive script: team favored by {abs(team_spread):.1f} pts elevates sack & turnover opportunities")
                ceiling_boost += 5.0
            elif team_spread >= 5.0:
                neg_reasons.append(f"[Risk] ⚠️ Underdog game script: {abs(team_spread):.1f}-pt underdog limits defensive aggression")
                floor_penalty += 8.0

            if opp_implied <= 19.0:
                pos_reasons.append(f"[Matchup] 🛡️ Stifling environment: opponent implied total held to {opp_implied:.1f} pts")
                ceiling_boost += 4.0
            elif opp_implied >= 25.0:
                neg_reasons.append(f"[Risk] ⚠️ High-scoring opponent: opponent implied total {opp_implied:.1f} pts")
                floor_penalty += 6.0

        elif pos in ("K", "PK"):
            opp_score = min(100.0, max(30.0, 50.0 + ((implied_total - 20.0) * 3.8)))
            if implied_total >= 24.5:
                pos_reasons.append(f"[Volume] 🎯 High drive volume: team implied total {implied_total:.1f} pts yields frequent scoring chances")
                ceiling_boost += 4.0
            elif implied_total < 19.5:
                neg_reasons.append(f"[Risk] ⚠️ Limited drive volume: team implied total only {implied_total:.1f} pts")
                floor_penalty += 7.0

        else:
            opp_score = min(100.0, max(40.0, (proj / max(pos_baseline, 1.0)) * 75.0))

        # Receptions-Grounded Floor vs. Touchdown-Dependency Trap (Skill Positions: WR/RB/TE)
        if pos in ("WR", "RB", "FB", "TE") and proj > 0:
            rec_pts = (receptions * 1.0) + (rec_yds * 0.1)
            td_pts = total_tds * 6.0
            rec_pt_share = (rec_pts / proj) * 100.0
            td_pt_share = (td_pts / proj) * 100.0

            if rec_pt_share >= 68.0 and targets >= 5.0:
                pos_reasons.append(
                    f"[Volume] 🛡️ Receptions-Grounded Floor: {rec_pt_share:.0f}% of projected output derived from catches & yardage ({targets:.1f} tgts) providing bust-resistant PPR safety"
                )
            elif td_pt_share >= 38.0 and targets < 4.0 and proj >= 8.0:
                neg_reasons.append(
                    f"[Risk] ⚠️ Touchdown-Dependent Trap: {td_pt_share:.0f}% of projected fantasy output hinges on finding the end zone ({total_tds:.2f} TDs) with limited volume safety"
                )
                floor_penalty += 3.0

        # 3. Mathematical Matchup Component with Role Splits & Stud Elasticity
        matchup_score = 70.0
        matchup_grade = "NEUTRAL"
        matchup_resilience = "MODERATE_ELASTICITY"
        opp_dvp_rank: int | None = None
        opp_def_rank: int | None = None
        opp_off_rank: int | None = None

        is_receiving_back = (pos in ("RB", "FB")) and (targets >= 3.0 or receptions >= 2.5)
        is_slot_wr = (pos == "WR") and (targets >= 4.0 and (rec_yds / max(1.0, targets)) < 11.0)
        is_dst = pos in ("D/ST", "DST")

        if nfl_game and opponent != "BYE":
            opp_dvp_rank = dvp_client.get_position_rank(opponent, pos)
            opp_def_rank = dvp_client.get_overall_rank(opponent)
            opp_off_rank = dvp_client.get_overall_off_rank(opponent)

            # Defensive Funnel Detection (Pass Funnel vs Run Funnel) - applicable to offensive skill positions
            if not is_dst:
                funnel = dvp_client.detect_defensive_funnel(opponent)
                if funnel.get("is_pass_funnel"):
                    if pos in ("WR", "TE", "QB"):
                        pos_reasons.append(
                            f"[Matchup] 🎯 Pass Funnel Advantage: Opponent brick-wall run defense (#{funnel['rush_rank']}) funnels gameplan to vulnerable secondary (#{funnel['pass_rank']})"
                        )
                        ceiling_boost += 3.0
                    elif pos in ("RB", "FB") and targets < 3.0:
                        neg_reasons.append(
                            f"[Matchup] ⚠️ Run Defense Brick Wall: Opponent shuts down rush attempts (#{funnel['rush_rank']}), funneling volume away from early downs"
                        )
                        floor_penalty += 4.0
                elif funnel.get("is_run_funnel"):
                    if pos in ("RB", "FB"):
                        pos_reasons.append(
                            f"[Matchup] 🛡️ Run Funnel Advantage: Opponent elite coverage (#{funnel['pass_rank']}) forces offensive attack onto soft ground defense (#{funnel['rush_rank']})"
                        )
                        ceiling_boost += 3.0
                    elif pos in ("WR", "TE", "QB"):
                        neg_reasons.append(
                            f"[Script] 📉 Pass Funnel Stymied: Opponent pass defense (#{funnel['pass_rank']}) funnels action away from perimeter passing to ground game"
                        )
                        floor_penalty += 3.0

            if is_receiving_back:
                raw_matchup_score, matchup_grade, role_detail = dvp_client.calculate_role_matchup_score(
                    opponent, pos, is_receiving_back=True, team_spread=team_spread
                )
                if matchup_grade == "ELITE":
                    pos_reasons.append(f"[Matchup] 🚀 {role_detail}")
                    ceiling_boost += 6.0
                elif matchup_grade == "FAVORABLE":
                    pos_reasons.append(f"[Matchup] 🎯 {role_detail}")
                    ceiling_boost += 4.0
                elif matchup_grade == "BRUTAL":
                    neg_reasons.append(f"[Matchup] 🛑 {role_detail}")
                    floor_penalty += 6.0
                elif matchup_grade == "TOUGH":
                    neg_reasons.append(f"[Matchup] ⚠️ {role_detail}")
                    floor_penalty += 4.0
                else:
                    pos_reasons.append(f"[Matchup] 🛡️ {role_detail}")
            elif is_slot_wr:
                raw_matchup_score, matchup_grade, role_detail = dvp_client.calculate_role_matchup_score(
                    opponent, pos, is_slot=True, team_spread=team_spread
                )
                if matchup_grade == "ELITE":
                    pos_reasons.append(f"[Matchup] 🚀 {role_detail}")
                    ceiling_boost += 6.0
                elif matchup_grade == "FAVORABLE":
                    pos_reasons.append(f"[Matchup] 🎯 {role_detail}")
                    ceiling_boost += 4.0
                elif matchup_grade == "BRUTAL":
                    neg_reasons.append(f"[Matchup] 🛑 {role_detail}")
                    floor_penalty += 6.0
                elif matchup_grade == "TOUGH":
                    neg_reasons.append(f"[Matchup] ⚠️ {role_detail}")
                    floor_penalty += 4.0
                else:
                    pos_reasons.append(f"[Matchup] 🛡️ {role_detail}")
            elif is_dst:
                raw_matchup_score, matchup_grade = dvp_client.calculate_matchup_score(opponent, pos)
                if matchup_grade == "ELITE":
                    pos_reasons.append(f"[Matchup] 🚀 Elite favorable streaming matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs D/ST, Opp Offense #{opp_off_rank})")
                    ceiling_boost += 6.0
                elif matchup_grade == "FAVORABLE":
                    pos_reasons.append(f"[Matchup] 🛡️ Favorable streaming matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs D/ST, Opp Offense #{opp_off_rank})")
                    ceiling_boost += 4.0
                elif matchup_grade in ("TOUGH", "BRUTAL"):
                    # Evaluated against stud resilience below
                    pass
                else:
                    pos_reasons.append(f"[Matchup] 🛡️ Neutral matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs D/ST, Opp Offense #{opp_off_rank})")

                if opp_dvp_rank is not None and opp_dvp_rank >= 27:
                    pos_reasons.append(f"[Defense] 💥 Elite Generous Turnover Opponent: {opponent} offense ranks #{opp_dvp_rank} in fantasy points and sacks surrendered (league-best D/ST ceiling)")
                    ceiling_boost += 5.0
                elif opp_dvp_rank is not None and opp_dvp_rank >= 21:
                    pos_reasons.append(f"[Defense] 💥 Generous Turnover Opponent: {opponent} offense ranks #{opp_dvp_rank} in fantasy points and sacks surrendered")
                    ceiling_boost += 3.0
                elif opp_dvp_rank is not None and opp_dvp_rank <= 6:
                    neg_reasons.append(f"[Defense] ⚠️ Disciplined Ball-Control Offense: {opponent} rarely gives away sacks or turnovers (rank #{opp_dvp_rank} in D/ST points conceded)")
                    floor_penalty += 5.0
            else:
                raw_matchup_score, matchup_grade = dvp_client.calculate_matchup_score(opponent, pos)
                if matchup_grade == "ELITE":
                    pos_reasons.append(f"[Matchup] 🚀 Elite smash matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, Def rank #{opp_def_rank} - Prime Target Spot)")
                    ceiling_boost += 6.0
                elif matchup_grade == "FAVORABLE":
                    pos_reasons.append(f"[Matchup] 🛡️ Favorable matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, Def rank #{opp_def_rank})")
                    ceiling_boost += 4.0
                elif matchup_grade in ("TOUGH", "BRUTAL"):
                    # Evaluated against stud resilience below
                    pass
                else:
                    pos_reasons.append(f"[Matchup] 🛡️ Neutral matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos})")

            # Non-linear Matchup Elasticity Scaling:
            # Stud Invariance: Tier-1 Alphas command volume regardless of matchup (dampened elasticity)
            c_rank = getattr(player, "consensus_rank", 999.0) or 999.0
            opp_unit_label = f"Opp Offense #{opp_off_rank}" if is_dst else f"Def rank #{opp_def_rank}"

            # Extract Positional Stud Ranking (e.g. "WR8", "RB5", "TE2", "QB3")
            pos_rank_num = None
            if fp_pos:
                import re
                m = re.search(r'\d+', str(fp_pos))
                if m:
                    pos_rank_num = int(m.group())

            is_pos_stud = False
            if pos == "QB" and (pos_rank_num is not None and pos_rank_num <= 5):
                is_pos_stud = True
            elif pos in ("RB", "FB") and (pos_rank_num is not None and pos_rank_num <= 10):
                is_pos_stud = True
            elif pos == "WR" and (pos_rank_num is not None and pos_rank_num <= 12):
                is_pos_stud = True
            elif pos == "TE" and (pos_rank_num is not None and pos_rank_num <= 4):
                is_pos_stud = True

            if proj >= 16.5 or (fp_ecr is not None and fp_ecr <= 8) or c_rank <= 8.0 or is_pos_stud:
                elasticity = 0.35  # Max swing +/- 9 pts
                matchup_resilience = "MATCHUP_RESILIENT_STUD"
                pos_reasons.append("[Matchup] 🛡️ Alpha volume insulation: High target/touch share makes player matchup-resilient")
                if is_pos_stud:
                    pos_reasons.append(f"[Matchup] 🛡️ 8-Man Locked Stud: Elite {fp_pos or pos} alpha role overrides tough defense")
                if matchup_grade in ("TOUGH", "BRUTAL") and not (is_receiving_back or is_slot_wr):
                    if is_dst:
                        pos_reasons.append(f"[Matchup] 🛡️ Elite defense resilience: High turnover/sack floor overrides potent {opponent} offense")
                    else:
                        pos_reasons.append(f"[Matchup] 🛡️ Stud matchup resilience: Elite role overrides {matchup_grade.lower()} #{opp_dvp_rank} defense vs {pos}")
            elif proj >= 12.0 or (fp_ecr is not None and fp_ecr <= 18) or (pos_rank_num is not None and pos_rank_num <= 24):
                elasticity = 0.65  # Moderate swing +/- 16 pts
                matchup_resilience = "MODERATE_ELASTICITY"
                if matchup_grade == "BRUTAL" and not (is_receiving_back or is_slot_wr):
                    neg_reasons.append(f"[Matchup] 🛑 Brutal lockdown matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, {opp_unit_label})")
                    floor_penalty += 6.0
                elif matchup_grade == "TOUGH" and not (is_receiving_back or is_slot_wr):
                    neg_reasons.append(f"[Matchup] ⚠️ Tough matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, {opp_unit_label})")
                    floor_penalty += 4.0
            else:
                elasticity = 1.00  # Full sensitivity for streamers
                matchup_resilience = "MATCHUP_SENSITIVE_STREAMER"
                if matchup_grade == "BRUTAL" and not (is_receiving_back or is_slot_wr):
                    neg_reasons.append(f"[Matchup] 🛑 Brutal lockdown matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, {opp_unit_label})")
                    floor_penalty += 6.0
                elif matchup_grade == "TOUGH" and not (is_receiving_back or is_slot_wr):
                    neg_reasons.append(f"[Matchup] ⚠️ Tough matchup vs {opponent} (DvP rank #{opp_dvp_rank} vs {pos}, {opp_unit_label})")
                    floor_penalty += 4.0
                if raw_matchup_score <= 50.0:
                    if is_dst:
                        neg_reasons.append(f"[Risk] 🛑 Dangerous matchup vs high-powered offense: {opponent} rarely turns over the ball or concedes sacks")
                    else:
                        neg_reasons.append(f"[Risk] 🛑 High matchup sensitivity: Low baseline volume leaves {player.full_name} vulnerable to brutal defense")

            # 5-Star Smash & 1-Star Lockdown Triggers
            matchup_stars = dvp_client.get_matchup_stars(opp_dvp_rank)
            if matchup_stars == 5 and not is_dst:
                pos_reasons.append(f"[Matchup] ⭐ 5-Star Smash Matchup: Facing #{opp_dvp_rank} ranked defense vs {pos} (softest tier in NFL, bottom-6 in points allowed)")
                ceiling_boost += 3.0
            elif matchup_stars == 1 and not is_dst and not is_pos_stud and matchup_resilience != "MATCHUP_RESILIENT_STUD":
                neg_reasons.append(f"[Matchup] 🛑 1-Star Lockdown Alert: Facing #{opp_dvp_rank} ranked defense vs {pos} (stifling top-6 defense in fantasy points allowed)")
                floor_penalty += 3.0

            opp_profile = dvp_client.profiles.get(opponent)
            if opp_profile and not is_dst:
                if opp_profile.points_allowed_per_game >= 24.5:
                    pos_reasons.append(f"[Matchup] 🚨 Porous Scoring Defense: {opponent} allows {opp_profile.points_allowed_per_game:.1f} PPG, creating abundant offensive scoring opportunities")
                elif opp_profile.points_allowed_per_game <= 17.5 and not is_pos_stud and matchup_resilience != "MATCHUP_RESILIENT_STUD":
                    neg_reasons.append(f"[Matchup] 🔒 Elite Scoring Defense: {opponent} yields just {opp_profile.points_allowed_per_game:.1f} PPG, suppressing team touchdown ceiling")

            if pos == "QB" and opp_dvp_rank is not None and opp_dvp_rank <= 6 and not is_pos_stud and matchup_resilience != "MATCHUP_RESILIENT_STUD":
                neg_reasons.append(
                    f"[Defense] ⚠️ Ballhawk Pressure Risk: {opponent} secondary ranks #{opp_dvp_rank} vs QBs, elevating sack and interception volatility"
                )
                floor_penalty += 3.0

            # 3b. High-Signal DraftEdge Defense vs Position (DvP / FPA) Intelligence
            dvp_info = None
            if not is_dst and opponent != "BYE":
                try:
                    dvp_info = dvp_service.get_matchup_for_player(opponent, pos)
                    if dvp_info:
                        fpa = dvp_info.get("dk_fpa", 0.0)
                        vs_avg = dvp_info.get("vs_avg", 0.0)
                        softness = dvp_info.get("rank_softness", 16)
                        def_rank = dvp_info.get("rank_defense", 16)
                        supp = dvp_info.get("supporting_stats", {})
                        trend = dvp_info.get("trend", "")
                        tier_code = dvp_info.get("tier", "NEUTRAL")
                        base_ctx = " (2025-26 weighted baseline)" if dvp_info.get("is_baseline") else ""

                        if tier_code in ("SMASH", "FAVORABLE") or vs_avg >= 2.0:
                            vs_sign = f"+{vs_avg:.1f}" if vs_avg > 0 else f"{vs_avg:.1f}"
                            pos_reasons.append(
                                f"[Matchup] 🎯 Soft {pos} Matchup: {opponent} allows {fpa:.1f} DK pts/G to {pos}s ({vs_sign} vs avg, #{softness} softest){base_ctx}"
                            )
                            if pos == "QB" and supp.get("pass_yds", 0) >= 235.0:
                                pos_reasons.append(
                                    f"[Matchup] 🚀 Secondary Funnel: {opponent} concedes {supp['pass_yds']:.1f} pass yds and {supp.get('pass_td', 0):.2f} pass TDs/G"
                                )
                            elif pos in ("RB", "FB") and supp.get("rush_yds", 0) >= 105.0:
                                pos_reasons.append(
                                    f"[Matchup] 🚀 Generous Ground Defense: {opponent} yields {supp['rush_yds']:.1f} rush yds/G to running backs"
                                )
                            elif pos == "WR" and supp.get("rec_yds", 0) >= 145.0:
                                pos_reasons.append(
                                    f"[Matchup] 🚀 Wideout Mismatch: {opponent} surrenders {supp['rec_yds']:.1f} rec yds and {supp.get('rec_td', 0):.2f} TDs/G to WRs"
                                )
                            elif pos == "TE" and supp.get("targets", 0) >= 6.5:
                                pos_reasons.append(
                                    f"[Matchup] 🚀 Seam Vulnerability: {opponent} allows {supp['targets']:.1f} targets and {supp.get('rec_yds', 0):.1f} rec yds/G to TEs"
                                )
                        elif tier_code in ("TOUGH", "LOCKDOWN") or vs_avg <= -2.0:
                            vs_sign = f"{vs_avg:.1f}"
                            if not is_pos_stud and matchup_resilience != "MATCHUP_RESILIENT_STUD":
                                neg_reasons.append(
                                    f"[Matchup] 🛑 Stifling Defense vs {pos}: {opponent} holds {pos}s to {fpa:.1f} DK pts/G ({vs_sign} vs avg, #{def_rank} toughest in NFL){base_ctx}"
                                )
                                if pos == "QB" and supp.get("sacks", 0) >= 2.4:
                                    neg_reasons.append(
                                        f"[Defense] ⚠️ Trench Pressure Alert: {opponent} defense averages {supp['sacks']:.1f} sacks per game"
                                    )
                                elif pos in ("RB", "FB") and supp.get("rush_yds", 0) <= 85.0:
                                    neg_reasons.append(
                                        f"[Matchup] ⚠️ Brick-Wall Run Defense: {opponent} surrenders just {supp['rush_yds']:.1f} rush yds/G"
                                    )

                        if "Allowing more" in trend:
                            pos_reasons.append(f"[Matchup] 📈 Surging Generosity: {opponent} defensive trend: {trend}")
                        elif "Tightening up" in trend and softness >= 17 and not is_pos_stud:
                            neg_reasons.append(f"[Matchup] 📉 Stiffening Trend: {opponent} defensive trend: {trend}")
                except Exception as ex:
                    logger.debug("DvP enrichment skipped for %s vs %s: %s", player.full_name, opponent, ex)

            matchup_delta = raw_matchup_score - 70.0
            matchup_score = round(70.0 + (matchup_delta * elasticity), 1)
            matchup_score = max(20.0, min(100.0, matchup_score))

        # 4. Game Environment Component (DraftKings Implied Total & Shootout Potential)
        env_score = min(100.0, max(25.0, 50.0 + ((implied_total - 21.0) * 4.2)))
        if is_home:
            env_score = min(100.0, env_score + 3.5)

        if implied_total >= 25.0:
            pos_reasons.append(f"[Game Script] 🏈 High-scoring game script (Team implied total: {implied_total:.1f} pts)")
            ceiling_boost += 4.0
        elif implied_total < 19.5:
            neg_reasons.append(f"[Game Script] ⚠️ Low-scoring game environment (Team implied total: {implied_total:.1f} pts)")
            floor_penalty += 5.0

        if game_over_under >= 48.0 or implied_total >= 26.0:
            pos_reasons.append(f"[Game Script] 🚀 High-pace shootout environment: Vegas total {game_over_under:.1f} pts elevates offensive volume")
            ceiling_boost += 4.0
            env_score = min(100.0, env_score + 3.0)
        elif game_over_under <= 41.0 and implied_total <= 19.0:
            neg_reasons.append(f"[Game Script] 🐌 Trench Slog / Snail Pace: Low game total ({game_over_under:.1f} O/U) caps drive sustainability and scoring upside")
            floor_penalty += 4.0

        if abs(team_spread) <= 2.5 and game_over_under >= 46.0:
            pos_reasons.append(f"[Script] ⚔️ Competitive Shootout Script: Tight spread (±{abs(team_spread):.1f}) and high game total ({game_over_under:.1f} O/U) guarantees 4-quarter offensive aggressiveness")
            ceiling_boost += 3.0

        if is_home and team_spread <= -1.0:
            pos_reasons.append(f"[Environment] 🏟️ Home Favorite Advantage: Playing at home favored by {abs(team_spread):.1f} pts with crowd cadence and offensive timing edge")
        elif not is_home and team_spread >= 4.5:
            neg_reasons.append(f"[Environment] ✈️ Hostile Road Underdog Spot: Road underdog (+{team_spread:.1f}) in opposing venue introduces crowd-noise communication friction")

        # Vegas Implied Team Touchdown Bonanza vs Touchdown Desert
        if implied_total >= 27.0:
            pos_reasons.append(
                f"[Red Zone] 🚨 Implied Touchdown Bonanza: Vegas projects ~{implied_total / 7.0:.1f} team TDs ({implied_total:.1f} implied pts), supercharging red zone scoring opportunities"
            )
            ceiling_boost += 3.0
        elif implied_total <= 16.5 and opponent != "BYE":
            neg_reasons.append(
                f"[Red Zone] ⚠️ Touchdown Desert: Vegas projects only ~{implied_total / 7.0:.1f} team TDs ({implied_total:.1f} implied total), severely suppressing multi-touchdown ceiling"
            )
            floor_penalty += 3.0

        # WR vs CB Secondary Coverage Intelligence (PFF Model)
        wrcb_adv_score = None
        wrcb_adv_rating = None
        wrcb_primary_cb = None
        wrcb_is_shadow = False

        if pos == "WR" and opponent != "BYE":
            wrcb_res = wrcb_analyzer.analyze_matchup(
                player_id=player.id,
                full_name=player.full_name,
                pro_team=player.pro_team,
                opponent=opponent,
                projected_points=proj,
            )
            wrcb_adv_score = wrcb_res.advantage_score
            wrcb_adv_rating = wrcb_res.advantage_rating
            wrcb_primary_cb = wrcb_res.primary_cb.name
            wrcb_is_shadow = wrcb_res.is_shadow_projected

            if wrcb_is_shadow:
                neg_reasons.append(
                    f"[Matchup Intel] ⚠️ SHADOW ALERT: Projected shadow coverage by {wrcb_res.primary_cb.name} "
                    f"({wrcb_res.primary_cb.coverage_grade:.1f} Grade). Severe efficiency and ceiling suppression expected."
                )
                floor_penalty += 4.0
            elif wrcb_res.advantage_rating == "SLOT_MISMATCH":
                pos_reasons.append(
                    f"[Matchup Intel] 🔥 SLOT MISMATCH: {player.full_name} ({wrcb_res.alignment.pct_slot*100:.0f}% slot rate) vs "
                    f"{wrcb_res.slot_cb.name if wrcb_res.slot_cb else 'Nickel CB'} ({wrcb_res.slot_cb.coverage_grade if wrcb_res.slot_cb else 65.0:.1f} Grade). Prime full-PPR target funnel."
                )
                ceiling_boost += 3.0
            elif wrcb_res.advantage_rating in ("MAJOR_ADVANTAGE", "FAVORABLE"):
                pos_reasons.append(
                    f"[Matchup Intel] ⭐ WR/CB Advantage: +{wrcb_res.advantage_score:.1f}% matchup edge over {wrcb_res.primary_cb.name} ({wrcb_res.primary_cb.coverage_grade:.1f} Grade)."
                )

        # Vegas Game Script Intelligence (Action Network / ETR Model)
        game_script_code = None
        game_script_label = None
        if nfl_game:
            g_script, g_label, g_pace, g_plays, g_advice = vegas_gamescript_analyzer.classify_game(nfl_game)
            game_script_code = g_script
            game_script_label = g_label

            if g_script == "SHOOTOUT":
                pos_reasons.append(
                    f"[Vegas Game Script] 🔥 High-Ceiling Shootout ({nfl_game.over_under:.1f} O/U, ±{abs(nfl_game.spread):.1f} spread): Fast tempo ({g_plays} plays) elevates multi-TD upside."
                )
                ceiling_boost += 3.0
            elif g_script == "FAVORITE_RUN_FUNNEL" and pos in ("RB", "FB") and team_spread <= -6.5:
                pos_reasons.append(
                    f"[Vegas Game Script] 🏃 Positive Run Script: Large {abs(team_spread):.1f}-pt favorite projects heavy 2nd-half rushing volume and clock-killing touches."
                )
                ceiling_boost += 2.0
            elif g_script == "UNDERDOG_PASS_FUNNEL" and (pos in ("WR", "TE") or (pos in ("RB", "FB") and targets >= 2.5)):
                pos_reasons.append(
                    f"[Vegas Game Script] 📈 Trailing Pass Script: Underdog script elevates hurry-up aerial volume."
                )

        # Tactical Lineup Construction: Thursday Kickoff FLEX Rule
        if nfl_game and nfl_game.date and pos in ("WR", "RB", "FB", "TE"):
            is_thursday = False
            try:
                from datetime import datetime
                dt_str = nfl_game.date.split("T")[0]
                dt = datetime.strptime(dt_str, "%Y-%m-%d")
                if dt.weekday() == 3:  # Monday=0, Thursday=3
                    is_thursday = True
            except Exception:
                if "thu" in nfl_game.date.lower():
                    is_thursday = True

            if is_thursday:
                pos_reasons.append(
                    f"[Tactical] ⏰ Thursday Kickoff FLEX Rule: Play {player.full_name} in a {pos} slot rather than FLEX to maintain weekend lineup elasticity for late news"
                )

        # 5. Health & Availability Component
        health_score = 100.0
        status = (player.injury_status or "ACTIVE").upper()

        if injury_report:
            status = injury_report.status.upper()

        is_ruled_out = status in ("DOUBTFUL", "OUT", "IR", "INACTIVE", "SUSPENDED") or bool(injury_report and injury_report.is_out)
        if status == "ACTIVE" and not is_ruled_out:
            health_score = 100.0
            if not player.injured and (fp_inj_note is None or not fp_inj_note):
                pos_reasons.append("[Health] ✅ Clean Bill of Health: Full active status with zero injury report restrictions")
        elif status == "QUESTIONABLE" and not is_ruled_out:
            p_status = injury_report.practice_status if injury_report else None
            if p_status == "FULL":
                health_score = 90.0
                pos_reasons.append("[Health] 🏥 Logged Full Practice (FP) despite Questionable tag — standard workload expected")
                floor_penalty += 3.0
            elif p_status == "LIMITED":
                health_score = 75.0
                neg_reasons.append("[Health] ⚠️ Limited Practice Participation: Sidelined in portions of practice (LP) indicating in-game re-injury management")
                floor_penalty += 10.0
            elif p_status == "DNP":
                health_score = 50.0
                neg_reasons.append("[Risk] ⚠️ Elevated risk: Did Not Practice (DNP) on latest injury report")
                floor_penalty += 25.0
            else:
                health_score = 70.0
                detail = f": {injury_report.headline}" if (injury_report and injury_report.headline) else ""
                neg_reasons.append(f"[Risk] ⚠️ Questionable injury designation{detail}")
                floor_penalty += 15.0
        elif is_ruled_out:
            health_score = 0.0
            proj = 0.0
            proj_score = 0.0
            neg_reasons.append(f"[Risk] 🚨 Rule out: Listed as {status} (0.0 proj pts)")
            floor_penalty += 50.0

        # 6. Weather Component
        weather_score = 100.0
        weather_summary = None
        if weather:
            pos_w_score, pos_w_note = weather_client.get_weather_impact_for_position(pos, weather)
            weather_score = pos_w_score
            weather_summary = f"{weather.temperature_f}°F, {weather.wind_speed_mph} mph wind"
            if weather.is_dome:
                weather_summary = "Indoor Dome (Optimal)"
                pos_reasons.append("[Weather] 🏟️ Pristine indoor track: Climate-controlled dome eliminates weather friction")
                if pos in ("K", "PK"):
                    pos_reasons.append("[Weather] 🏟️ Climate-Controlled Kicking: Indoor dome eliminates wind turbulence and footing friction for long-range field goals")
            elif pos_w_note:
                if pos_w_score < 80.0:
                    neg_reasons.append(f"[Weather] 💨 Weather alert: {pos_w_note}")
                    floor_penalty += 6.0
                elif "boost" in pos_w_note or "script" in pos_w_note or "Defensive" in pos_w_note:
                    pos_reasons.append(f"[Weather] ☀️ {pos_w_note}")
                weather_summary += f" - {pos_w_note}"

        # Base composite StartScore
        w = self.weights
        composite = (
            w.projection_weight * proj_score
            + w.opportunity_weight * opp_score
            + w.matchup_weight * matchup_score
            + w.environment_weight * env_score
            + w.health_weight * health_score
            + w.weather_weight * weather_score
        )

        # 90th Percentile Ceiling Score
        raw_ceiling = (composite * 0.78) + (ceiling_boost * 1.8) + (proj_score * 0.15)
        if fp_std is not None and fp_std >= 1.4:
            raw_ceiling += (fp_std * 1.6)
            pos_reasons.append(f"[Floor/Ceiling] 🚀 Expert divergence (std dev +/-{fp_std:.2f}) elevates 90th percentile boom ceiling")
        if health_score < 60.0:
            raw_ceiling *= 0.60
        calc_ceiling = round(max(10.0, min(100.0, raw_ceiling)), 1)

        # 20th Percentile Floor Score
        raw_floor = (composite * 0.88) - (floor_penalty * 1.4)
        if fp_std is not None:
            if fp_std <= 0.8:
                raw_floor += 3.0
                pos_reasons.append(f"[Floor/Ceiling] 🛡️ Consensus lock (std dev +/-{fp_std:.2f}) provides elite cash floor")
            elif fp_std >= 2.2:
                raw_floor -= 3.0
                neg_reasons.append(f"[Risk] ⚠️ High expert disagreement (std dev +/-{fp_std:.2f}) signals volatile floor risk")

        if health_score < 80.0:
            raw_floor -= (80.0 - health_score) * 0.6
        calc_floor = round(max(0.0, min(95.0, raw_floor)), 1)

        # Contingency Upside for Backup RBs
        contingency_score = 0.0
        if pos in ("RB", "FB") and rush_att <= 9.0 and proj < 13.5:
            # Contingent workhorse upside if starting RB is sidelined
            efficiency = (rush_yds / max(1.0, rush_att)) if rush_att > 0 else 4.0
            contingent_touches = 16.0 + (targets * 1.2)
            contingency_score = round(min(92.0, max(65.0, 50.0 + (contingent_touches * 1.4) + (efficiency * 3.0))), 1)
            if contingency_score >= 68.0:
                pos_reasons.append(f"[Contingency] 🔒 High-Ceiling Handcuff: {contingency_score:.1f} contingent upside score if backfield touches consolidate")

        # Dynamic Strategy Mode application
        mode_str = str(getattr(mode, "default", mode) if hasattr(mode, "default") else (mode or "BALANCED"))
        mode_upper = mode_str.upper()
        if mode_upper == "CEILING":
            final_composite = (composite * 0.40) + (calc_ceiling * 0.60)
        elif mode_upper == "FLOOR":
            final_composite = (composite * 0.40) + (calc_floor * 0.60)
        else:
            final_composite = composite

        if is_ruled_out:
            final_composite = 0.0
            calc_ceiling = 0.0
            calc_floor = 0.0

        final_score = round(max(0.0, min(100.0, final_composite)), 1)

        # Confidence rating
        if health_score < 70.0 or opp_score < 55.0:
            confidence = "LOW"
        elif (final_score >= 76.0 and health_score >= 90.0) or final_score >= 80.0 or final_score <= 45.0:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        # Recommendation Category calibrated for league size / 8-man talent density
        if eff_size <= 8:
            if final_score >= 83.0:
                recommendation = "STRONG START"
            elif final_score >= 73.0:
                recommendation = "START"
            elif final_score >= 65.0:
                recommendation = "TOSS-UP"
            elif final_score >= 48.0:
                recommendation = "BENCH"
            else:
                recommendation = "SIT"
        else:
            if final_score >= 82.0:
                recommendation = "STRONG START"
            elif final_score >= 70.0:
                recommendation = "START"
            elif final_score >= 60.0:
                recommendation = "TOSS-UP"
            elif final_score >= 45.0:
                recommendation = "BENCH"
            else:
                recommendation = "SIT"

        playoff_score, playoff_grade = calculate_playoff_sos(player.pro_team, pos)
        dynamic_vorp = round(proj - pos_baseline, 1)

        if dynamic_vorp >= 5.5:
            pos_reasons.append(f"[8-Man PPR Leverage] 🚀 Dominant Positional Edge: +{dynamic_vorp:.1f} VORP advantage over shallow league replacement baseline")
        elif dynamic_vorp <= -2.5 and pos in ("QB", "TE", "WR") and final_score < 70.0 and contingency_score == 0.0:
            neg_reasons.append(f"[8-Man PPR Trap] ⚠️ Sub-Baseline Replacement Value: {dynamic_vorp:.1f} VORP below starter caliber in competitive 8-man formats")

        if playoff_grade == "ELITE":
            pos_reasons.append(f"[Schedule] 🏆 Championship Playoff Schedule: Weeks 15–17 fantasy playoff schedule graded ELITE (score {playoff_score:.1f})")
        elif playoff_grade in ("BRUTAL", "TOUGH") and eff_size <= 8 and final_score < 68.0:
            neg_reasons.append(f"[Schedule] ⚠️ Tough Playoff Outlook: Weeks 15–17 fantasy playoff stretch rated {playoff_grade} (score {playoff_score:.1f})")

        # 7. Vegas Sportsbook Player Proposition Markets & Implied PPR Points
        props_data = vegas_props_client._synthesize_props_from_vegas(
            player_id=player.id,
            player_name=player.full_name,
            position=pos,
            team=player.pro_team,
            opponent=opponent,
            implied_team_total=implied_total,
            spread=team_spread,
            over_under=game_over_under,
            projected_points=proj,
        )
        vegas_props_client._calculate_implied_ppr(props_data, implied_team_total=implied_total)

        # 7a. Core Vegas Grade Consensus Outlook
        if props_data.vegas_grade in ("VERY_ELITE", "ELITE"):
            pos_reasons.append(
                f"[Vegas Props] {props_data.vegas_grade_label}: {props_data.vegas_takeaway}"
            )
        elif props_data.vegas_grade in ("FADE", "VERY_BAD"):
            neg_reasons.append(
                f"[Vegas Props] {props_data.vegas_grade_label}: {props_data.vegas_takeaway}"
            )

        # 7b. Reception Floor Anchor (WR / TE / RB)
        if props_data.receptions_ou and props_data.receptions_ou >= 5.5:
            pos_reasons.append(
                f"[Vegas Props] 🎯 High-Volume PPR Floor: Sportsbooks price {props_data.receptions_ou} Receptions O/U, confirming script-proof target volume"
            )
        elif pos == "TE" and props_data.receptions_ou and props_data.receptions_ou >= 4.5:
            pos_reasons.append(
                f"[Vegas Props] 🎯 Elite TE Target Share: Sportsbooks price {props_data.receptions_ou} Receptions O/U as focal seam weapon"
            )
        elif pos in ("WR", "TE") and props_data.receptions_ou and props_data.receptions_ou <= 2.5 and final_score < 72.0:
            neg_reasons.append(
                f"[Vegas Props] ⚠️ Capped Reception Floor: Low {props_data.receptions_ou} Receptions O/U warns of heavy reliance on low-probability chunk plays"
            )

        # 7c. Anytime Touchdown (ATD) Probability & Red Zone Equity
        if props_data.anytime_td_prob >= 0.48:
            odds_str = f" ({props_data.anytime_td_odds:+d})" if props_data.anytime_td_odds else ""
            pos_reasons.append(
                f"[Vegas Props] 💰 Red Zone TD Equity: Heavy {int(props_data.anytime_td_prob * 100)}% anytime TD probability{odds_str} establishes premier scoring ceiling"
            )
        elif pos in ("WR", "TE", "RB") and props_data.anytime_td_prob <= 0.20 and final_score < 70.0:
            odds_str = f" ({props_data.anytime_td_odds:+d})" if props_data.anytime_td_odds else ""
            neg_reasons.append(
                f"[Vegas Props] ⚠️ Touchdown-Drought Risk: Only {int(props_data.anytime_td_prob * 100)}% anytime TD odds{odds_str} severely suppresses non-yardage ceiling"
            )

        # 7d. RB Workhorse Carry Line vs Committee Warning
        if pos == "RB":
            if props_data.rush_att_ou and props_data.rush_att_ou >= 15.5:
                pos_reasons.append(
                    f"[Vegas Props] 🏃 Bellcow Carry Line: {props_data.rush_att_ou} Carries O/U signals heavy 2nd-half clock-killing volume in favorable game script"
                )
            elif props_data.rush_att_ou and props_data.rush_att_ou <= 9.5 and final_score < 70.0:
                neg_reasons.append(
                    f"[Vegas Props] ⚠️ Limited Rushing Volume: Under {props_data.rush_att_ou} Carries O/U warns of a timeshare or pass-heavy deficit"
                )

        # 7e. QB Passing Line Script
        if pos == "QB":
            if props_data.pass_yards_ou and props_data.pass_yards_ou >= 250.0 and implied_total >= 22.5:
                pos_reasons.append(
                    f"[Vegas Props] 🚀 High-Volume Passing Line: {props_data.pass_yards_ou} Pass Yds O/U with 1.5 Pass TDs O/U validates a pass-funnel shootout script"
                )
            elif props_data.pass_yards_ou and props_data.pass_yards_ou <= 195.0 and final_score < 72.0:
                neg_reasons.append(
                    f"[Vegas Props] ⚠️ Low Passing Expectations: Sub-{props_data.pass_yards_ou} Pass Yds O/U caps upside in a run-heavy or defensive slugfest"
                )

        # 7f. Market-Implied Fantasy Discrepancy (Sharp Edge)
        if props_data.implied_ppr_points > 0 and proj > 0:
            market_diff = round(props_data.implied_ppr_points - proj, 1)
            if market_diff >= 2.5:
                pos_reasons.append(
                    f"[Vegas Props] 📈 Sharp Market Discrepancy: Sportsbooks imply {props_data.implied_ppr_points:.1f} PPR pts (+{market_diff:.1f} over projection) — betting markets strongly favor the over"
                )
            elif market_diff <= -2.5 and final_score < 72.0:
                neg_reasons.append(
                    f"[Vegas Props] 📉 Sharp Market Skepticism: Sportsbooks imply only {props_data.implied_ppr_points:.1f} PPR pts ({market_diff:.1f} below projection) — volume expectations are tempered"
                )

        # 7g. Kicker & D/ST Vegas Factor Symmetry
        if pos == "K":
            if implied_total >= 25.0:
                pos_reasons.append(
                    f"[Vegas Props] ⚡ High-Scoring Kicking Script: {implied_total:.1f} team implied total projects frequent red-zone drives and multi-FG opportunities"
                )
            elif implied_total <= 18.0 and final_score < 70.0:
                neg_reasons.append(
                    f"[Vegas Props] ⚠️ Low Scoring Ceiling: Sub-{implied_total:.1f} team implied total severely limits kicking volume and scoring opportunities"
                )
        elif pos in ("D/ST", "DST"):
            opp_implied = round(max(10.0, game_over_under - implied_total), 1)
            if game_over_under <= 41.0 or opp_implied <= 18.5:
                pos_reasons.append(
                    f"[Vegas Props] 🛡️ Defensive Slugfest Environment: Low {game_over_under:.1f} game total (opponent implied {opp_implied:.1f} pts) projects heavy punting and turnover equity"
                )
            elif game_over_under >= 48.0 or opp_implied >= 26.0:
                neg_reasons.append(
                    f"[Vegas Props] ⚠️ High-Scoring Shootout Threat: High {game_over_under:.1f} game total (opponent implied {opp_implied:.1f} pts) threatens points-allowed penalties"
                )

        # 8. Boris Chen GMM Tier Clustering
        boris_tier_num = fp_tier
        if boris_tier_num is None:
            if fp_ecr:
                if fp_ecr <= 6:
                    boris_tier_num = 1
                elif fp_ecr <= 14:
                    boris_tier_num = 2
                elif fp_ecr <= 24:
                    boris_tier_num = 3
                elif fp_ecr <= 36:
                    boris_tier_num = 4
                elif fp_ecr <= 50:
                    boris_tier_num = 5
                else:
                    boris_tier_num = 6
            else:
                boris_tier_num = 1 if proj >= 18.0 else (2 if proj >= 14.5 else (3 if proj >= 11.5 else 4))

        boris_tier_label = f"Tier {boris_tier_num}" if boris_tier_num else None
        boris_is_dropoff = bool(fp_std and fp_std >= 1.8)

        if boris_tier_num == 1:
            pos_reasons.append("[Boris Chen] 💎 Tier 1 Undisputed Stud: Top statistical cluster of weekly fantasy starters")
        elif boris_tier_num == 2:
            pos_reasons.append("[Boris Chen] 🥈 Tier 2 Anchor: Locked into high-end starter tier with safe weekly touch expectation")

        def dedupe(lst: list[str]) -> list[str]:
            seen = set()
            out = []
            for item in lst:
                if item not in seen:
                    seen.add(item)
                    out.append(item)
            return out

        sorted_pos = sort_factor_reasons(dedupe(pos_reasons))
        sorted_neg = sort_factor_reasons(dedupe(neg_reasons))

        # Resilient multi-source projection resolution
        if is_ruled_out:
            res_model_pts = 0.0
            res_fp_pts = 0.0
            res_sleeper_pts = 0.0
            res_espn_pts = 0.0
            res_consensus_pts = 0.0
        else:
            res_model_pts = q_proj.model_points if q_proj and q_proj.model_points > 0 else (getattr(player, "projected_points_model", 0.0) or proj)
            res_fp_pts = q_proj.fp_points if q_proj and q_proj.fp_points > 0 else (getattr(player, "projected_points_fp", 0.0) or getattr(player, "fp_r2p_pts", 0.0) or 0.0)
            res_sleeper_pts = q_proj.sleeper_points if q_proj and q_proj.sleeper_points > 0 else (getattr(player, "projected_points_sleeper", 0.0) or 0.0)
            res_espn_pts = q_proj.espn_points if q_proj and q_proj.espn_points > 0 else (getattr(player, "projected_points_espn", 0.0) or 0.0)
            res_consensus_pts = q_proj.consensus_points if q_proj and q_proj.consensus_points > 0 else (getattr(player, "projected_points_consensus", 0.0) or proj)

        act_pts = float(actual_points if actual_points is not None else (getattr(player, "actual_points", 0.0) or 0.0))
        game_started = bool(nfl_game.is_started if nfl_game else False)
        game_final = bool(nfl_game.is_final if nfl_game else False)

        if game_final:
            g_status = "FINAL"
        elif game_started or lineup_locked:
            g_status = "LIVE" if (act_pts > 0 or not game_final) else "FINAL"
        elif act_pts > 0:
            g_status = "FINAL"
        else:
            g_status = "UPCOMING"

        if g_status == "FINAL":
            eff_pts = round(act_pts, 2)
        elif g_status == "LIVE":
            eff_pts = round(act_pts if act_pts > 0 else proj, 2)
        else:
            eff_pts = round(proj, 2)

        return StartSitEvaluation(
            player_id=player.id,
            full_name=player.full_name,
            position=pos,
            pro_team=player.pro_team,
            projected_points=round(proj, 2),
            actual_points=round(act_pts, 2),
            lineup_locked=lineup_locked,
            is_started=game_started,
            is_final=game_final,
            game_status=g_status,
            effective_points=eff_pts,
            start_score=final_score,
            confidence=confidence,
            recommendation=recommendation,
            matchup_grade=matchup_grade,
            opponent=opponent,
            is_home=is_home,
            implied_team_total=round(implied_total, 1),
            injury_status=status,
            weather_summary=weather_summary,
            reasons_positive=sorted_pos,
            reasons_negative=sorted_neg,
            components=ComponentScores(
                projection_score=round(proj_score, 1),
                opportunity_score=round(opp_score, 1),
                matchup_score=round(matchup_score, 1),
                environment_score=round(env_score, 1),
                health_score=round(health_score, 1),
                weather_score=round(weather_score, 1),
            ),
            itemized_stats=stats,
            upcoming_schedule=player.upcoming_schedule or [],
            consensus_rank=fp_ave or (c_rank if c_rank < 900 else None),
            ceiling_score=calc_ceiling,
            floor_score=calc_floor,
            contingency_score=contingency_score,
            mode=mode_upper,
            game_date=nfl_game.date if nfl_game else None,
            live_vorp=dynamic_vorp,
            fp_rank_ecr=fp_ecr,
            fp_pos_rank=fp_pos,
            fp_tier=fp_tier,
            fp_rank_ave=fp_ave,
            fp_rank_std=fp_std,
            fp_start_sit_grade=fp_grade,
            fp_r2p_pts=fp_r2p,
            fp_injury_note=fp_inj_note,
            matchup_resilience=matchup_resilience,
            playoff_sos_score=playoff_score,
            playoff_sos_grade=playoff_grade,
            opp_dvp_rank=opp_dvp_rank,
            opp_def_rank=opp_def_rank,
            opp_off_rank=opp_off_rank if is_dst else None,
            opp_dvp_grade=matchup_grade,
            matchup_stars=dvp_client.get_matchup_stars(opp_dvp_rank) if opp_dvp_rank is not None else None,
            dvp_source="FantasyPros Consensus",
            volume_share=q_proj.volume_share if q_proj else None,
            team_projected_plays=q_proj.team_projected_plays if q_proj else None,
            team_pass_att=q_proj.team_pass_att if q_proj else None,
            team_rush_att=q_proj.team_rush_att if q_proj else None,
            efficiency_multiplier=q_proj.efficiency_multiplier if q_proj else None,
            proj_model=round(res_model_pts, 2),
            proj_fantasypros=round(res_fp_pts, 2),
            proj_sleeper=round(res_sleeper_pts, 2),
            proj_espn=round(res_espn_pts, 2),
            proj_consensus=round(res_consensus_pts, 2),
            projected_points_model=round(res_model_pts, 2),
            projected_points_fp=round(res_fp_pts, 2),
            projected_points_sleeper=round(res_sleeper_pts, 2),
            projected_points_espn=round(res_espn_pts, 2),
            projected_points_consensus=round(res_consensus_pts, 2),
            active_projection_source=q_proj.active_source if q_proj else projection_source,
            consensus_spread=q_proj.consensus_spread if q_proj else 0.0,
            consensus_agreement=q_proj.consensus_agreement if q_proj else "HIGH_AGREEMENT",
            floor_points=q_proj.floor_points if q_proj else round(max(0.0, proj * 0.65), 1),
            ceiling_points=q_proj.ceiling_points if q_proj else round(proj * 1.45, 1),
            fp_itemized_stats=getattr(player, "fp_projected_stats", {}) or {},
            sleeper_itemized_stats=getattr(player, "sleeper_projected_stats", {}) or {},
            model_provenance=q_proj.model_provenance if q_proj else {},
            wrcb_advantage_score=wrcb_adv_score,
            wrcb_advantage_rating=wrcb_adv_rating,
            wrcb_primary_cb=wrcb_primary_cb,
            wrcb_is_shadow=wrcb_is_shadow,
            game_script=game_script_code,
            game_script_label=game_script_label,
            props_receptions_ou=props_data.receptions_ou,
            props_rec_yds_ou=props_data.rec_yards_ou,
            props_rush_yds_ou=props_data.rush_yards_ou,
            props_rush_att_ou=props_data.rush_att_ou,
            props_pass_yds_ou=props_data.pass_yards_ou,
            props_pass_tds_ou=props_data.pass_tds_ou,
            props_anytime_td_odds=props_data.anytime_td_odds,
            props_anytime_td_prob=props_data.anytime_td_prob,
            props_implied_ppr_pts=props_data.implied_ppr_points,
            props_market_sentiment=props_data.market_sentiment,
            props_sharp_notes=props_data.sharp_notes,
            props_vegas_grade=props_data.vegas_grade,
            props_vegas_grade_label=props_data.vegas_grade_label,
            props_vegas_grade_color=props_data.vegas_grade_color,
            props_vegas_takeaway=props_data.vegas_takeaway,
            boris_chen_tier=boris_tier_num,
            boris_chen_tier_label=boris_tier_label,
            boris_chen_is_dropoff=boris_is_dropoff,
            dvp_fpa=dvp_info,
        )



scoring_engine = StartSitScoringEngine()
