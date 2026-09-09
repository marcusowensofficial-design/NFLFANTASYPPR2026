"""Lineup Optimizer honoring dynamic ESPN roster slots, eligibility, and game locks."""

import logging
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.espn.constants import SLOT_NAME_MAP, RosterSlot
from src.services.recommendation.comparator import ComparisonResult, player_comparator
from src.services.recommendation.scoring_engine import StartSitEvaluation

logger = logging.getLogger(__name__)


class SlotAssignment(BaseModel):
    slot_id: int
    slot_name: str
    recommended_player: StartSitEvaluation
    current_starter: StartSitEvaluation | None = None
    is_diff: bool = False
    net_start_score_delta: float = 0.0
    net_projected_delta: float = 0.0
    is_flex_timing_optimal: bool = True
    flex_timing_note: str | None = None


class CloseCallPair(BaseModel):
    slot_name: str
    starter: StartSitEvaluation
    bench_player: StartSitEvaluation
    score_delta: float
    comparison: ComparisonResult


# Canonical fantasy roster slot ordering
SLOT_ORDER: dict[str, int] = {
    "QB": 10,
    "TQB": 11,
    "RB": 20,
    "RB/WR": 25,
    "WR": 30,
    "WR/TE": 35,
    "TE": 40,
    "FLEX": 50,
    "SUPERFLEX": 60,
    "OP": 60,
    "K": 70,
    "KICKER": 70,
    "PK": 70,
    "D/ST": 80,
    "DST": 80,
    "DEF": 80,
    "BE": 90,
    "BENCH": 90,
    "IR": 100,
}


class OptimizedLineupResult(BaseModel):
    team_id: int
    total_start_score: float
    total_projected_points: float
    current_espn_projected: float
    net_projected_gain: float
    starters: list[SlotAssignment]
    bench: list[StartSitEvaluation]
    ir: list[StartSitEvaluation] = Field(default_factory=list)
    bench_slots_count: int = 7
    ir_slots_count: int = 1
    close_calls: list[CloseCallPair]
    differences_count: int
    mode: str = "BALANCED"
    projection_source: str = "MODEL"
    total_model_projected: float = 0.0
    total_fp_projected: float = 0.0
    total_sleeper_projected: float = 0.0
    total_espn_projected: float = 0.0
    total_consensus_projected: float = 0.0
    opponent_projected_points: float | None = None
    opponent_team_id: int | None = None
    opponent_team_name: str | None = None
    opponent_team_abbrev: str | None = None
    implied_matchup_spread: float | None = None
    game_theory_posture: str | None = None
    game_theory_recommendation: str | None = None
    flex_timing_risk: bool = False
    flex_timing_warning: str | None = None
    active_stacks: list[str] = Field(default_factory=list)


def get_kickoff_timestamp(eval_item: StartSitEvaluation) -> str:
    """Returns a sortable ISO-like string representing game kickoff time."""
    if eval_item.game_date:
        return str(eval_item.game_date)
    # Default fallback: standard Sunday 1:00 PM ET
    return "2026-09-13T17:00:00Z"


