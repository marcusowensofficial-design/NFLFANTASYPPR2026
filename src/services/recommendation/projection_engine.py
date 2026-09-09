"""Institutional Quant DFS Projection Engine.

Provides mathematically grounded, transparent projections combining:
1. Macro Vegas Game Environment (ITT, spread, expected offensive plays).
2. Play-calling distribution (Pass/Run script modeling).
3. Depth-chart micro volume allocation (Target & Carry shares with injury reallocation).
4. Positional efficiency adjusted for opponent DvP and weather.
5. Multi-Source Bayesian Ensembling (Model 45%, FantasyPros 35%, ESPN 20%).
"""

import logging
import statistics
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.espn.schemas import ItemizedStatLine
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.schedule_client import NFLGame
from src.adapters.weather.client import WeatherReport
from src.db.models import PlayerModel

logger = logging.getLogger(__name__)


@dataclass
class TeamGameScriptContext:
    """Macro Vegas game environment and play distribution for a team."""
    pro_team: str
    opponent: str
    is_home: bool
    implied_team_total: float
    spread: float  # Negative = favorite, Positive = underdog
    over_under: float
    expected_plays: float
    pass_ratio: float
    expected_pass_attempts: float
    expected_rush_attempts: float
    expected_team_tds: float
    is_dome: bool
    wind_mph: float


class PlayerProjectionResult(BaseModel):
    """Calibrated output for a player's projected statline with complete mathematical provenance."""
    projected_points: float
    model_points: float = 0.0
    fp_points: float = 0.0
    sleeper_points: float = 0.0
    espn_points: float = 0.0
    consensus_points: float = 0.0
    active_points: float = 0.0
    active_source: str = "MODEL"
    consensus_spread: float = 0.0
    consensus_agreement: str = "HIGH_AGREEMENT"
    itemized_stats: ItemizedStatLine
    volume_share: float  # Target share % (WR/TE/RB) or Carry share % (RB)
    team_projected_plays: float
    team_pass_att: float
    team_rush_att: float
    efficiency_multiplier: float  # % delta from baseline (-15% to +15%)
    model_provenance: dict[str, Any] = Field(default_factory=dict)
    floor_points: float
    median_points: float
    ceiling_points: float


