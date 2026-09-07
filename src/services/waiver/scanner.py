"""Waiver Wire Upgrade Analyzer with league ownership filtering and core drop protection."""

import logging
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.nfl.dvp_client import dvp_client
from src.db.models import PlayerModel, RosterEntryModel, TeamModel
from src.services.recommendation.scoring_engine import (
    StartSitEvaluation,
    scoring_engine,
)

logger = logging.getLogger(__name__)


class WaiverUpgradeRecommendation(BaseModel):
    pickup_player: StartSitEvaluation
    drop_player: StartSitEvaluation | None
    upgrade_type: str  # "STARTING_LINEUP_UPGRADE", "BENCH_STASH", "STREAMER"
    replaces_slot: str | None
    net_projected_delta: float
    net_start_score_delta: float
    rationale: str


class LookaheadStreamerItem(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    next_week: int
    next_opponent: str
    matchup_grade: str
    matchup_score: float
    tactical_reason: str


class DeadweightBenchItem(BaseModel):
    player_id: int
    full_name: str
    position: str
    projected_points: float
    start_score: float
    ceiling_score: float
    diagnosis: str
    suggested_action: str


class RosterArchitectureAudit(BaseModel):
    grade: str
    score: float
    handcuff_rb_count: int
    wasted_bench_slots: list[str] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)
    tactical_prescriptions: list[str] = Field(default_factory=list)


class WaiverAnalysisResult(BaseModel):
    user_team_id: int
    total_available_scanned: int
    top_upgrades: list[WaiverUpgradeRecommendation]
    streaming_te: list[StartSitEvaluation]
    streaming_dst: list[StartSitEvaluation]
    streaming_k: list[StartSitEvaluation]
    architecture_audit: RosterArchitectureAudit | None = None
    lookahead_streaming_dst: list[LookaheadStreamerItem] = Field(default_factory=list)
    lookahead_streaming_k: list[LookaheadStreamerItem] = Field(default_factory=list)
    deadweight_drops: list[DeadweightBenchItem] = Field(default_factory=list)


