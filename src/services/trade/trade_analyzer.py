"""Consolidation Trade Analyzer (2-for-1 & 3-for-1) for 8-Man Leagues.

In 8-team leagues, roster depth has negligible value while elite Tier-1 Alphas
decide championships. This analyzer scans opponent rosters to identify high-leverage
2-for-1 consolidation trades that net positive weekly starting points after
backfilling the open roster spot from the talent-rich waiver wire.
"""

import logging
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PlayerModel, RosterEntryModel, TeamModel
from src.services.recommendation.scoring_engine import (
    StartSitEvaluation,
    scoring_engine,
)

logger = logging.getLogger(__name__)


class TradePlayerSummary(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    projected_points: float
    start_score: float
    is_starter: bool = False
    playoff_sos_score: float = 70.0
    playoff_sos_grade: str = "NEUTRAL"


class ConsolidationTradeRecommendation(BaseModel):
    trade_id: str
    partner_team_id: int
    partner_team_name: str
    target_alpha: TradePlayerSummary
    send_players: list[TradePlayerSummary]
    waiver_backfill: TradePlayerSummary | None = None
    user_net_projected_delta: float
    user_net_start_score_delta: float
    partner_net_projected_delta: float
    feasibility: str  # "HIGH", "MEDIUM", "SPECULATIVE"
    rationale: str
    pitch_message: str
    target_playoff_sos: float = 70.0
    target_playoff_grade: str = "NEUTRAL"
    user_playoff_leverage_delta: float = 0.0
    is_championship_target: bool = False


class ConsolidationTradeAnalysisResult(BaseModel):
    user_team_id: int
    total_trades_analyzed: int
    recommendations: list[ConsolidationTradeRecommendation]


class TradeAnalyzer:
    """Discovers and models high-leverage 2-for-1 consolidation trades."""

    def analyze_consolidation_trades(
        self,
        db: Session,
        league_id: int,
        user_team_id: int,
        user_roster_evaluations: list[StartSitEvaluation],
        free_agent_pool: list[PlayerModel] | None = None,
        league_size: int = 8,
    ) -> ConsolidationTradeAnalysisResult:
        # 1. Fetch user roster entries to know who is starting vs bench
        user_entries = db.execute(
            select(RosterEntryModel).where(
                RosterEntryModel.league_id == league_id,
                RosterEntryModel.team_id == user_team_id,
            )
        ).scalars().all()
        user_starter_pids = {e.player_id for e in user_entries if e.is_starter}

        user_eval_by_id = {e.player_id: e for e in user_roster_evaluations}

        # 2. Get top waiver wire talent by position to model the backfill
        all_rostered_pids = set(
            db.execute(
                select(RosterEntryModel.player_id).where(RosterEntryModel.league_id == league_id)
            ).scalars().all()
        )

        if free_agent_pool is None:
            free_agent_pool = db.execute(
                select(PlayerModel).where(PlayerModel.id.not_in(all_rostered_pids))
            ).scalars().all()

        unowned_players = [p for p in free_agent_pool if p.id not in all_rostered_pids]
        fa_evals: list[StartSitEvaluation] = [
            scoring_engine.evaluate_player(p, league_size=league_size)
            for p in unowned_players
        ]

        # Top waiver replacement by position
        top_fa_by_pos: dict[str, StartSitEvaluation] = {}
        for pos in ("QB", "RB", "WR", "TE"):
            matching_fa = [f for f in fa_evals if f.position.upper() == pos]
            if matching_fa:
                top_fa_by_pos[pos] = max(matching_fa, key=lambda x: x.start_score)

        # Fallback generic replacement
        fallback_fa = StartSitEvaluation(
            player_id=99999,
            full_name="Top Free Agent Replacement",
            position="FLEX",
            pro_team="FA",
            projected_points=12.5,
            start_score=68.0,
            confidence="MEDIUM",
            recommendation="START",
            matchup_grade="NEUTRAL",
            opponent="VARIES",
            is_home=True,
            implied_team_total=21.0,
            injury_status="ACTIVE",
        )

        # 3. Fetch opponent teams
        rival_teams = db.execute(
            select(TeamModel).where(
                TeamModel.league_id == league_id,
                TeamModel.id != user_team_id,
            )
        ).scalars().all()

        recommendations: list[ConsolidationTradeRecommendation] = []
        total_scanned = 0

        # Tier-1 Alpha thresholds
        min_alpha_score = 80.0 if league_size <= 8 else 78.0

        for rival in rival_teams:
            rival_entries = db.execute(
                select(RosterEntryModel).where(
                    RosterEntryModel.league_id == league_id,
                    RosterEntryModel.team_id == rival.id,
                )
            ).scalars().all()

            rival_pids = [e.player_id for e in rival_entries]
            if not rival_pids:
                continue

            rival_players = db.execute(
                select(PlayerModel).where(PlayerModel.id.in_(rival_pids))
            ).scalars().all()

            rival_entry_map = {e.player_id: e for e in rival_entries}
            rival_evals = [
                scoring_engine.evaluate_player(p, league_size=league_size)
                for p in rival_players
            ]

            # Identify rival's Tier-1 Alphas (the targets we want to acquire)
            alpha_targets = [
                ev for ev in rival_evals
                if (
                    ev.start_score >= min_alpha_score
                    or ev.projected_points >= 18.0
                    or (ev.position.upper() == "TE" and ev.projected_points >= 13.5)
                    or (ev.position.upper() == "QB" and ev.projected_points >= 22.0)
                )
                and ev.position.upper() in ("QB", "RB", "WR", "TE")
            ]

            # Identify rival's weaknesses (starting slots with lowest scores)
            rival_starters = [
                ev for ev in rival_evals
                if rival_entry_map.get(ev.player_id) and rival_entry_map[ev.player_id].is_starter
            ]

            for alpha in alpha_targets:
                alpha_pos = alpha.position.upper()

                # Search user roster for viable 2-for-1 packages:
                user_candidates = [
                    ev for ev in user_roster_evaluations
                    if ev.player_id != alpha.player_id
                    and ev.position.upper() in ("QB", "RB", "WR", "TE")
                    and (ev.start_score >= 60.0 or ev.projected_points >= 13.0)
                ]

                # We consider pairing one higher-scoring user player (Player 1) with another (Player 2)
                for i in range(len(user_candidates)):
                    for j in range(i + 1, len(user_candidates)):
                        p1 = user_candidates[i]
                        p2 = user_candidates[j]
                        total_scanned += 1

                        # Avoid offering two low-end players for an elite alpha
                        combined_start_score = p1.start_score + p2.start_score
                        if combined_start_score < (alpha.start_score * 1.65):
                            continue

                        # Ensure at least one sent player is near the top tier
                        if max(p1.start_score, p2.start_score) < 74.0:
                            continue

                        # Alpha should be superior to both individual players sent
                        if alpha.start_score <= max(p1.start_score, p2.start_score) + 1.5:
                            continue

                        # User perspective:
                        p1_is_starter = p1.player_id in user_starter_pids
                        p2_is_starter = p2.player_id in user_starter_pids

                        # Vacated roster spot backfilled by best free agent
                        vacated_pos = p2.position.upper() if p2_is_starter else p1.position.upper()
                        backfill = top_fa_by_pos.get(vacated_pos, fallback_fa)

                        if p1_is_starter and p2_is_starter:
                            # User lost 2 starters, gains Alpha + Waiver Backfill
                            user_net_pts = (alpha.projected_points + backfill.projected_points) - (p1.projected_points + p2.projected_points)
                            user_net_score = (alpha.start_score + backfill.start_score) - (p1.start_score + p2.start_score)
                        elif p1_is_starter or p2_is_starter:
                            # User lost 1 starter and 1 bench player, gains Alpha
                            lost_starter = p1 if p1_is_starter else p2
                            user_net_pts = alpha.projected_points - lost_starter.projected_points
                            user_net_score = alpha.start_score - lost_starter.start_score
                        else:
                            # Both were bench players (rare, but pure profit if Alpha upgrades a starter)
                            user_net_pts = alpha.projected_points - min(p1.projected_points, p2.projected_points)
                            user_net_score = alpha.start_score - min(p1.start_score, p2.start_score)

                        # We only want trades that meaningfully upgrade our starting roster
                        if user_net_pts <= 0.5:
                            continue

                        # Partner perspective:
                        # Partner loses Alpha.
                        # Partner gains P1 (to replace Alpha) and P2 (to replace their weakest starter)
                        matching_rival_weak = [
                            s for s in rival_starters
                            if s.position.upper() == p2.position.upper()
                            and s.player_id != alpha.player_id
                        ]
                        weakest_partner_starter = min(matching_rival_weak, key=lambda x: x.start_score) if matching_rival_weak else None

                        if weakest_partner_starter:
                            partner_net_pts = (p1.projected_points - alpha.projected_points) + (p2.projected_points - weakest_partner_starter.projected_points)
                            partner_weak_desc = f"upgrades their {weakest_partner_starter.position} slot ({weakest_partner_starter.full_name}, {weakest_partner_starter.projected_points:.1f} pts)"
                        else:
                            partner_net_pts = (p1.projected_points + p2.projected_points) - (alpha.projected_points + 11.0)
                            partner_weak_desc = "adds crucial starting depth"

                        # Feasibility rating
                        if partner_net_pts >= 1.0:
                            feasibility = "HIGH"
                        elif partner_net_pts >= -2.0:
                            feasibility = "MEDIUM"
                        else:
                            feasibility = "SPECULATIVE"

                        # Pitch message for league chat
                        pitch = (
                            f"Hey {rival.name}, proposing a 2-for-1: I'll send {p1.full_name} and {p2.full_name} "
                            f"for {alpha.full_name}. This immediately {partner_weak_desc} and gives you two reliable starters."
                        )

                        trade_id = f"{user_team_id}_{rival.id}_{alpha.player_id}_{p1.player_id}_{p2.player_id}"

                        alpha_playoff_score = getattr(alpha, "playoff_sos_score", 70.0)
                        alpha_playoff_grade = getattr(alpha, "playoff_sos_grade", "NEUTRAL")
                        p1_playoff = getattr(p1, "playoff_sos_score", 70.0)
                        p2_playoff = getattr(p2, "playoff_sos_score", 70.0)
                        send_avg_playoff = (p1_playoff + p2_playoff) / 2.0
                        playoff_leverage_delta = round(alpha_playoff_score - send_avg_playoff, 1)
                        is_championship_target = (alpha_playoff_score >= 76.0) or (playoff_leverage_delta >= 5.0)

                        playoff_note = (
                            f" Playoff Championship Leverage: {alpha.full_name} has an {alpha_playoff_grade} Weeks 15-17 schedule "
                            f"({alpha_playoff_score:.1f} SoS, {playoff_leverage_delta:+.1f} leverage vs outgoing starters)."
                        )

                        recommendations.append(
                            ConsolidationTradeRecommendation(
                                trade_id=trade_id,
                                partner_team_id=rival.id,
                                partner_team_name=rival.name,
                                target_alpha=TradePlayerSummary(
                                    player_id=alpha.player_id,
                                    full_name=alpha.full_name,
                                    position=alpha.position,
                                    pro_team=alpha.pro_team,
                                    projected_points=alpha.projected_points,
                                    start_score=alpha.start_score,
                                    is_starter=True,
                                    playoff_sos_score=alpha_playoff_score,
                                    playoff_sos_grade=alpha_playoff_grade,
                                ),
                                send_players=[
                                    TradePlayerSummary(
                                        player_id=p1.player_id,
                                        full_name=p1.full_name,
                                        position=p1.position,
                                        pro_team=p1.pro_team,
                                        projected_points=p1.projected_points,
                                        start_score=p1.start_score,
                                        is_starter=p1_is_starter,
                                        playoff_sos_score=p1_playoff,
                                        playoff_sos_grade=getattr(p1, "playoff_sos_grade", "NEUTRAL"),
                                    ),
                                    TradePlayerSummary(
                                        player_id=p2.player_id,
                                        full_name=p2.full_name,
                                        position=p2.position,
                                        pro_team=p2.pro_team,
                                        projected_points=p2.projected_points,
                                        start_score=p2.start_score,
                                        is_starter=p2_is_starter,
                                        playoff_sos_score=p2_playoff,
                                        playoff_sos_grade=getattr(p2, "playoff_sos_grade", "NEUTRAL"),
                                    ),
                                ],
                                waiver_backfill=TradePlayerSummary(
                                    player_id=backfill.player_id,
                                    full_name=backfill.full_name,
                                    position=backfill.position,
                                    pro_team=backfill.pro_team,
                                    projected_points=backfill.projected_points,
                                    start_score=backfill.start_score,
                                    is_starter=False,
                                    playoff_sos_score=getattr(backfill, "playoff_sos_score", 70.0),
                                    playoff_sos_grade=getattr(backfill, "playoff_sos_grade", "NEUTRAL"),
                                ),
                                user_net_projected_delta=round(user_net_pts, 1),
                                user_net_start_score_delta=round(user_net_score, 1),
                                partner_net_projected_delta=round(partner_net_pts, 1),
                                feasibility=feasibility,
                                rationale=(
                                    f"Consolidates depth into Tier-1 Alpha {alpha.full_name} (+{user_net_pts:.1f} net starting pts). "
                                    f"In an 8-man league, starting studs outperform bench depth. Open roster spot backfilled by {backfill.full_name} ({backfill.projected_points:.1f} pts)."
                                    f"{playoff_note}"
                                ),
                                pitch_message=pitch,
                                target_playoff_sos=alpha_playoff_score,
                                target_playoff_grade=alpha_playoff_grade,
                                user_playoff_leverage_delta=playoff_leverage_delta,
                                is_championship_target=is_championship_target,
                            )
                        )

        # Sort recommendations by net user projected delta and feasibility
        feasibility_order = {"HIGH": 0, "MEDIUM": 1, "SPECULATIVE": 2}
        recommendations.sort(
            key=lambda x: (feasibility_order.get(x.feasibility, 3), -x.user_net_projected_delta)
        )

        return ConsolidationTradeAnalysisResult(
            user_team_id=user_team_id,
            total_trades_analyzed=total_scanned,
            recommendations=recommendations[:8],
        )


trade_analyzer = TradeAnalyzer()