class LineupOptimizer:
    """Solves the optimal starting lineup maximizing Total StartScore under ESPN rules."""

    def optimize_lineup(
        self,
        team_id: int,
        roster_slots_config: dict[str, int],
        evaluations: list[StartSitEvaluation],
        current_starter_ids: set[int] | None = None,
        locked_player_ids: set[int] | None = None,
        locked_starter_slot_map: dict[int, int] | None = None,
        mode: str = "BALANCED",
        opponent_projected_points: float | None = None,
        opponent_team_id: int | None = None,
        opponent_team_name: str | None = None,
        opponent_team_abbrev: str | None = None,
        current_ir_ids: set[int] | None = None,
        projection_source: str = "MODEL",
    ) -> OptimizedLineupResult:
        if current_starter_ids is None:
            current_starter_ids = set()
        if current_ir_ids is None:
            current_ir_ids = set()
        if locked_player_ids is None:
            locked_player_ids = set()
        if locked_starter_slot_map is None:
            locked_starter_slot_map = {}

        mode_str = str(getattr(mode, "default", mode) if hasattr(mode, "default") else (mode or "BALANCED"))
        mode_upper = mode_str.upper()
        eval_by_id = {e.player_id: e for e in evaluations}

        # Opponent Matchup Game Theory Posture & Spread Calculation
        implied_spread: float | None = None
        game_theory_posture: str | None = None
        game_theory_rec: str | None = None

        current_starters_list = [eval_by_id[pid] for pid in current_starter_ids if pid in eval_by_id]
        current_espn_points = sum(p.projected_points for p in current_starters_list)

        if isinstance(opponent_projected_points, (int, float)) and opponent_projected_points > 0:
            est_proj = current_espn_points if current_espn_points > 0 else sum(p.projected_points for p in sorted(evaluations, key=lambda x: x.start_score, reverse=True)[:9])
            implied_spread = round(est_proj - opponent_projected_points, 1)

            if mode_upper == "AUTO":
                if implied_spread <= -7.0:
                    mode_upper = "CEILING"
                    game_theory_posture = "HEAVY_UNDERDOG_CEILING"
                    game_theory_rec = (
                        f"Underdog Game Theory ({implied_spread:+.1f} pts): Auto-activated CEILING mode. "
                        f"Prioritizing 90th-percentile boom profiles and shootout environments to chase upset variance."
                    )
                elif implied_spread >= 8.0:
                    mode_upper = "FLOOR"
                    game_theory_posture = "SUBSTANTIAL_FAVORITE_FLOOR"
                    game_theory_rec = (
                        f"Favorite Game Theory ({implied_spread:+.1f} pts): Auto-activated FLOOR mode. "
                        f"Prioritizing high touch floors and health certainty to suppress bust variance and protect lead."
                    )
                else:
                    mode_upper = "BALANCED"
                    game_theory_posture = "BALANCED_TOSS_UP"
                    game_theory_rec = (
                        f"Toss-up Matchup ({implied_spread:+.1f} pts): Balanced StartScore composite optimization."
                    )
            else:
                if implied_spread <= -7.0:
                    game_theory_posture = "HEAVY_UNDERDOG_CEILING"
                    game_theory_rec = (
                        f"Underdog Posture ({implied_spread:+.1f} pts): Consider CEILING mode to chase weekly upset potential."
                    )
                elif implied_spread >= 8.0:
                    game_theory_posture = "SUBSTANTIAL_FAVORITE_FLOOR"
                    game_theory_rec = (
                        f"Favorite Posture ({implied_spread:+.1f} pts): Consider FLOOR mode to protect your projected lead."
                    )
                else:
                    game_theory_posture = "BALANCED_TOSS_UP"
                    game_theory_rec = (
                        f"Toss-up Matchup ({implied_spread:+.1f} pts): Balanced composite optimization recommended."
                    )

        # Sort available players: Active players with points first, Bye-week players last
        def sort_key(p: StartSitEvaluation) -> tuple[bool, float]:
            is_bye = p.opponent == "BYE" or p.projected_points <= 0.0
            if mode_upper == "CEILING":
                metric = p.ceiling_score or p.start_score
            elif mode_upper == "FLOOR":
                metric = p.floor_score or p.start_score
            else:
                metric = p.start_score
            return (not is_bye, metric)

        available = sorted(evaluations, key=sort_key, reverse=True)
        assigned_player_ids: set[int] = set()
        starters_assigned: list[SlotAssignment] = []

        # Target slot counts
        rem_slots = {
            "QB": roster_slots_config.get("QB", 1),
            "RB": roster_slots_config.get("RB", 2),
            "WR": roster_slots_config.get("WR", 2),
            "TE": roster_slots_config.get("TE", 1),
            "FLEX": roster_slots_config.get("FLEX", 1),
            "SUPERFLEX": roster_slots_config.get("SUPERFLEX", 0) + roster_slots_config.get("OP", 0),
            "D/ST": roster_slots_config.get("D/ST", 1),
            "K": roster_slots_config.get("K", 1),
        }

        # 1. Lock bench players whose games have started (they cannot be promoted to starters)
        locked_bench_ids = {pid for pid in locked_player_ids if pid not in current_starter_ids}

        # 2. Fill locked starters FIRST (game has kicked off, cannot be moved)
        for p in available:
            if p.player_id in locked_player_ids and p.player_id in current_starter_ids:
                assigned_player_ids.add(p.player_id)
                pos = p.position.upper()
                assigned_slot_id = locked_starter_slot_map.get(p.player_id)

                if assigned_slot_id is None:
                    if pos == "QB" and rem_slots["QB"] > 0:
                        assigned_slot_id = RosterSlot.QB
                        rem_slots["QB"] -= 1
                    elif pos in ("RB", "FB") and rem_slots["RB"] > 0:
                        assigned_slot_id = RosterSlot.RB
                        rem_slots["RB"] -= 1
                    elif pos == "WR" and rem_slots["WR"] > 0:
                        assigned_slot_id = RosterSlot.WR
                        rem_slots["WR"] -= 1
                    elif pos == "TE" and rem_slots["TE"] > 0:
                        assigned_slot_id = RosterSlot.TE
                        rem_slots["TE"] -= 1
                    elif pos in ("RB", "FB", "WR", "TE") and rem_slots["FLEX"] > 0:
                        assigned_slot_id = RosterSlot.FLEX
                        rem_slots["FLEX"] -= 1
                    elif pos in ("QB", "RB", "FB", "WR", "TE") and rem_slots["SUPERFLEX"] > 0:
                        assigned_slot_id = RosterSlot.OP
                        rem_slots["SUPERFLEX"] -= 1
                    elif pos in ("D/ST", "DST") and rem_slots["D/ST"] > 0:
                        assigned_slot_id = RosterSlot.DST
                        rem_slots["D/ST"] -= 1
                    elif pos in ("K", "PK") and rem_slots["K"] > 0:
                        assigned_slot_id = RosterSlot.K
                        rem_slots["K"] -= 1
                    else:
                        assigned_slot_id = RosterSlot.FLEX
                else:
                    slot_name = SLOT_NAME_MAP.get(assigned_slot_id, pos)
                    if slot_name in rem_slots and rem_slots[slot_name] > 0:
                        rem_slots[slot_name] -= 1

                starters_assigned.append(
                    SlotAssignment(
                        slot_id=assigned_slot_id,
                        slot_name=SLOT_NAME_MAP.get(assigned_slot_id, pos),
                        recommended_player=p,
                    )
                )

        # Helper to assign slots by position
        def assign_onesie_position(pos_name: str, slot_id: int, count: int) -> None:
            assigned_count = 0
            for p in available:
                if assigned_count >= count:
                    break
                if p.player_id in assigned_player_ids or p.player_id in locked_bench_ids:
                    continue
                if p.position.upper() == pos_name.upper():
                    assigned_player_ids.add(p.player_id)
                    starters_assigned.append(
                        SlotAssignment(
                            slot_id=slot_id,
                            slot_name=SLOT_NAME_MAP.get(slot_id, pos_name),
                            recommended_player=p,
                        )
                    )
                    assigned_count += 1

        # 3. Assign non-flex positions first (QB, D/ST, K)
        assign_onesie_position("QB", RosterSlot.QB, rem_slots["QB"])
        assign_onesie_position("D/ST", RosterSlot.DST, rem_slots["D/ST"])
        assign_onesie_position("K", RosterSlot.K, rem_slots["K"])

        # 4. Chronological & Tactical Allocation for RB, WR, TE, and FLEX
        starting_qb = next(
            (s.recommended_player for s in starters_assigned if s.slot_id == RosterSlot.QB),
            None,
        )

        def skill_sort_key(p: StartSitEvaluation) -> tuple[bool, float]:
            is_bye = p.opponent == "BYE" or p.projected_points <= 0.0
            if mode_upper == "CEILING":
                metric = p.ceiling_score or p.start_score
                if starting_qb and p.pro_team == starting_qb.pro_team and p.position.upper() in ("WR", "TE"):
                    metric += 3.0  # Stacking correlation bonus for ceiling mode
            elif mode_upper == "FLOOR":
                metric = p.floor_score or p.start_score
            else:
                metric = p.start_score
                # In BALANCED mode, competitive or underdog matchup game theory encourages stacking
                if starting_qb and p.pro_team == starting_qb.pro_team and p.position.upper() in ("WR", "TE"):
                    if implied_spread is not None and implied_spread <= 4.0:
                        metric += 1.8  # Correlated boom leverage in close / underdog matchups

            # Full PPR FLEX Tactical Calibration:
            # High-target pass-catchers in full PPR outscore 2-down rushers in floor and ceiling
            if p.position.upper() == "WR":
                stats = p.itemized_stats or {}
                tgts = float(stats.get("targets", 0.0))
                if tgts >= 7.0:
                    metric += 1.0  # 1.0 PPR reception floor bonus for alpha target WRs in FLEX contention

            return (not is_bye, metric)

        # Re-sort available for skill positions with correlation stacking awareness
        skill_available = sorted(available, key=skill_sort_key, reverse=True)

        # Step A: Select the optimal set of starters for primary slots + FLEX
        needed_rb = rem_slots["RB"]
        needed_wr = rem_slots["WR"]
        needed_te = rem_slots["TE"]
        needed_flex = rem_slots["FLEX"]

        chosen_rbs: list[StartSitEvaluation] = []
        chosen_wrs: list[StartSitEvaluation] = []
        chosen_tes: list[StartSitEvaluation] = []

        # Find candidate players by position
        for p in skill_available:
            if p.player_id in assigned_player_ids or p.player_id in locked_bench_ids:
                continue
            pos = p.position.upper()
            if pos in ("RB", "FB") and len(chosen_rbs) < (needed_rb + needed_flex):
                chosen_rbs.append(p)
            elif pos == "WR" and len(chosen_wrs) < (needed_wr + needed_flex):
                chosen_wrs.append(p)
            elif pos == "TE" and len(chosen_tes) < (needed_te + needed_flex):
                chosen_tes.append(p)

        # Select the best primary players
        prim_rbs = chosen_rbs[:needed_rb]
        prim_wrs = chosen_wrs[:needed_wr]
        prim_tes = chosen_tes[:needed_te]

        # Remaining candidates compete for FLEX slots
        flex_candidates: list[StartSitEvaluation] = (
            chosen_rbs[needed_rb:] + chosen_wrs[needed_wr:] + chosen_tes[needed_te:]
        )
        flex_candidates.sort(key=skill_sort_key, reverse=True)
        chosen_flex_pool = flex_candidates[:needed_flex]

        # Combine all starters for these positions:
        all_chosen_skill = prim_rbs + prim_wrs + prim_tes + chosen_flex_pool

        # Mark all selected as assigned
        for p in all_chosen_skill:
            assigned_player_ids.add(p.player_id)

        # Step B: Chronological kickoff allocation:
        # Sort each positional group chronologically (earliest kickoff first for primary slots)
        rbs_pool = [p for p in all_chosen_skill if p.position.upper() in ("RB", "FB")]
        wrs_pool = [p for p in all_chosen_skill if p.position.upper() == "WR"]
        tes_pool = [p for p in all_chosen_skill if p.position.upper() == "TE"]

        # Among all flex-eligible starters, identify who should hold the FLEX slot:
        # In 8-man leagues, the FLEX starter should be the player with the LATEST kickoff time
        # among the excess players so emergency swaps remain viable all weekend.
        flex_assigned_players: list[StartSitEvaluation] = []
        for _ in range(needed_flex):
            # Candidates for FLEX are players from positions that exceed primary slot needs
            viable_flex_candidates: list[StartSitEvaluation] = []
            if len(rbs_pool) > needed_rb:
                viable_flex_candidates.extend(rbs_pool)
            if len(wrs_pool) > needed_wr:
                viable_flex_candidates.extend(wrs_pool)
            if len(tes_pool) > needed_te:
                viable_flex_candidates.extend(tes_pool)

            if not viable_flex_candidates:
                break

            # Pick the candidate with the LATEST kickoff time
            latest_candidate = max(viable_flex_candidates, key=get_kickoff_timestamp)
            flex_assigned_players.append(latest_candidate)
            if latest_candidate in rbs_pool:
                rbs_pool.remove(latest_candidate)
            elif latest_candidate in wrs_pool:
                wrs_pool.remove(latest_candidate)
            elif latest_candidate in tes_pool:
                tes_pool.remove(latest_candidate)

        # Sort primary starters earliest kickoff first
        rbs_pool.sort(key=get_kickoff_timestamp)
        wrs_pool.sort(key=get_kickoff_timestamp)
        tes_pool.sort(key=get_kickoff_timestamp)

        for p in rbs_pool[:needed_rb]:
            starters_assigned.append(
                SlotAssignment(
                    slot_id=RosterSlot.RB,
                    slot_name="RB",
                    recommended_player=p,
                )
            )

        for p in wrs_pool[:needed_wr]:
            starters_assigned.append(
                SlotAssignment(
                    slot_id=RosterSlot.WR,
                    slot_name="WR",
                    recommended_player=p,
                )
            )

        for p in tes_pool[:needed_te]:
            starters_assigned.append(
                SlotAssignment(
                    slot_id=RosterSlot.TE,
                    slot_name="TE",
                    recommended_player=p,
                )
            )

        # Assign FLEX starters with timing optimization check
        primary_max_kickoff = max(
            [get_kickoff_timestamp(p) for p in (rbs_pool + wrs_pool + tes_pool)]
            or ["0000"]
        )

        for p in flex_assigned_players:
            p_time = get_kickoff_timestamp(p)
            is_optimal_time = p_time >= primary_max_kickoff
            timing_note = (
                "Optimal FLEX timing: Latest kickoff preserves emergency pivot flexibility."
                if is_optimal_time
                else "Tactical Note: Early kickoff in FLEX locks slot early; no later options available."
            )
            starters_assigned.append(
                SlotAssignment(
                    slot_id=RosterSlot.FLEX,
                    slot_name="FLEX",
                    recommended_player=p,
                    is_flex_timing_optimal=is_optimal_time,
                    flex_timing_note=timing_note,
                )
            )

        # 5. Assign remaining SUPERFLEX (QB/RB/WR/TE)
        sflex_assigned = 0
        for p in available:
            if sflex_assigned >= rem_slots["SUPERFLEX"]:
                break
            if p.player_id in assigned_player_ids or p.player_id in locked_bench_ids:
                continue
            if p.position.upper() in ("QB", "RB", "WR", "TE"):
                assigned_player_ids.add(p.player_id)
                starters_assigned.append(
                    SlotAssignment(
                        slot_id=RosterSlot.OP,
                        slot_name="SUPERFLEX",
                        recommended_player=p,
                    )
                )
                sflex_assigned += 1

        # Sort starters strictly by canonical fantasy lineup slot order:
        # QB -> RB -> WR -> TE -> FLEX -> SUPERFLEX -> K -> D/ST
        starters_assigned.sort(key=lambda s: SLOT_ORDER.get(s.slot_name.upper(), 999))

        # Bench and IR allocation
        bench_slots_count = int(roster_slots_config.get("BE", roster_slots_config.get("BENCH", 7)))
        ir_slots_count = int(roster_slots_config.get("IR", 1))

        ir_players = [eval_by_id[pid] for pid in current_ir_ids if pid in eval_by_id and pid not in assigned_player_ids]
        bench_players = [
            p for p in available
            if p.player_id not in assigned_player_ids and p.player_id not in current_ir_ids
        ]
        # Sort bench players by StartScore descending
        bench_players.sort(key=lambda p: (not (p.opponent == "BYE" or p.projected_points <= 0), p.start_score), reverse=True)

        # 6. Evaluate diffs against current ESPN starting lineup with distinct replacement pairing
        current_starters_list = [eval_by_id[pid] for pid in current_starter_ids if pid in eval_by_id]
        current_espn_points = sum(p.projected_points for p in current_starters_list)

        diff_count = 0
        recommended_starter_ids = {s.recommended_player.player_id for s in starters_assigned}
        unpaired_benched = [p for p in current_starters_list if p.player_id not in recommended_starter_ids]

        for s in starters_assigned:
            rec_p = s.recommended_player
            # Check if this recommended starter is not in current starters
            if rec_p.player_id not in current_starter_ids:
                s.is_diff = True
                diff_count += 1
                # Find best matching benched starter by same position first
                matching_benched = next(
                    (p for p in unpaired_benched if p.position.upper() == rec_p.position.upper()),
                    None,
                )
                if not matching_benched and unpaired_benched:
                    matching_benched = unpaired_benched[0]

                if matching_benched:
                    unpaired_benched.remove(matching_benched)
                    s.current_starter = matching_benched
                    s.net_start_score_delta = round(rec_p.start_score - matching_benched.start_score, 1)
                    s.net_projected_delta = round(rec_p.projected_points - matching_benched.projected_points, 1)

        # 7. Detect Close Calls (starter vs bench player delta <= 2.5)
        close_calls: list[CloseCallPair] = []
        for s in starters_assigned:
            starter = s.recommended_player
            for b in bench_players:
                # Check eligibility
                is_eligible = (
                    b.position.upper() == starter.position.upper()
                    or (s.slot_name in ("FLEX", "SUPERFLEX") and b.position.upper() in ("RB", "WR", "TE"))
                )
                if not is_eligible:
                    continue

                delta = abs(starter.start_score - b.start_score)
                if delta <= 2.5:
                    comp = player_comparator.compare([starter, b])
                    close_calls.append(
                        CloseCallPair(
                            slot_name=s.slot_name,
                            starter=starter,
                            bench_player=b,
                            score_delta=round(delta, 1),
                            comparison=comp,
                        )
                    )

        # Check current ESPN lineup for tactical FLEX lock risk
        flex_timing_risk = False
        flex_timing_warning = None

        current_flex_starters = [
            eval_by_id[pid]
            for pid, slot_id in locked_starter_slot_map.items()
            if slot_id == RosterSlot.FLEX and pid in eval_by_id
        ]
        current_primary_starters = [
            eval_by_id[pid]
            for pid, slot_id in locked_starter_slot_map.items()
            if slot_id in (RosterSlot.RB, RosterSlot.WR, RosterSlot.TE) and pid in eval_by_id
        ]

        if current_flex_starters and current_primary_starters:
            earliest_flex = min(current_flex_starters, key=get_kickoff_timestamp)
            latest_primary = max(current_primary_starters, key=get_kickoff_timestamp)
            if get_kickoff_timestamp(earliest_flex) < get_kickoff_timestamp(latest_primary):
                flex_timing_risk = True
                flex_timing_warning = (
                    f"Tactical FLEX Lock Alert: Current starter {earliest_flex.full_name} is in FLEX but plays earlier than "
                    f"{latest_primary.full_name}. Move {earliest_flex.full_name} to your primary position slot to keep FLEX "
                    f"open for emergency Sunday/Monday pivot options."
                )

        total_opt_start_score = sum(s.recommended_player.start_score for s in starters_assigned)
        total_opt_proj = sum(s.recommended_player.projected_points for s in starters_assigned)
        net_gain = total_opt_proj - current_espn_points if current_espn_points > 0 else 0.0

        # Collect active QB+WR/TE correlation stacks
        active_stacks: list[str] = []
        if starting_qb:
            stacked_pass_catchers = [
                s.recommended_player
                for s in starters_assigned
                if s.recommended_player.player_id != starting_qb.player_id
                and s.recommended_player.pro_team == starting_qb.pro_team
                and s.recommended_player.position.upper() in ("WR", "TE")
            ]
            for pc in stacked_pass_catchers:
                active_stacks.append(
                    f"Boom Correlation Stack: {starting_qb.pro_team} QB {starting_qb.full_name} + {pc.position} {pc.full_name}"
                )

        total_model_pts = sum(s.recommended_player.proj_model for s in starters_assigned)
        total_fp_pts = sum(s.recommended_player.proj_fantasypros for s in starters_assigned)
        total_sleeper_pts = sum(s.recommended_player.proj_sleeper for s in starters_assigned)
        total_espn_pts = sum(s.recommended_player.proj_espn for s in starters_assigned)
        total_consensus_pts = sum(s.recommended_player.proj_consensus for s in starters_assigned)

        return OptimizedLineupResult(
            team_id=team_id,
            total_start_score=round(total_opt_start_score, 1),
            total_projected_points=round(total_opt_proj, 2),
            current_espn_projected=round(current_espn_points, 2),
            net_projected_gain=round(net_gain, 2),
            starters=starters_assigned,
            bench=bench_players,
            ir=ir_players,
            bench_slots_count=bench_slots_count,
            ir_slots_count=ir_slots_count,
            close_calls=close_calls,
            differences_count=diff_count,
            mode=mode_upper,
            projection_source=projection_source,
            total_model_projected=round(total_model_pts, 2),
            total_fp_projected=round(total_fp_pts, 2),
            total_sleeper_projected=round(total_sleeper_pts, 2),
            total_espn_projected=round(total_espn_pts, 2),
            total_consensus_projected=round(total_consensus_pts, 2),
            opponent_projected_points=opponent_projected_points,
            opponent_team_id=opponent_team_id,
            opponent_team_name=opponent_team_name,
            opponent_team_abbrev=opponent_team_abbrev,
            implied_matchup_spread=implied_spread,
            game_theory_posture=game_theory_posture,
            game_theory_recommendation=game_theory_rec,
            flex_timing_risk=flex_timing_risk,
            flex_timing_warning=flex_timing_warning,
            active_stacks=active_stacks,
        )



lineup_optimizer = LineupOptimizer()