class WaiverScanner:
    """Scans available unowned players and recommends high-value upgrades and streamers."""

    def scan_upgrades(
        self,
        db: Session,
        league_id: int,
        user_team_id: int,
        user_roster_evaluations: list[StartSitEvaluation],
        free_agent_pool: list[PlayerModel] | None = None,
        games_by_team: dict[str, Any] | None = None,
        injuries_by_athlete: dict[int, Any] | None = None,
        weather_by_team: dict[str, Any] | None = None,
        league_size: int = 8,
        current_week: int = 1,
        next_week_games: list[Any] | None = None,
    ) -> WaiverAnalysisResult:
        # 1. Identify all rostered player IDs across the entire league
        all_rostered_player_ids = set(
            db.execute(
                select(RosterEntryModel.player_id).where(RosterEntryModel.league_id == league_id)
            ).scalars().all()
        )

        # 2. Get unowned player pool
        if free_agent_pool is None:
            # Query players in DB that are NOT rostered
            free_agent_pool = db.execute(
                select(PlayerModel).where(PlayerModel.id.not_in(all_rostered_player_ids))
            ).scalars().all()

        # Filter strictly for unowned players
        available_players = [p for p in free_agent_pool if p.id not in all_rostered_player_ids]

        games_map = games_by_team or {}
        injuries_map = injuries_by_athlete or {}
        weather_map = weather_by_team or {}

        # Evaluate available players with scoring engine using live context
        available_evals: list[StartSitEvaluation] = []
        for p in available_players:
            game = games_map.get(p.pro_team)
            weather = weather_map.get(p.pro_team)
            injury = injuries_map.get(p.id)
            ev = scoring_engine.evaluate_player(
                p,
                nfl_game=game,
                injury_report=injury,
                weather=weather,
                league_size=league_size,
            )
            available_evals.append(ev)

        # Sort available players by StartScore descending
        available_evals.sort(key=lambda x: x.start_score, reverse=True)

        # 3. Identify Drop Candidates on User's Roster (Drop Protection logic)
        user_eval_by_id = {e.player_id: e for e in user_roster_evaluations}
        user_roster_entries = db.execute(
            select(RosterEntryModel).where(
                RosterEntryModel.league_id == league_id,
                RosterEntryModel.team_id == user_team_id,
            )
        ).scalars().all()

        bench_pids = {e.player_id for e in user_roster_entries if not e.is_starter}
        bench_evals = [user_eval_by_id[pid] for pid in bench_pids if pid in user_eval_by_id]

        # Calibrated drop protection thresholds based on league size
        if league_size <= 8:
            min_proj = 15.5
            min_score = 78.0
        elif league_size == 10:
            min_proj = 14.2
            min_score = 75.0
        else:
            min_proj = 13.0
            min_score = 72.0

        def is_protected_bench_asset(b: StartSitEvaluation) -> bool:
            """Ensure studs on BYE, IR, or with elite consensus ECR are completely immune from waiver drops."""
            if b.projected_points >= min_proj or b.start_score >= min_score:
                return True
            # Rest-of-season / ECR consensus immunity: Top-75 overall or Tier 1-4
            b_ecr = getattr(b, "fp_rank_ecr", getattr(b, "fp_ecr", None))
            if b_ecr is not None and b_ecr <= 75:
                return True
            b_c_rank = getattr(b, "consensus_rank", None)
            if b_c_rank is not None and b_c_rank <= 75:
                return True
            b_tier = getattr(b, "fp_tier", None)
            if b_tier is not None and b_tier <= 4:
                return True
            # Positional rank immunity: RB <= 24, WR <= 28, QB <= 10, TE <= 8
            pos_str = b.position.upper()
            pos_rank_num = None
            pos_rank_str = getattr(b, "fp_pos_rank", None)
            if pos_rank_str:
                import re
                m = re.search(r'\d+', str(pos_rank_str))
                if m:
                    pos_rank_num = int(m.group())
            if pos_str in ("RB", "FB") and pos_rank_num is not None and pos_rank_num <= 24:
                return True
            if pos_str == "WR" and pos_rank_num is not None and pos_rank_num <= 28:
                return True
            if pos_str == "QB" and pos_rank_num is not None and pos_rank_num <= 10:
                return True
            if pos_str == "TE" and pos_rank_num is not None and pos_rank_num <= 8:
                return True
            # Bye-week immunity for core players (they have 0 projected points this week, but high ROS value)
            if b.opponent == "BYE" and ((b_ecr and b_ecr <= 85) or (b_c_rank and b_c_rank <= 85)):
                return True
            return False

        def drop_sort_key(b: StartSitEvaluation) -> tuple[int, int, float]:
            # Priority 0: Unprotected expendables (backup K/DST, mediocre backup QB/TE)
            # Priority 1: Other unprotected bench players
            # Priority 2: Protected assets (shielded from drops)
            is_prot = 1 if is_protected_bench_asset(b) else 0
            is_expendable = 0 if (league_size <= 8 and b.position.upper() in ("QB", "TE", "K", "D/ST") and b.start_score < 75.0 and not is_prot) else 1
            return (is_prot, is_expendable, b.start_score)

        bench_evals.sort(key=drop_sort_key)

        # Protected Core filter: Players flagged as protected cannot be dropped
        eligible_drop_candidates = [
            b for b in bench_evals if not is_protected_bench_asset(b)
        ]
        if not eligible_drop_candidates and bench_evals:
            # Fallback to the absolute lowest player on the bench only if no candidate found
            eligible_drop_candidates = [bench_evals[0]]

        # 4. Generate Upgrade Recommendations
        upgrades: list[WaiverUpgradeRecommendation] = []
        starter_evals = [user_eval_by_id[e.player_id] for e in user_roster_entries if e.is_starter and e.player_id in user_eval_by_id]

        # Identify rostered Kickers and D/STs across user's entire team (starters + bench)
        rostered_k = [e for e in user_roster_evaluations if e.position.upper() in ("K", "PK")]
        rostered_dst = [e for e in user_roster_evaluations if e.position.upper() in ("D/ST", "DST")]

        for fa in available_evals[:15]:
            fa_pos = fa.position.upper()

            # Positional eligibility mapping:
            # - RB/FB/WR/TE: can replace matching position or flex starters
            # - QB: strictly QB
            # - K: strictly K (can never replace an offensive player)
            # - D/ST: strictly D/ST (can never replace an offensive player)
            if fa_pos in ("RB", "FB", "WR", "TE"):
                matching_starters = [
                    s for s in starter_evals
                    if s.position.upper() in ("RB", "FB", "WR", "TE")
                ]
            elif fa_pos == "QB":
                matching_starters = [
                    s for s in starter_evals
                    if s.position.upper() == "QB"
                ]
            elif fa_pos in ("K", "PK"):
                matching_starters = [
                    s for s in starter_evals
                    if s.position.upper() in ("K", "PK")
                ]
            elif fa_pos in ("D/ST", "DST"):
                matching_starters = [
                    s for s in starter_evals
                    if s.position.upper() in ("D/ST", "DST")
                ]
            else:
                matching_starters = [
                    s for s in starter_evals
                    if s.position.upper() == fa_pos
                ]

            matching_starters.sort(key=lambda x: x.start_score)

            if matching_starters and fa.start_score > matching_starters[0].start_score:
                weakest_starter = matching_starters[0]

                # Drop candidate determination:
                # If upgrading K or D/ST, drop the current rostered K or D/ST to avoid carrying duplicates
                if fa_pos in ("K", "PK") and rostered_k:
                    drop_candidate = min(rostered_k, key=lambda x: x.start_score)
                elif fa_pos in ("D/ST", "DST") and rostered_dst:
                    drop_candidate = min(rostered_dst, key=lambda x: x.start_score)
                else:
                    drop_candidate = eligible_drop_candidates[0] if eligible_drop_candidates else None

                net_pts = round(fa.projected_points - weakest_starter.projected_points, 1)
                net_score = round(fa.start_score - weakest_starter.start_score, 1)

                upgrades.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="STARTING_LINEUP_UPGRADE",
                        replaces_slot=weakest_starter.position,
                        net_projected_delta=net_pts,
                        net_start_score_delta=net_score,
                        rationale=(
                            f"Direct starting lineup upgrade (+{net_score} StartScore, +{net_pts} projected pts). "
                            f"Outscores current starter {weakest_starter.full_name}."
                        ),
                    )
                )
            elif not matching_starters and fa_pos in ("K", "PK", "D/ST", "DST") and eligible_drop_candidates:
                # User has an empty K or D/ST starting slot: dropping lowest bench player to field a starter
                drop_candidate = eligible_drop_candidates[0]
                upgrades.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="STARTING_LINEUP_UPGRADE",
                        replaces_slot="K" if fa_pos in ("K", "PK") else "D/ST",
                        net_projected_delta=round(fa.projected_points, 1),
                        net_start_score_delta=round(fa.start_score, 1),
                        rationale=(
                            f"Fill empty {fa_pos} starting slot (+{fa.projected_points:.1f} projected pts) "
                            f"by dropping lowest-impact bench stash {drop_candidate.full_name}."
                        ),
                    )
                )
            elif fa_pos in ("RB", "FB") and getattr(fa, "contingency_score", 0.0) >= 75.0 and eligible_drop_candidates:
                drop_candidate = eligible_drop_candidates[0]
                if drop_candidate.player_id != fa.player_id:
                    net_score = round(fa.contingency_score - drop_candidate.start_score, 1)
                    upgrades.append(
                        WaiverUpgradeRecommendation(
                            pickup_player=fa,
                            drop_player=drop_candidate,
                            upgrade_type="CONTINGENT_UPSIDE_STASH",
                            replaces_slot="BENCH",
                            net_projected_delta=round(fa.projected_points - drop_candidate.projected_points, 1),
                            net_start_score_delta=net_score,
                            rationale=(
                                f"Elite contingent upside stash ({fa.contingency_score:.1f} contingent StartScore). "
                                f"In an 8-team league, backup RBs with workhorse upside upon injury "
                                f"provide far higher championship equity than {drop_candidate.full_name}."
                            ),
                        )
                    )
            elif fa_pos not in ("K", "PK", "D/ST", "DST") and eligible_drop_candidates and fa.start_score > eligible_drop_candidates[0].start_score + 4.0:
                # BENCH_STASH: Only valid for offensive skill players (RB, WR, TE) and QB.
                # In 8-team leagues, stashing backup Kickers or D/STs on the bench is strictly avoided.
                drop_candidate = eligible_drop_candidates[0]
                net_score = round(fa.start_score - drop_candidate.start_score, 1)
                upgrades.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="BENCH_STASH",
                        replaces_slot="BENCH",
                        net_projected_delta=round(fa.projected_points - drop_candidate.projected_points, 1),
                        net_start_score_delta=net_score,
                        rationale=(
                            f"Bench depth upgrade (+{net_score} StartScore). "
                            f"Superior role and floor compared to {drop_candidate.full_name}."
                        ),
                    )
                )

        # 5. Extract Streaming Options
        streaming_te = [p for p in available_evals if p.position.upper() == "TE"][:3]
        streaming_dst = [p for p in available_evals if p.position.upper() == "D/ST"][:3]
        streaming_k = [p for p in available_evals if p.position.upper() == "K"][:3]

        # 6. Dynamic Live-Wire VORP Calculation
        # For each position, find the highest projected unowned free agent
        top_wire_proj_map: dict[str, float] = {}
        for pos in ("QB", "RB", "WR", "TE", "K", "D/ST"):
            matching_fa = [p for p in available_evals if p.position.upper() == pos]
            if matching_fa:
                top_wire_proj_map[pos] = max(p.projected_points for p in matching_fa)
            else:
                top_wire_proj_map[pos] = 12.0

        for p in user_roster_evaluations:
            wire_baseline = top_wire_proj_map.get(p.position.upper(), 12.0)
            p.live_vorp = round(p.projected_points - wire_baseline, 1)

        # 7. 8-Man Roster Architecture & Bench Optimization Audit
        wasted_slots: list[str] = []
        strengths: list[str] = []
        prescriptions: list[str] = []
        audit_score = 85.0

        bench_k = [b for b in bench_evals if b.position.upper() in ("K", "PK")]
        if bench_k:
            audit_score -= 15.0
            wasted_slots.append(f"Backup Kicker ({bench_k[0].full_name})")
            prescriptions.append("Drop backup kicker. In an 8-team league, carrying 2 kickers burns an elite lottery ticket slot.")

        bench_dst = [b for b in bench_evals if b.position.upper() in ("D/ST", "DST")]
        if bench_dst:
            audit_score -= 15.0
            wasted_slots.append(f"Backup D/ST ({bench_dst[0].full_name})")
            prescriptions.append("Drop backup D/ST. Stream elite matchups weekly rather than holding two defenses on an 8-man bench.")

        starter_qbs = [s for s in starter_evals if s.position.upper() == "QB"]
        bench_qb = [b for b in bench_evals if b.position.upper() == "QB"]
        if bench_qb and starter_qbs and starter_qbs[0].start_score >= 80.0:
            audit_score -= 10.0
            wasted_slots.append(f"Redundant backup QB ({bench_qb[0].full_name})")
            prescriptions.append(f"Your starter {starter_qbs[0].full_name} is an elite anchor. Drop {bench_qb[0].full_name} for a high-contingency RB.")

        starter_tes = [s for s in starter_evals if s.position.upper() == "TE"]
        bench_te = [b for b in bench_evals if b.position.upper() == "TE"]
        if bench_te and starter_tes and starter_tes[0].start_score >= 76.0 and bench_te[0].start_score < 70.0:
            audit_score -= 10.0
            wasted_slots.append(f"Low-ceiling backup TE ({bench_te[0].full_name})")
            prescriptions.append(f"Drop low-ceiling backup TE {bench_te[0].full_name}. Stream matchups instead of holding mediocre TEs.")

        handcuff_rbs = [
            b for b in bench_evals
            if b.position.upper() in ("RB", "FB")
            and (getattr(b, "contingency_score", 0.0) >= 65.0 or b.projected_points < 13.5)
        ]
        handcuff_count = len(handcuff_rbs)

        if handcuff_count >= 3:
            audit_score += 15.0
            strengths.append(f"Elite RB lottery ticket profile: {handcuff_count} high-contingency RBs stashed for championship leverage.")
        elif handcuff_count == 2:
            audit_score += 8.0
            strengths.append("Solid contingent RB stash depth (2 lottery tickets).")
        elif handcuff_count == 0 and len(bench_evals) > 0:
            audit_score -= 20.0
            prescriptions.append("Zero backup running backs stashed. In 8-man PPR, stash 2-3 elite handcuffs who inherit 18+ touches upon injury.")

        if not wasted_slots and audit_score >= 85.0:
            strengths.append("Zero wasted bench slots: Pure lean championship construction.")

        final_audit_score = round(min(100.0, max(20.0, audit_score)), 1)
        if final_audit_score >= 92.0:
            grade = "A+"
        elif final_audit_score >= 84.0:
            grade = "A"
        elif final_audit_score >= 76.0:
            grade = "B+"
        elif final_audit_score >= 68.0:
            grade = "B"
        elif final_audit_score >= 58.0:
            grade = "C"
        else:
            grade = "F"

        # 8. Week N+1 Lookahead Streaming Radar (D/ST & Kicker)
        lookahead_dst: list[LookaheadStreamerItem] = []
        lookahead_k: list[LookaheadStreamerItem] = []
        target_next_week = current_week + 1

        next_games_map: dict[str, Any] = {}
        if next_week_games:
            for g in next_week_games:
                if hasattr(g, "home_team") and hasattr(g, "away_team"):
                    next_games_map[g.home_team] = g
                    next_games_map[g.away_team] = g

        unowned_dsts = [p for p in available_players if p.position.upper() in ("D/ST", "DST")]
        for d in unowned_dsts:
            g = next_games_map.get(d.pro_team)
            next_opp = "VARIES"
            if g and hasattr(g, "get_opponent_for_team"):
                next_opp = g.get_opponent_for_team(d.pro_team) or "VARIES"
            score, grade = dvp_client.calculate_matchup_score(next_opp, "D/ST")
            if score >= 68.0:
                lookahead_dst.append(
                    LookaheadStreamerItem(
                        player_id=d.id,
                        full_name=d.full_name,
                        position="D/ST",
                        pro_team=d.pro_team,
                        next_week=target_next_week,
                        next_opponent=next_opp,
                        matchup_grade=grade,
                        matchup_score=score,
                        tactical_reason=f"Smash Week {target_next_week} Matchup: Faces {next_opp} ({score:.1f} DvP Score). Stash now for $0 before Tuesday waivers.",
                    )
                )
        lookahead_dst.sort(key=lambda x: x.matchup_score, reverse=True)

        unowned_ks = [p for p in available_players if p.position.upper() in ("K", "PK")]
        for k in unowned_ks:
            g = next_games_map.get(k.pro_team)
            next_opp = "VARIES"
            implied = 23.5
            if g and hasattr(g, "get_opponent_for_team"):
                next_opp = g.get_opponent_for_team(k.pro_team) or "VARIES"
                implied = g.get_implied_total_for_team(k.pro_team) if hasattr(g, "get_implied_total_for_team") else 23.5
            score = round(min(100.0, max(30.0, 50.0 + ((implied - 20.0) * 3.8))), 1)
            grade = "FAVORABLE" if score >= 70.0 else "NEUTRAL"
            if score >= 68.0:
                lookahead_k.append(
                    LookaheadStreamerItem(
                        player_id=k.id,
                        full_name=k.full_name,
                        position="K",
                        pro_team=k.pro_team,
                        next_week=target_next_week,
                        next_opponent=next_opp,
                        matchup_grade=grade,
                        matchup_score=score,
                        tactical_reason=f"High-Volume Week {target_next_week} Environment: Implied total {implied:.1f} pts vs {next_opp}.",
                    )
                )
        lookahead_k.sort(key=lambda x: x.matchup_score, reverse=True)

        # 9. Bench Deadweight Purge Detector
        deadweight_drops: list[DeadweightBenchItem] = []
        for b in bench_evals:
            if b.position.upper() in ("WR", "RB", "TE"):
                if b.projected_points < 11.0 and b.ceiling_score < 62.0 and getattr(b, "contingency_score", 0.0) < 60.0:
                    deadweight_drops.append(
                        DeadweightBenchItem(
                            player_id=b.player_id,
                            full_name=b.full_name,
                            position=b.position,
                            projected_points=b.projected_points,
                            start_score=b.start_score,
                            ceiling_score=b.ceiling_score,
                            diagnosis=f"Zero-Ceiling Depth Trap ({b.projected_points:.1f} proj, {b.ceiling_score:.1f} ceiling). In an 8-man league, safe mediocrity will never start over your active core.",
                            suggested_action="Purge immediately for an elite contingent backup RB or a Week N+1 lookahead streaming defense.",
                        )
                    )
                    prescriptions.append(f"Purge bench deadweight {b.full_name}. Roster spots in an 8-man league must hold ceiling or contingency, not 10-point filler.")

        arch_audit = RosterArchitectureAudit(
            grade=grade,
            score=final_audit_score,
            handcuff_rb_count=handcuff_count,
            wasted_bench_slots=wasted_slots,
            key_strengths=strengths,
            tactical_prescriptions=prescriptions,
        )

        return WaiverAnalysisResult(
            user_team_id=user_team_id,
            total_available_scanned=len(available_players),
            top_upgrades=upgrades[:6],
            streaming_te=streaming_te,
            streaming_dst=streaming_dst,
            streaming_k=streaming_k,
            architecture_audit=arch_audit,
            lookahead_streaming_dst=lookahead_dst[:4],
            lookahead_streaming_k=lookahead_k[:4],
            deadweight_drops=deadweight_drops,
        )


waiver_scanner = WaiverScanner()
