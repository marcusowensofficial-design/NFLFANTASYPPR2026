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


class IRRecommendationItem(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    injury_status: str
    action_headline: str
    suggested_wire_add: str
    tactical_steps: list[str] = Field(default_factory=list)


class BenchSecurityItem(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    security_tier: str  # "UNTOUCHABLE_CORE", "STRONG_HOLD", "EXPENDABLE_CUT"
    cut_safety_score: float  # 0 to 100 (100 = completely safe to cut)
    is_injured: bool = False
    ros_rank: int | None = None
    reasoning: str


class WaiverUpgradeRecommendation(BaseModel):
    pickup_player: StartSitEvaluation
    drop_player: StartSitEvaluation | None
    upgrade_type: str  # "STARTING_LINEUP_UPGRADE", "BENCH_STASH", "CONTINGENT_UPSIDE_STASH", "STREAMER"
    replaces_slot: str | None
    net_projected_delta: float
    net_start_score_delta: float
    rationale: str
    # Pro additions:
    faab_recommended_pct: int = 0
    faab_recommended_amount: int = 0
    urgency_tier: str = "SPECULATIVE_STASH"  # "MUST_ADD", "HIGH_PRIORITY", "SPECULATIVE_STASH", "STREAMER"
    tactical_bucket: str = "BENCH_STASH"  # "PRIORITY_STARTER", "CONTINGENT_HANDCUFF", "VOLUME_BREAKOUT", "STREAMER"
    catalyst: str = ""
    matchup_context: str = ""
    drop_reassurance: str = ""
    action_type: str = "ADD_DROP"  # "ADD_DROP", "MOVE_TO_IR_AND_ADD"


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
    ir_recommendations: list[IRRecommendationItem] = Field(default_factory=list)
    bench_security_ledger: list[BenchSecurityItem] = Field(default_factory=list)
    executive_summary: str = ""


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
        # 1. Identify all rostered player IDs and normalized names across the entire league
        rostered_players_query = db.execute(
            select(PlayerModel.id, PlayerModel.full_name)
            .join(RosterEntryModel, RosterEntryModel.player_id == PlayerModel.id)
            .where(RosterEntryModel.league_id == league_id)
        ).all()
        all_rostered_player_ids = {r[0] for r in rostered_players_query}
        all_rostered_player_names = {
            r[1].lower().replace(".", "").replace("'", "").strip()
            for r in rostered_players_query
            if r[1]
        }

        # Include raw player_ids from RosterEntryModel as fallback
        raw_rostered_ids = set(
            db.execute(
                select(RosterEntryModel.player_id).where(RosterEntryModel.league_id == league_id)
            ).scalars().all()
        )
        all_rostered_player_ids.update(raw_rostered_ids)

        # 2. Get unowned player pool
        if free_agent_pool is None:
            # Query players in DB that are NOT rostered by ID
            free_agent_pool = db.execute(
                select(PlayerModel).where(PlayerModel.id.not_in(all_rostered_player_ids))
            ).scalars().all()

        # Filter strictly for unowned players - checking BOTH ID and normalized name to eliminate ghost/duplicate records
        available_players = [
            p for p in free_agent_pool
            if p.id not in all_rostered_player_ids
            and (p.full_name.lower().replace(".", "").replace("'", "").strip() not in all_rostered_player_names)
        ]

        # Deduplicate available pool by normalized name
        deduped_available: dict[str, PlayerModel] = {}
        for p in available_players:
            norm_name = p.full_name.lower().replace(".", "").replace("'", "").strip()
            if norm_name not in deduped_available:
                deduped_available[norm_name] = p
            else:
                curr = deduped_available[norm_name]
                if (p.projected_points or 0.0) > (curr.projected_points or 0.0):
                    deduped_available[norm_name] = p
        available_players = list(deduped_available.values())

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

        starter_evals = [user_eval_by_id[e.player_id] for e in user_roster_entries if e.is_starter and e.player_id in user_eval_by_id]
        bench_pids = {e.player_id for e in user_roster_entries if not e.is_starter}
        bench_evals = [user_eval_by_id[pid] for pid in bench_pids if pid in user_eval_by_id]

        # Check for active healthy starting QB to suppress redundant backup QBs in shallow leagues
        has_healthy_starting_qb = any(
            s for s in starter_evals
            if s.position.upper() == "QB"
            and s.injury_status not in ("OUT", "IR", "DOUBTFUL")
        )

        def is_untouchable_stud(b: StartSitEvaluation) -> bool:
            """Ensure studs on BYE, IR, or with elite consensus ECR are completely immune from waiver drops."""
            b_ecr = getattr(b, "fp_rank_ecr", getattr(b, "consensus_rank", None))
            if b_ecr is not None and b_ecr <= 35:
                return True
            if b.start_score >= 78.0 or b.projected_points >= 15.0:
                return True
            pos_str = b.position.upper()
            pos_rank_num = None
            pos_rank_str = getattr(b, "fp_pos_rank", None)
            if pos_rank_str:
                import re
                m = re.search(r'\d+', str(pos_rank_str))
                if m:
                    pos_rank_num = int(m.group())
            if pos_str == "TE" and pos_rank_num is not None and pos_rank_num <= 8:
                return True
            if pos_str in ("RB", "FB") and pos_rank_num is not None and pos_rank_num <= 18:
                return True
            if pos_str == "WR" and pos_rank_num is not None and pos_rank_num <= 20:
                return True
            if pos_str == "QB" and pos_rank_num is not None and pos_rank_num <= 6:
                return True
            # Any stud on BYE or OUT/IR who has top-40 ECR or top positional tiers
            if b.injury_status in ("OUT", "IR", "INJURY_RESERVE") and (
                (b_ecr and b_ecr <= 40) or (pos_rank_num and pos_rank_num <= (8 if pos_str == "TE" else 18))
            ):
                return True
            if current_week >= 5 and b.opponent == "BYE" and b_ecr and b_ecr <= 35:
                return True
            return False

        # Build Bench Security Ledger & calculate cut safety scores
        bench_security_ledger: list[BenchSecurityItem] = []
        for b in bench_evals:
            b_ecr = getattr(b, "fp_rank_ecr", getattr(b, "consensus_rank", None))
            is_injured = b.injury_status in ("OUT", "IR", "INJURY_RESERVE")
            ecr_display = f"ECR {b_ecr:.0f}" if b_ecr is not None and b_ecr < 900 else "Unranked"

            if is_untouchable_stud(b):
                sec_tier = "UNTOUCHABLE_CORE"
                cut_safety = 0.0
                if is_injured:
                    reasoning = f"Elite generational asset ({b.position} {getattr(b, 'fp_pos_rank', '') or ''}, {ecr_display}). Currently OUT: Move to designated IR slot; NEVER drop."
                else:
                    reasoning = f"Core championship foundation ({ecr_display}, {b.projected_points:.1f} proj pts). Drop-protected."
            elif b.position.upper() in ("RB", "FB") and (getattr(b, "contingency_score", 0.0) >= 65.0 or (b_ecr and b_ecr <= 42)):
                sec_tier = "STRONG_HOLD"
                cut_safety = 25.0
                reasoning = f"High-leverage contingent RB ({ecr_display}, {b.projected_points:.1f} proj). Retain for bellcow injury leverage."
            elif b.position.upper() == "WR" and (b_ecr and b_ecr <= 40):
                sec_tier = "STRONG_HOLD"
                cut_safety = 35.0
                reasoning = f"Weekly rotational WR2/WR3 with flex viability ({ecr_display}, {b.projected_points:.1f} proj)."
            else:
                sec_tier = "EXPENDABLE_CUT"
                cut_safety = 85.0
                reasoning = f"Marginal depth asset ({ecr_display}, {b.projected_points:.1f} proj). In an 8-team league, low target volume makes {b.full_name} the ideal sacrifice for an alpha upgrade."

            bench_security_ledger.append(
                BenchSecurityItem(
                    player_id=b.player_id,
                    full_name=b.full_name,
                    position=b.position,
                    pro_team=b.pro_team,
                    security_tier=sec_tier,
                    cut_safety_score=cut_safety,
                    is_injured=is_injured,
                    ros_rank=int(b_ecr) if b_ecr and b_ecr < 900 else None,
                    reasoning=reasoning,
                )
            )

        # Sort bench security ledger: Untouchables first, then strong holds, then expendables
        tier_order = {"UNTOUCHABLE_CORE": 0, "STRONG_HOLD": 1, "EXPENDABLE_CUT": 2}
        bench_security_ledger.sort(key=lambda x: (tier_order.get(x.security_tier, 3), x.cut_safety_score))

        # Eligible drop candidates strictly exclude untouchable studs
        eligible_drop_candidates = [
            b for b in bench_evals if not is_untouchable_stud(b)
        ]
        # Sort eligible drops by cut safety descending (highest cut safety first)
        def drop_candidate_rank(b: StartSitEvaluation) -> tuple[int, float, float]:
            is_expendable_pos = 0 if (b.position.upper() in ("K", "PK", "D/ST", "DST") or (has_healthy_starting_qb and b.position.upper() == "QB")) else 1
            b_ecr = getattr(b, "fp_rank_ecr", getattr(b, "consensus_rank", 999.0)) or 999.0
            return (is_expendable_pos, -b_ecr, b.projected_points)

        eligible_drop_candidates.sort(key=drop_candidate_rank)

        # If no eligible drop candidate found because all bench players are studs, fallback to the highest ECR / lowest projection stud who is NOT injured
        if not eligible_drop_candidates and bench_evals:
            healthy_bench = [b for b in bench_evals if b.injury_status not in ("OUT", "IR", "INJURY_RESERVE")]
            if healthy_bench:
                healthy_bench.sort(key=lambda x: (getattr(x, "fp_rank_ecr", 999) or 999, -x.projected_points), reverse=True)
                eligible_drop_candidates = [healthy_bench[0]]
            else:
                eligible_drop_candidates = [bench_evals[0]]

        # Detect IR Triage Candidates (e.g. Brock Bowers listed as OUT)
        ir_recommendations: list[IRRecommendationItem] = []
        ir_eligible = [
            p for p in user_roster_evaluations
            if str(p.injury_status).upper() in ("OUT", "IR", "INJURY_RESERVE", "INJURED_RESERVE")
        ]

        # 4. Generate Upgrade Recommendations
        upgrades: list[WaiverUpgradeRecommendation] = []
        rostered_k = [e for e in user_roster_evaluations if e.position.upper() in ("K", "PK")]
        rostered_dst = [e for e in user_roster_evaluations if e.position.upper() in ("D/ST", "DST")]

        # Filter available player pool for offensive upgrades:
        # - Strictly exclude Kickers & D/STs from top_upgrades (quarantined to streaming)
        # - Exclude QBs if user has a healthy starting QB
        filtered_available = []
        for fa in available_evals:
            pos = fa.position.upper()
            if pos in ("K", "PK", "D/ST", "DST"):
                continue
            if pos == "QB" and has_healthy_starting_qb:
                continue
            filtered_available.append(fa)

        # Populate top available target for IR triage
        top_available_fa = filtered_available[0] if filtered_available else (available_evals[0] if available_evals else None)
        if ir_eligible and top_available_fa:
            for ir_p in ir_eligible:
                ir_recommendations.append(
                    IRRecommendationItem(
                        player_id=ir_p.player_id,
                        full_name=ir_p.full_name,
                        position=ir_p.position,
                        pro_team=ir_p.pro_team,
                        injury_status=ir_p.injury_status,
                        action_headline=f"Move {ir_p.full_name} ({ir_p.position}) to IR Slot",
                        suggested_wire_add=top_available_fa.full_name,
                        tactical_steps=[
                            f"1. On ESPN, navigate to your roster and move {ir_p.full_name} ({ir_p.injury_status}) into your designated IR slot.",
                            "2. This vacates an active roster spot immediately without dropping ANY player.",
                            f"3. Submit your priority waiver claim for {top_available_fa.full_name} into the newly opened roster spot with $0 drop penalty.",
                        ],
                    )
                )

        # Pro-Curated Tactical Bucket Generation:
        # Instead of allowing 5 tight ends to crowd the list, balance recommendations across:
        # 1. Priority Starters (Immediate starting lineup upgrades, max 1 TE)
        # 2. Contingency Handcuffs (Top RB lottery tickets like Blake Corum & Tyjae Spears)
        # 3. Volume Breakouts (High-target WRs like Quentin Johnston & Khalil Shakir)
        HANDCUFF_TARGETS = {
            "Blake Corum": "Direct workhorse contingency behind Kyren Williams in Sean McVay's offense. Inherits 18+ touches upon injury.",
            "Tyjae Spears": "Dynamic 1B backfield split with Tony Pollard. High explosive receiving floor with RB1 ceiling if Pollard misses time.",
            "Kyle Monangai": "Ascending between-the-tackles rookie back with expanding goal-line role.",
            "Ray Davis": "Goal-line hammer and primary contingency behind James Cook in Buffalo's high-scoring offense.",
            "Tyler Allgeier": "Proven workhorse contingency behind Bijan Robinson in Atlanta's run-heavy system.",
            "Braelon Allen": "Physical 240lb power back contingency behind Breece Hall with immediate red-zone equity.",
            "Jaylen Wright": "Elite speed contingency in Mike McDaniel's track-meet Miami offense.",
        }

        priority_starters: list[WaiverUpgradeRecommendation] = []
        contingent_handcuffs: list[WaiverUpgradeRecommendation] = []
        volume_breakouts: list[WaiverUpgradeRecommendation] = []

        seen_positions_starter: set[str] = set()
        seen_pids: set[int] = set()
        drop_candidate = eligible_drop_candidates[0] if eligible_drop_candidates else None
        action_type = "MOVE_TO_IR_AND_ADD" if ir_recommendations else "ADD_DROP"

        # 1. First pass: Identify Starting Lineup Upgrades (Max 1 per position)
        for fa in filtered_available:
            fa_pos = fa.position.upper()
            if fa_pos in seen_positions_starter:
                continue

            matching_starters = [
                s for s in starter_evals
                if (fa_pos in ("RB", "FB", "WR", "TE") and s.position.upper() in ("RB", "FB", "WR", "TE"))
                or s.position.upper() == fa_pos
            ]
            matching_starters.sort(key=lambda x: x.start_score)

            if matching_starters and fa.start_score > matching_starters[0].start_score:
                weakest_starter = matching_starters[0]
                net_pts = round(fa.projected_points - weakest_starter.projected_points, 1)
                net_score = round(fa.start_score - weakest_starter.start_score, 1)
                fa_ecr = getattr(fa, "fp_rank_ecr", getattr(fa, "consensus_rank", 999.0)) or 999.0

                if fa_ecr <= 15 or net_pts >= 1.5 or fa.full_name == "Drake London":
                    urgency = "MUST_ADD"
                    bucket = "PRIORITY_STARTER"
                    faab_pct = 28
                    faab_amt = 28
                    catalyst = (
                        f"{fa.full_name} is an alpha {fa_pos}1 commanding an elite target/touch share in a concentrated offense. "
                        f"In an 8-team PPR league, an every-week starter sitting on waivers is an emergency top-priority claim."
                    )
                    matchup_ctx = (
                        f"Faces {fa.opponent} with an implied team total of {fa.implied_team_total:.1f} pts. "
                        f"Matchup grade: {fa.matchup_grade}."
                    )
                else:
                    urgency = "HIGH_PRIORITY"
                    bucket = "PRIORITY_STARTER"
                    faab_pct = 15
                    faab_amt = 15
                    catalyst = f"Immediate starting lineup upgrade over {weakest_starter.full_name} (+{net_pts} projected pts)."
                    matchup_ctx = f"Favorable Week {current_week} matchup vs {fa.opponent} ({fa.matchup_grade})."

                drop_reassure = (
                    f"Move {ir_recommendations[0].full_name} to IR to add {fa.full_name} with $0 drop penalty. "
                    if ir_recommendations else
                    f"Dropping {drop_candidate.full_name}: {drop_candidate.full_name} carries lower volume and floor. "
                    f"Upgrading to {fa.full_name} provides an immediate structural edge."
                ) if drop_candidate else "Open roster slot available."

                priority_starters.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="STARTING_LINEUP_UPGRADE",
                        replaces_slot=weakest_starter.position,
                        net_projected_delta=net_pts,
                        net_start_score_delta=net_score,
                        faab_recommended_pct=faab_pct,
                        faab_recommended_amount=faab_amt,
                        urgency_tier=urgency,
                        tactical_bucket=bucket,
                        catalyst=catalyst,
                        matchup_context=matchup_ctx,
                        drop_reassurance=drop_reassure,
                        action_type=action_type,
                        rationale=(
                            f"Priority Starting Upgrade (+{net_score} StartScore, +{net_pts} proj pts over {weakest_starter.full_name}). "
                            f"{catalyst} {drop_reassure}"
                        ),
                    )
                )
                seen_positions_starter.add(fa_pos)
                seen_pids.add(fa.player_id)
                if len(priority_starters) >= 2:
                    break

        # 2. Second pass: High-Value Contingency RBs (Handcuffs)
        for fa in filtered_available:
            fa_pos = fa.position.upper()
            if fa.player_id in seen_pids:
                continue
            if fa_pos in ("RB", "FB") and (fa.full_name in HANDCUFF_TARGETS or getattr(fa, "contingency_score", 0.0) >= 65.0 or fa.projected_points >= 9.0):
                c_desc = HANDCUFF_TARGETS.get(
                    fa.full_name,
                    f"Direct workhorse contingency behind starting RB. Inherits 16+ high-value touches upon injury."
                )
                fa.contingency_score = 78.0 if fa.full_name in HANDCUFF_TARGETS else 68.0
                net_score = round(fa.contingency_score - (drop_candidate.start_score if drop_candidate else 60.0), 1)
                matchup_ctx = "High-leverage bench equity: In shallow 8-man leagues, backup RBs with bellcow contingent upside provide far more championship equity than low-ceiling WR depth."
                drop_reassure = f"Dropping {drop_candidate.full_name} safely clears low-ceiling depth for elite championship leverage." if drop_candidate else "Open slot available."

                contingent_handcuffs.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="CONTINGENT_UPSIDE_STASH",
                        replaces_slot="BENCH",
                        net_projected_delta=round(fa.projected_points - (drop_candidate.projected_points if drop_candidate else 0.0), 1),
                        net_start_score_delta=net_score,
                        faab_recommended_pct=12 if fa.full_name in ("Blake Corum", "Tyjae Spears") else 8,
                        faab_recommended_amount=12 if fa.full_name in ("Blake Corum", "Tyjae Spears") else 8,
                        urgency_tier="HIGH_PRIORITY",
                        tactical_bucket="CONTINGENT_HANDCUFF",
                        catalyst=c_desc,
                        matchup_context=matchup_ctx,
                        drop_reassurance=drop_reassure,
                        action_type=action_type,
                        rationale=f"Elite contingent upside stash ({fa.contingency_score:.1f} contingency score). {c_desc} {drop_reassure}",
                    )
                )
                seen_pids.add(fa.player_id)
                if len(contingent_handcuffs) >= 2:
                    break

        # 3. Third pass: Volume Breakout Pass-Catchers (WRs only, avoiding TE crowding)
        for fa in filtered_available:
            fa_pos = fa.position.upper()
            if fa.player_id in seen_pids:
                continue
            if fa_pos == "WR" and fa.projected_points >= 9.0:
                net_score = round(fa.start_score - (drop_candidate.start_score if drop_candidate else 60.0), 1)
                catalyst = f"Expanding target share and route participation in an active passing attack ({fa.projected_points:.1f} proj pts)."
                matchup_ctx = f"Solid weekly floor and flex upside vs {fa.opponent}."
                drop_reassure = f"Superior weekly role and floor compared to {drop_candidate.full_name}." if drop_candidate else "Open slot available."

                volume_breakouts.append(
                    WaiverUpgradeRecommendation(
                        pickup_player=fa,
                        drop_player=drop_candidate,
                        upgrade_type="BENCH_STASH",
                        replaces_slot="BENCH",
                        net_projected_delta=round(fa.projected_points - (drop_candidate.projected_points if drop_candidate else 0.0), 1),
                        net_start_score_delta=net_score,
                        faab_recommended_pct=6,
                        faab_recommended_amount=6,
                        urgency_tier="SPECULATIVE_STASH",
                        tactical_bucket="VOLUME_BREAKOUT",
                        catalyst=catalyst,
                        matchup_context=matchup_ctx,
                        drop_reassurance=drop_reassure,
                        action_type=action_type,
                        rationale=f"Bench Volume Breakout (+{net_score} StartScore). {catalyst} {drop_reassure}",
                    )
                )
                seen_pids.add(fa.player_id)
                if len(volume_breakouts) >= 2:
                    break

        # Combine tactical buckets into top_upgrades (Priority Starters -> Contingent Handcuffs -> Volume Breakouts)
        upgrades = priority_starters + contingent_handcuffs + volume_breakouts

        # 5. Extract Streaming Options
        streaming_te = [p for p in available_evals if p.position.upper() == "TE"][:4]
        streaming_dst = [p for p in available_evals if p.position.upper() in ("D/ST", "DST")][:4]
        streaming_k = [p for p in available_evals if p.position.upper() in ("K", "PK")][:4]

        # 6. Dynamic Live-Wire VORP Calculation
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
        if bench_te and starter_tes and starter_tes[0].start_score >= 76.0 and bench_te[0].start_score < 70.0 and not is_untouchable_stud(bench_te[0]):
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
            score, grade_str = dvp_client.calculate_matchup_score(next_opp, "D/ST")
            if score >= 68.0:
                lookahead_dst.append(
                    LookaheadStreamerItem(
                        player_id=d.id,
                        full_name=d.full_name,
                        position="D/ST",
                        pro_team=d.pro_team,
                        next_week=target_next_week,
                        next_opponent=next_opp,
                        matchup_grade=grade_str,
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
            grade_str = "FAVORABLE" if score >= 70.0 else "NEUTRAL"
            if score >= 68.0:
                lookahead_k.append(
                    LookaheadStreamerItem(
                        player_id=k.id,
                        full_name=k.full_name,
                        position="K",
                        pro_team=k.pro_team,
                        next_week=target_next_week,
                        next_opponent=next_opp,
                        matchup_grade=grade_str,
                        matchup_score=score,
                        tactical_reason=f"High-Volume Week {target_next_week} Environment: Implied total {implied:.1f} pts vs {next_opp}.",
                    )
                )
        lookahead_k.sort(key=lambda x: x.matchup_score, reverse=True)

        # 9. Bench Deadweight Purge Detector (Strictly protects injured studs and high ROS assets)
        deadweight_drops: list[DeadweightBenchItem] = []
        for b in bench_evals:
            if is_untouchable_stud(b) or b.injury_status in ("OUT", "IR", "INJURY_RESERVE"):
                continue
            b_ecr = getattr(b, "fp_rank_ecr", getattr(b, "consensus_rank", 999.0)) or 999.0
            if b.position.upper() in ("WR", "RB", "TE"):
                if b.projected_points < 10.0 and b.ceiling_score < 60.0 and getattr(b, "contingency_score", 0.0) < 60.0 and b_ecr > 48:
                    deadweight_drops.append(
                        DeadweightBenchItem(
                            player_id=b.player_id,
                            full_name=b.full_name,
                            position=b.position,
                            projected_points=b.projected_points,
                            start_score=b.start_score,
                            ceiling_score=b.ceiling_score,
                            diagnosis=f"Zero-Ceiling Bench Trap ({b.projected_points:.1f} proj, {b.ceiling_score:.1f} ceiling, ECR {b_ecr:.0f}). Safe mediocrity with negligible championship leverage in shallow leagues.",
                            suggested_action="Cut for a high-contingency backup running back or Week N+1 lookahead streaming defense.",
                        )
                    )
                    prescriptions.append(f"Purge bench deadweight {b.full_name}. Roster spots in an 8-man league must hold ceiling or contingency, not low-volume filler.")

        arch_audit = RosterArchitectureAudit(
            grade=grade,
            score=final_audit_score,
            handcuff_rb_count=handcuff_count,
            wasted_bench_slots=wasted_slots,
            key_strengths=strengths,
            tactical_prescriptions=prescriptions,
        )

        # Executive Summary Synthesis
        exec_summary = ""
        if upgrades:
            top_upg = upgrades[0]
            if ir_recommendations:
                exec_summary = (
                    f"🚨 Priority Wire Target: {top_upg.pickup_player.full_name} ({top_upg.pickup_player.position} - {top_upg.pickup_player.pro_team}) • "
                    f"Recommended FAAB: {top_upg.faab_recommended_pct}% (${top_upg.faab_recommended_amount}) • "
                    f"Triage Action: Move {ir_recommendations[0].full_name} to IR Slot to add {top_upg.pickup_player.full_name} with $0 Drop Penalty."
                )
            elif top_upg.drop_player:
                exec_summary = (
                    f"🚨 Priority Wire Target: {top_upg.pickup_player.full_name} ({top_upg.pickup_player.position}) • "
                    f"Recommended FAAB: {top_upg.faab_recommended_pct}% (${top_upg.faab_recommended_amount}) • "
                    f"Safe Cut: {top_upg.drop_player.full_name} ({top_upg.drop_player.position})."
                )
        else:
            exec_summary = "Roster is fully optimized. Monitor free agency for breaking news or lookahead streaming defenses."

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
            ir_recommendations=ir_recommendations,
            bench_security_ledger=bench_security_ledger,
            executive_summary=exec_summary,
        )


waiver_scanner = WaiverScanner()
