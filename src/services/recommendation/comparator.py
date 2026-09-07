"""Multi-player Start/Sit comparator (2-4 players) with head-to-head factor delta breakdown."""

from pydantic import BaseModel
from src.services.recommendation.scoring_engine import StartSitEvaluation


class ComparisonResult(BaseModel):
    recommended_player_id: int
    recommended_player_name: str
    is_close_call: bool
    score_delta: float
    headline: str
    detailed_rationale: str
    players: list[StartSitEvaluation]


class PlayerComparator:
    """Compares 2 to 4 players side-by-side with explainable head-to-head rationale."""

    def compare(self, evaluations: list[StartSitEvaluation]) -> ComparisonResult:
        if not evaluations:
            raise ValueError("Must provide at least one player evaluation to compare.")

        # Sort descending by StartScore
        ranked = sorted(evaluations, key=lambda x: x.start_score, reverse=True)
        winner = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else None

        if not runner_up:
            return ComparisonResult(
                recommended_player_id=winner.player_id,
                recommended_player_name=winner.full_name,
                is_close_call=False,
                score_delta=0.0,
                headline=f"Start {winner.full_name}",
                detailed_rationale=f"{winner.full_name} is the sole candidate evaluated.",
                players=ranked,
            )

        delta = round(winner.start_score - runner_up.start_score, 1)
        is_close = delta <= 2.5

        # Formulate concise, factual comparison rationale
        reasons: list[str] = []
        if winner.projected_points > runner_up.projected_points:
            reasons.append(f"higher projected PPR points ({winner.projected_points:.1f} vs {runner_up.projected_points:.1f})")
        elif runner_up.projected_points > winner.projected_points:
            reasons.append(f"despite {runner_up.full_name}'s higher raw projection ({runner_up.projected_points:.1f} vs {winner.projected_points:.1f})")

        # Full PPR Target Volume & Share comparison
        w_stats = winner.itemized_stats or {}
        r_stats = runner_up.itemized_stats or {}
        w_tgts = float(w_stats.get("targets", 0.0))
        r_tgts = float(r_stats.get("targets", 0.0))
        if w_tgts >= r_tgts + 2.0 and w_tgts >= 5.0:
            reasons.append(f"superior full-PPR target volume ({w_tgts:.1f} vs {r_tgts:.1f} tgts)")
        elif r_tgts >= w_tgts + 2.0 and r_tgts >= 5.0:
            reasons.append(f"despite {runner_up.full_name}'s higher target volume ({r_tgts:.1f} vs {w_tgts:.1f} tgts)")

        if winner.volume_share and runner_up.volume_share and winner.volume_share >= runner_up.volume_share + 5.0:
            reasons.append(f"heavier offensive workload share ({winner.volume_share:.1f}% vs {runner_up.volume_share:.1f}%)")

        # Red zone & TD equity
        w_tds = float(w_stats.get("rush_td", 0.0)) + float(w_stats.get("rec_td", 0.0))
        r_tds = float(r_stats.get("rush_td", 0.0)) + float(r_stats.get("rec_td", 0.0))
        if w_tds >= r_tds + 0.25 and w_tds >= 0.50:
            reasons.append(f"superior red-zone TD equity ({w_tds:.2f} vs {r_tds:.2f} TDs)")

        # Expert consensus tier advantage
        if winner.fp_tier and runner_up.fp_tier and winner.fp_tier < runner_up.fp_tier:
            reasons.append(f"higher consensus expert tier (Tier {winner.fp_tier} vs Tier {runner_up.fp_tier})")
        elif winner.consensus_rank and runner_up.consensus_rank and runner_up.consensus_rank >= winner.consensus_rank + 6.0:
            reasons.append(f"higher expert consensus rank (#{int(winner.consensus_rank)} vs #{int(runner_up.consensus_rank)})")

        if winner.components.health_score > runner_up.components.health_score:
            reasons.append(f"cleaner health profile ({winner.injury_status} vs {runner_up.injury_status})")

        if winner.components.matchup_score > runner_up.components.matchup_score:
            reasons.append(f"more favorable positional matchup ({winner.matchup_grade} vs {runner_up.matchup_grade})")

        if winner.components.environment_score > runner_up.components.environment_score:
            reasons.append(f"higher-scoring offensive environment (Team implied: {winner.implied_team_total} vs {runner_up.implied_team_total})")

        if winner.ceiling_score > runner_up.ceiling_score + 3.0:
            reasons.append(f"superior 90th-percentile ceiling ({winner.ceiling_score:.1f} vs {runner_up.ceiling_score:.1f})")

        if winner.floor_score > runner_up.floor_score + 3.0:
            reasons.append(f"safer touch floor ({winner.floor_score:.1f} vs {runner_up.floor_score:.1f})")

        reason_str = ", ".join(reasons) if reasons else "higher overall composite opportunity"

        # Special game-theory callout if runner-up has higher ceiling
        upside_note = ""
        if runner_up.ceiling_score > winner.ceiling_score + 2.5:
            upside_note = (
                f" Game Theory Note: {runner_up.full_name} carries a higher 90th-percentile ceiling "
                f"({runner_up.ceiling_score:.1f} vs {winner.ceiling_score:.1f}) — consider starting if you are a heavy weekly underdog."
            )
        elif runner_up.floor_score > winner.floor_score + 2.5:
            upside_note = (
                f" Game Theory Note: {runner_up.full_name} has a slightly safer floor "
                f"({runner_up.floor_score:.1f} vs {winner.floor_score:.1f}) if seeking to protect a lead as a heavy favorite."
            )

        if is_close:
            headline = f"TOSS-UP: Edge to {winner.full_name} over {runner_up.full_name} (+{delta} pts)"
            detailed = (
                f"This is a razor-thin decision separated by only {delta} StartScore points. "
                f"We give the slight nod to {winner.full_name} due to {reason_str}. "
                f"In an 8-team league where every roster is loaded, check late inactives before locking.{upside_note}"
            )
        else:
            headline = f"START {winner.full_name} over {runner_up.full_name} (+{delta} pts)"
            detailed = (
                f"Strong recommendation to start {winner.full_name} ({winner.start_score:.1f}) "
                f"over {runner_up.full_name} ({runner_up.start_score:.1f}). "
                f"Key drivers: {reason_str}.{upside_note}"
            )

        return ComparisonResult(
            recommended_player_id=winner.player_id,
            recommended_player_name=winner.full_name,
            is_close_call=is_close,
            score_delta=delta,
            headline=headline,
            detailed_rationale=detailed,
            players=ranked,
        )


player_comparator = PlayerComparator()