class QuantProjectionEngine:
    """Enterprise-grade quantitative projection model for NFL DFS and season-long fantasy."""

    def __init__(
        self,
        model_weight: float = 0.35,
        fantasypros_weight: float = 0.30,
        sleeper_weight: float = 0.20,
        espn_weight: float = 0.15,
    ):
        self.model_weight = model_weight
        self.fantasypros_weight = fantasypros_weight
        self.sleeper_weight = sleeper_weight
        self.espn_weight = espn_weight

    def build_game_script_context(
        self,
        pro_team: str,
        nfl_game: NFLGame | None = None,
        weather: WeatherReport | None = None,
    ) -> TeamGameScriptContext:
        """Derive macro expected plays and pass/run distribution from Vegas lines."""
        team = pro_team.upper().strip()
        if team == "FA":
            return TeamGameScriptContext(
                pro_team=team,
                opponent="BYE",
                is_home=False,
                implied_team_total=0.0,
                spread=0.0,
                over_under=0.0,
                expected_plays=0.0,
                pass_ratio=0.58,
                expected_pass_attempts=0.0,
                expected_rush_attempts=0.0,
                expected_team_tds=0.0,
                is_dome=False,
                wind_mph=0.0,
            )

        if not nfl_game:
            return TeamGameScriptContext(
                pro_team=team,
                opponent="OPP",
                is_home=False,
                implied_team_total=21.0,
                spread=0.0,
                over_under=44.0,
                expected_plays=63.0,
                pass_ratio=0.58,
                expected_pass_attempts=36.5,
                expected_rush_attempts=26.5,
                expected_team_tds=2.5,
                is_dome=False,
                wind_mph=0.0,
            )

        is_home = nfl_game.is_home_for_team(team)
        opp = nfl_game.get_opponent_for_team(team) or "BYE"
        itt = nfl_game.get_implied_total_for_team(team)
        team_spread = nfl_game.spread if is_home else -nfl_game.spread
        ou = nfl_game.over_under
        is_dome = nfl_game.is_dome
        wind = weather.wind_speed_mph if weather and not weather.is_dome else 0.0

        # Expected plays calibrated around NFL median (63.5 plays per 60 min)
        # Higher game totals indicate faster pace and more total plays
        ou_delta = ou - 44.0
        expected_plays = round(max(55.0, min(75.0, 63.5 + (ou_delta * 0.38))), 1)

        # Baseline Pass Ratio in modern NFL is ~58%
        # Underdogs pass more to chase points; Favorites run more to bleed clock
        # team_spread > 0 means underdog (e.g. +6.5 underdog)
        spread_pass_adj = team_spread * 0.0075
        pass_ratio = max(0.48, min(0.70, 0.58 + spread_pass_adj))

        # Weather wind dampens pass ratio if extreme
        if wind >= 18.0:
            pass_ratio = max(0.44, pass_ratio - 0.05)

        pass_att = round(expected_plays * pass_ratio, 1)
        rush_att = round(expected_plays * (1.0 - pass_ratio), 1)
        team_tds = round(itt / 7.0, 2)

        return TeamGameScriptContext(
            pro_team=team,
            opponent=opp,
            is_home=is_home,
            implied_team_total=round(itt, 1),
            spread=round(team_spread, 1),
            over_under=round(ou, 1),
            expected_plays=expected_plays,
            pass_ratio=round(pass_ratio, 3),
            expected_pass_attempts=pass_att,
            expected_rush_attempts=rush_att,
            expected_team_tds=team_tds,
            is_dome=is_dome,
            wind_mph=round(wind, 1),
        )

    def calculate_player_projection(
        self,
        player: PlayerModel,
        nfl_game: NFLGame | None = None,
        weather: WeatherReport | None = None,
        projection_source: str = "MODEL",
    ) -> PlayerProjectionResult:
        """Run hierarchical bottom-up volume allocation + Bayesian multi-source ensemble."""
        pos = player.position.upper().strip()
        context = self.build_game_script_context(player.pro_team, nfl_game, weather)

        if context.opponent == "BYE":
            zero_stats = ItemizedStatLine()
            return PlayerProjectionResult(
                projected_points=0.0,
                model_points=0.0,
                fp_points=0.0,
                espn_points=0.0,
                consensus_points=0.0,
                active_points=0.0,
                active_source="MODEL",
                consensus_spread=0.0,
                consensus_agreement="HIGH_AGREEMENT",
                itemized_stats=zero_stats,
                volume_share=0.0,
                team_projected_plays=0.0,
                team_pass_att=0.0,
                team_rush_att=0.0,
                efficiency_multiplier=0.0,
                model_provenance={"reason": "BYE week"},
                floor_points=0.0,
                median_points=0.0,
                ceiling_points=0.0,
            )

        # 1. Determine Matchup Efficiency Multiplier (from DvP)
        dvp_rank = dvp_client.get_position_rank(context.opponent, pos)
        if pos in ("D/ST", "DST"):
            unit_rank = dvp_client.get_overall_off_rank(context.opponent)
        else:
            unit_rank = dvp_client.get_overall_rank(context.opponent)
        
        # DvP: 1 is toughest, 32 is softest. Neutral is 16.5
        dvp_delta = (dvp_rank - 16.5) / 15.5  # -1.0 to +1.0
        unit_delta = (unit_rank - 16.5) / 15.5
        blended_matchup = (0.75 * dvp_delta) + (0.25 * unit_delta)
        # Efficiency swings between -10% (vs #1 unit) to +12% (vs #32)
        efficiency_mult = round(blended_matchup * 0.11, 3)

        # Weather wind drag on passing
        wind_drag = 0.0
        if context.wind_mph > 15.0 and pos in ("QB", "WR", "TE", "K"):
            wind_drag = min(0.15, (context.wind_mph - 15.0) * 0.012)
        total_efficiency_adj = round(1.0 + efficiency_mult - wind_drag, 3)

        # 2. Extract Prior Baseline / Consensus Signals
        espn_proj = getattr(player, "projected_points_espn", 0.0) or player.projected_points or 0.0
        raw_espn_stats = player.projected_stats or {}
        fp_r2p = getattr(player, "projected_points_fp", 0.0) or getattr(player, "fp_r2p_pts", None)
        fp_ecr = getattr(player, "fp_rank_ecr", None)

        # 3. Model-Driven Volume Allocation by Position
        quant_stats = ItemizedStatLine()
        volume_share = 0.0

        if pos == "QB":
            has_explicit_pass_att = "pass_att" in raw_espn_stats
            pass_att = float(raw_espn_stats["pass_att"]) if has_explicit_pass_att else context.expected_pass_attempts
            cmp = float(raw_espn_stats.get("pass_cmp", round(pass_att * max(0.58, min(0.72, 0.655 * total_efficiency_adj)), 1)))
            pass_yds = float(raw_espn_stats.get("pass_yds", round(pass_att * max(5.8, min(8.6, 7.25 * total_efficiency_adj)), 1)))
            pass_td = float(raw_espn_stats.get("pass_td", round(pass_att * max(0.025, min(0.075, (context.expected_team_tds * 0.65) / max(pass_att, 1.0))), 2)))
            pass_int = float(raw_espn_stats.get("pass_int", round(pass_att * max(0.012, min(0.032, 0.018 / max(0.8, total_efficiency_adj))), 2)))

            rush_att = float(raw_espn_stats.get("rush_att", 2.0))
            rush_yds = float(raw_espn_stats.get("rush_yds", round(rush_att * 4.8, 1)))
            rush_td = float(raw_espn_stats.get("rush_td", round(rush_att * 0.04, 2)))

            quant_stats = ItemizedStatLine(
                pass_att=pass_att,
                pass_cmp=cmp,
                pass_yds=pass_yds,
                pass_td=pass_td,
                pass_int=pass_int,
                rush_att=rush_att,
                rush_yds=rush_yds,
                rush_td=rush_td,
            )
            volume_share = 100.0

        elif pos in ("RB", "FB"):
            has_explicit_rush = "rush_att" in raw_espn_stats
            has_explicit_tgt = "targets" in raw_espn_stats
            hist_carries = float(raw_espn_stats.get("rush_att", 12.0 if espn_proj >= 10.0 else max(2.0, espn_proj * 0.8)))
            hist_tgt = float(raw_espn_stats.get("targets", 2.5 if espn_proj >= 10.0 else max(0.5, espn_proj * 0.2)))
            
            # Carry share percentage of team total
            carry_share = min(0.82, max(0.15, hist_carries / max(context.expected_rush_attempts, 18.0)))
            volume_share = round(carry_share * 100.0, 1)
            rush_att = float(raw_espn_stats["rush_att"]) if has_explicit_rush else round(context.expected_rush_attempts * carry_share, 1)

            if "rush_yds" in raw_espn_stats:
                rush_yds = float(raw_espn_stats["rush_yds"])
            else:
                ypc = max(3.5, min(5.4, 4.35 * total_efficiency_adj))
                rush_yds = round(rush_att * ypc, 1)

            if "rush_td" in raw_espn_stats:
                rush_td = float(raw_espn_stats["rush_td"])
            else:
                td_share = carry_share * (context.expected_team_tds * 0.40)
                rush_td = round(max(0.1, min(1.3, td_share)), 2)

            # Receiving profile
            tgt_share = min(0.22, max(0.04, hist_tgt / max(context.expected_pass_attempts, 25.0)))
            targets = float(raw_espn_stats["targets"]) if has_explicit_tgt else round(context.expected_pass_attempts * tgt_share, 1)

            if "receptions" in raw_espn_stats:
                rec = float(raw_espn_stats["receptions"])
            else:
                rec = round(targets * 0.78, 1)

            if "rec_yds" in raw_espn_stats:
                rec_yds = float(raw_espn_stats["rec_yds"])
            else:
                rec_yds = round(rec * 7.4 * total_efficiency_adj, 1)

            if "rec_td" in raw_espn_stats:
                rec_td = float(raw_espn_stats["rec_td"])
            else:
                rec_td = round(targets * 0.025, 2)

            quant_stats = ItemizedStatLine(
                rush_att=rush_att,
                rush_yds=rush_yds,
                rush_td=rush_td,
                targets=targets,
                receptions=rec,
                rec_yds=rec_yds,
                rec_td=rec_td,
            )

        elif pos in ("WR", "TE"):
            has_explicit_tgt = "targets" in raw_espn_stats
            hist_tgt = float(raw_espn_stats.get("targets", 6.5 if espn_proj >= 10.0 else max(1.0, espn_proj * 0.45)))
            # Target share allocation
            tgt_share = min(0.32, max(0.04, hist_tgt / max(context.expected_pass_attempts, 28.0)))
            volume_share = round(tgt_share * 100.0, 1)
            targets = float(raw_espn_stats["targets"]) if has_explicit_tgt else round(context.expected_pass_attempts * tgt_share, 1)

            if "receptions" in raw_espn_stats:
                rec = float(raw_espn_stats["receptions"])
            else:
                catch_rate = 0.65 if pos == "WR" else 0.72
                catch_rate = max(0.55, min(0.82, catch_rate * total_efficiency_adj))
                rec = round(targets * catch_rate, 1)

            if "rec_yds" in raw_espn_stats:
                rec_yds = float(raw_espn_stats["rec_yds"])
            else:
                ypt = 8.4 if pos == "WR" else 7.6
                ypt = max(6.0, min(11.5, ypt * total_efficiency_adj))
                rec_yds = round(targets * ypt, 1)

            if "rec_td" in raw_espn_stats:
                rec_td = float(raw_espn_stats["rec_td"])
            else:
                td_share = (tgt_share * 1.25) * (context.expected_team_tds * 0.65)
                rec_td = round(max(0.05, min(1.2, td_share)), 2)

            rush_att = float(raw_espn_stats.get("rush_att", 0.0))
            rush_yds = float(raw_espn_stats.get("rush_yds", round(rush_att * 6.0, 1)))
            rush_td = float(raw_espn_stats.get("rush_td", round(rush_att * 0.03, 2)))

            quant_stats = ItemizedStatLine(
                targets=targets,
                receptions=rec,
                rec_yds=rec_yds,
                rec_td=rec_td,
                rush_att=rush_att,
                rush_yds=rush_yds,
                rush_td=rush_td,
            )

        elif pos in ("D/ST", "DST"):
            opp_itt = nfl_game.get_implied_total_for_team(context.opponent) if nfl_game else 21.0
            # Sacks: facing generous/turnover-prone offenses yields more sacks
            # dvp_rank for D/ST is 1-32 where 32 = softest / most sacks & turnovers conceded
            base_sacks = 2.4 + (0.08 * -context.spread) + ((24.0 - opp_itt) * 0.08)
            sacks = round(max(1.0, min(5.5, base_sacks * (1.0 + (dvp_rank - 16.5) * 0.025))), 1)
            turnovers = round(max(0.5, min(3.0, 1.25 + (sacks * 0.22) + ((dvp_rank - 16.5) * 0.03))), 1)
            def_td = round(max(0.05, min(0.35, 0.15 + ((dvp_rank - 16.5) * 0.008))), 2)
            pts_allowed = round(opp_itt, 1)

            quant_stats = ItemizedStatLine(
                sacks=sacks,
                turnovers=turnovers,
                def_td=def_td,
                pts_allowed=pts_allowed,
            )
            volume_share = 100.0

        elif pos in ("K", "PK"):
            fg_made = round(max(1.0, min(3.2, (context.implied_team_total / 12.0) * total_efficiency_adj)), 1)
            pat_made = round(max(1.0, min(4.5, context.expected_team_tds)), 1)
            quant_stats = ItemizedStatLine(
                fg_made=fg_made,
                pat_made=pat_made,
            )
            volume_share = 100.0

        # Calculate pure PPR total for the Quant Model
        calc_quant_ppr = self._calculate_ppr(quant_stats)
        quant_stats.calculated_ppr = calc_quant_ppr

        # 4. Multi-Source Calculations & Outlier-Protected Bayesian Consensus
        has_rich_stats = any(k in raw_espn_stats for k in ("rush_yds", "rec_yds", "pass_yds", "calculated_ppr", "receptions"))
        if getattr(player, "projected_points_model", 0.0) and player.projected_points_model > 0.0:
            model_pts = round(player.projected_points_model, 2)
        elif has_rich_stats and calc_quant_ppr > 0.0:
            model_pts = round(calc_quant_ppr, 2)
        elif espn_proj > 0.0:
            model_pts = round(espn_proj * total_efficiency_adj, 2)
        else:
            model_pts = round(calc_quant_ppr, 2)

        fp_pts = round(fp_r2p, 2) if fp_r2p is not None and fp_r2p > 0.0 else (round(max(4.0, 24.0 - (fp_ecr * 0.28)), 2) if fp_ecr else 0.0)
        espn_pts = round(espn_proj, 2) if espn_proj > 0.0 else 0.0
        sleeper_raw = getattr(player, "projected_points_sleeper", 0.0) or 0.0
        sleeper_pts = round(float(sleeper_raw), 2) if sleeper_raw > 0.0 else 0.0

        # Collect valid non-zero signals
        valid_signals = [p for p in (model_pts, fp_pts, sleeper_pts, espn_pts) if p > 0.0]
        if not valid_signals:
            consensus_pts = round(max(1.0, model_pts), 2)
            consensus_spread = 0.0
            consensus_agreement = "HIGH_AGREEMENT"
        elif len(valid_signals) == 1:
            consensus_pts = round(valid_signals[0], 2)
            consensus_spread = 0.0
            consensus_agreement = "HIGH_AGREEMENT"
        else:
            med = float(statistics.median(valid_signals))
            spread = max(valid_signals) - min(valid_signals)
            consensus_spread = round(spread, 2)
            if spread <= 2.2:
                consensus_agreement = "HIGH_AGREEMENT"
            elif spread <= 4.5:
                consensus_agreement = "MODERATE"
            else:
                consensus_agreement = "SHARP_DIVERGENCE"

            # Outlier protection: clamp any source > 35% away from median and compute normalized weighted sum
            source_weights: list[tuple[float, float]] = []
            if model_pts > 0:
                clamped_model = med + max(-0.35 * med, min(0.35 * med, model_pts - med))
                source_weights.append((clamped_model, self.model_weight))
            if fp_pts > 0:
                clamped_fp = med + max(-0.35 * med, min(0.35 * med, fp_pts - med))
                source_weights.append((clamped_fp, self.fantasypros_weight))
            if sleeper_pts > 0:
                clamped_sleeper = med + max(-0.35 * med, min(0.35 * med, sleeper_pts - med))
                source_weights.append((clamped_sleeper, self.sleeper_weight))
            if espn_pts > 0:
                clamped_espn = med + max(-0.35 * med, min(0.35 * med, espn_pts - med))
                source_weights.append((clamped_espn, self.espn_weight))

            total_w = sum(w for _, w in source_weights)
            if total_w > 0:
                weighted_val = sum(val * (w / total_w) for val, w in source_weights)
                consensus_pts = round(weighted_val, 2)
            else:
                consensus_pts = round(med, 2)

        # 5. Resolve Active Projection by User Selection
        source_clean = (projection_source or "MODEL").upper().strip()
        if source_clean == "FANTASYPROS" and fp_pts > 0.0:
            active_points = fp_pts
        elif source_clean == "SLEEPER" and sleeper_pts > 0.0:
            active_points = sleeper_pts
        elif source_clean == "ESPN" and espn_pts > 0.0:
            active_points = espn_pts
        elif source_clean == "CONSENSUS":
            active_points = consensus_pts
        else:
            source_clean = "MODEL"
            active_points = model_pts if model_pts > 0.0 else consensus_pts

        # 6. Scale itemized stats to match active target points
        if source_clean == "FANTASYPROS" and getattr(player, "fp_projected_stats", None):
            fp_raw = player.fp_projected_stats
            if any(fp_raw.get(k, 0) > 0 for k in ("rush_att", "rec_rec", "receptions", "pass_att", "fg", "def_sack")):
                reconciled_stats = ItemizedStatLine(
                    pass_att=fp_raw.get("pass_att", 0.0),
                    pass_cmp=fp_raw.get("pass_cmp", 0.0),
                    pass_yds=fp_raw.get("pass_yds", 0.0),
                    pass_td=fp_raw.get("pass_td", fp_raw.get("pass_tds", 0.0)),
                    pass_int=fp_raw.get("pass_int", fp_raw.get("pass_ints", 0.0)),
                    rush_att=fp_raw.get("rush_att", 0.0),
                    rush_yds=fp_raw.get("rush_yds", 0.0),
                    rush_td=fp_raw.get("rush_td", fp_raw.get("rush_tds", 0.0)),
                    targets=fp_raw.get("targets", round((fp_raw.get("receptions", fp_raw.get("rec_rec", 0.0)) / 0.72), 1) if fp_raw.get("receptions", fp_raw.get("rec_rec", 0.0)) > 0 else 0.0),
                    receptions=fp_raw.get("receptions", fp_raw.get("rec_rec", 0.0)),
                    rec_yds=fp_raw.get("rec_yds", 0.0),
                    rec_td=fp_raw.get("rec_td", fp_raw.get("rec_tds", 0.0)),
                    fg_made=fp_raw.get("fg", fp_raw.get("fg_made", 0.0)),
                    pat_made=fp_raw.get("xpt", fp_raw.get("pat_made", 0.0)),
                    sacks=fp_raw.get("def_sack", fp_raw.get("sacks", 0.0)),
                    turnovers=fp_raw.get("turnovers", (fp_raw.get("def_int", 0.0) + fp_raw.get("def_fr", 0.0))),
                    def_td=fp_raw.get("def_td", 0.0),
                    pts_allowed=fp_raw.get("def_pa", fp_raw.get("pts_allowed", 21.0)),
                    calculated_ppr=active_points,
                )
            else:
                reconciled_stats = self._reconcile_itemized_to_points(quant_stats, active_points, pos)
        elif source_clean == "SLEEPER" and getattr(player, "sleeper_projected_stats", None):
            sl_raw = player.sleeper_projected_stats
            if any(sl_raw.get(k, 0) > 0 for k in ("rush_att", "rec_rec", "receptions", "rec", "pass_att", "fg", "fgm", "def_sack", "sack")):
                reconciled_stats = ItemizedStatLine(
                    pass_att=sl_raw.get("pass_att", 0.0),
                    pass_cmp=sl_raw.get("pass_cmp", 0.0),
                    pass_yds=sl_raw.get("pass_yds", sl_raw.get("pass_yd", 0.0)),
                    pass_td=sl_raw.get("pass_td", sl_raw.get("pass_tds", 0.0)),
                    pass_int=sl_raw.get("pass_int", sl_raw.get("pass_ints", 0.0)),
                    rush_att=sl_raw.get("rush_att", 0.0),
                    rush_yds=sl_raw.get("rush_yds", sl_raw.get("rush_yd", 0.0)),
                    rush_td=sl_raw.get("rush_td", sl_raw.get("rush_tds", 0.0)),
                    targets=sl_raw.get("targets", sl_raw.get("rec_tgt", 0.0)),
                    receptions=sl_raw.get("receptions", sl_raw.get("rec", 0.0)),
                    rec_yds=sl_raw.get("rec_yds", sl_raw.get("rec_yd", 0.0)),
                    rec_td=sl_raw.get("rec_td", sl_raw.get("rec_tds", 0.0)),
                    fg_made=sl_raw.get("fg_made", sl_raw.get("fgm", 0.0)),
                    pat_made=sl_raw.get("pat_made", sl_raw.get("xpm", 0.0)),
                    sacks=sl_raw.get("sacks", sl_raw.get("def_sack", sl_raw.get("sack", 0.0))),
                    turnovers=sl_raw.get("turnovers", (sl_raw.get("def_int", 0.0) + sl_raw.get("def_fr", 0.0))),
                    def_td=sl_raw.get("def_td", 0.0),
                    pts_allowed=sl_raw.get("pts_allowed", sl_raw.get("def_pa", 21.0)),
                    calculated_ppr=active_points,
                )
            else:
                reconciled_stats = self._reconcile_itemized_to_points(quant_stats, active_points, pos)
        else:
            reconciled_stats = self._reconcile_itemized_to_points(quant_stats, active_points, pos)

        # 7. Probabilistic Floor & Ceiling
        std_est = getattr(player, "fp_rank_std", 1.2) or 1.2
        volatility_factor = max(0.18, min(0.42, 0.22 + (std_est * 0.05)))
        floor_pts = round(max(0.0, active_points * (1.0 - (volatility_factor * 1.5))), 1)
        ceiling_pts = round(active_points * (1.0 + (volatility_factor * 2.0)), 1)

        # Provenance audit package
        provenance = {
            "team": player.pro_team,
            "opponent": context.opponent,
            "implied_total": context.implied_team_total,
            "spread": context.spread,
            "expected_plays": context.expected_plays,
            "pass_ratio_pct": round(context.pass_ratio * 100.0, 1),
            "expected_pass_att": context.expected_pass_attempts,
            "expected_rush_att": context.expected_rush_attempts,
            "volume_share_pct": volume_share,
            "dvp_rank": dvp_rank,
            "def_rank": unit_rank,
            "off_rank": unit_rank if pos in ("D/ST", "DST") else None,
            "efficiency_multiplier_pct": round(efficiency_mult * 100.0, 1),
            "raw_model_ppr": model_pts,
            "fantasypros_ppr": fp_pts if fp_pts > 0 else None,
            "sleeper_ppr": sleeper_pts if sleeper_pts > 0 else None,
            "espn_ppr": espn_pts if espn_pts > 0 else None,
            "consensus_ppr": consensus_pts,
            "active_projection_source": source_clean,
            "active_projected_points": active_points,
            "consensus_spread": consensus_spread,
            "consensus_agreement": consensus_agreement,
            "sources": {
                "quant_model": model_pts,
                "fantasypros": fp_pts if fp_pts > 0 else None,
                "sleeper": sleeper_pts if sleeper_pts > 0 else None,
                "espn": espn_pts if espn_pts > 0 else None,
                "consensus": consensus_pts,
                "active_source": source_clean,
                "active_points": active_points,
                "consensus_spread": consensus_spread,
                "consensus_agreement": consensus_agreement,
            },
        }

        return PlayerProjectionResult(
            projected_points=active_points,
            model_points=model_pts,
            fp_points=fp_pts,
            sleeper_points=sleeper_pts,
            espn_points=espn_pts,
            consensus_points=consensus_pts,
            active_points=active_points,
            active_source=source_clean,
            consensus_spread=consensus_spread,
            consensus_agreement=consensus_agreement,
            itemized_stats=reconciled_stats,
            volume_share=volume_share,
            team_projected_plays=context.expected_plays,
            team_pass_att=context.expected_pass_attempts,
            team_rush_att=context.expected_rush_attempts,
            efficiency_multiplier=round(efficiency_mult * 100.0, 1),
            model_provenance=provenance,
            floor_points=floor_pts,
            median_points=active_points,
            ceiling_points=ceiling_pts,
        )

    def _calculate_ppr(self, s: ItemizedStatLine) -> float:
        """Full PPR calculation formula."""
        return round(
            (s.pass_yds * 0.04) + (s.pass_td * 4.0) - (s.pass_int * 2.0)
            + (s.rush_yds * 0.1) + (s.rush_td * 6.0)
            + (s.receptions * 1.0) + (s.rec_yds * 0.1) + (s.rec_td * 6.0)
            + (s.fg_made * 3.0) + (s.pat_made * 1.0)
            + (s.sacks * 1.0) + (s.turnovers * 2.0) + (s.def_td * 6.0),
            2,
        )

    def _reconcile_itemized_to_points(
        self,
        base_stats: ItemizedStatLine,
        target_points: float,
        pos: str,
    ) -> ItemizedStatLine:
        """Scale itemized yards, receptions, and touches so calculated PPR strictly equals target_points."""
        current_calc = self._calculate_ppr(base_stats)
        if current_calc <= 0.0 or target_points <= 0.0:
            base_stats.calculated_ppr = target_points
            return base_stats

        scale_ratio = target_points / current_calc
        scale_ratio = max(0.65, min(1.45, scale_ratio))

        scaled = ItemizedStatLine(
            pass_att=base_stats.pass_att,
            pass_cmp=base_stats.pass_cmp,
            pass_yds=round(base_stats.pass_yds * scale_ratio, 1),
            pass_td=round(base_stats.pass_td * scale_ratio, 2),
            pass_int=base_stats.pass_int,
            rush_att=base_stats.rush_att,
            rush_yds=round(base_stats.rush_yds * scale_ratio, 1),
            rush_td=round(base_stats.rush_td * scale_ratio, 2),
            targets=base_stats.targets,
            receptions=round(base_stats.receptions * scale_ratio, 1),
            rec_yds=round(base_stats.rec_yds * scale_ratio, 1),
            rec_td=round(base_stats.rec_td * scale_ratio, 2),
            fg_made=round(base_stats.fg_made * scale_ratio, 1),
            pat_made=round(base_stats.pat_made * scale_ratio, 1),
            sacks=base_stats.sacks,
            turnovers=base_stats.turnovers,
            def_td=base_stats.def_td,
            pts_allowed=base_stats.pts_allowed,
            calculated_ppr=round(target_points, 2),
        )
        return scaled


quant_projection_engine = QuantProjectionEngine()
