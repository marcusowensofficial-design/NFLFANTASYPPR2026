"""Expert Consensus Waiver Wire Intelligence Service for Week 2 of the 2026 NFL Season.

Aggregates internet-sourced expert consensus recommendations (FantasyPros, CBS Sports,
NFL.com, RotoBaller, FTN Fantasy, PFF, Athlon Sports, Sports Illustrated) across all 6
positions (QB, RB, WR, TE, D/ST, K), diagnoses individual team positional needs, and
recommends consensus targets tailored to those needs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PlayerModel, RosterEntryModel
from src.services.recommendation.scoring_engine import StartSitEvaluation

logger = logging.getLogger(__name__)

CONSENSUS_DATA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "waiver_expert_consensus_week_2_2026.json"


class ExpertConsensusPlayerItem(BaseModel):
    rank: int
    player_id: int | None = None
    full_name: str
    position: str
    pro_team: str
    consensus_tier: str  # "MUST_ADD", "PRIORITY_STARTER", "HIGH_PRIORITY", "STREAMING_LOCK", "CONTINGENT_HANDCUFF", "BENCH_STASH", "SPECULATIVE_STASH", "STREAMING_OPTION"
    faab_recommended_pct: int
    faab_range: str
    week_1_metric: str
    expert_rationale: str
    expert_sources: list[str] = Field(default_factory=list)
    is_available: bool = True
    availability_status: str = "AVAILABLE"  # "AVAILABLE", "ROSTERED_USER", "ROSTERED_OPPONENT"
    tailored_to_need: bool = False
    projected_points: float = 0.0


class PositionalNeedItem(BaseModel):
    position: str
    need_level: str  # "CRITICAL_NEED", "HIGH_NEED", "MODERATE_NEED", "LOW_NEED", "STABLE"
    need_score: float  # 0.0 to 100.0 (higher = more urgent need)
    primary_driver: str
    starter_summary: str
    recommended_consensus_targets: list[str] = Field(default_factory=list)


class ExpertConsensusWaiverService:
    """Manages Week 2 2026 expert consensus waiver data and team positional need analysis."""

    def __init__(self, data_path: Path | None = None) -> None:
        self.data_path = data_path or CONSENSUS_DATA_PATH
        self._cache: dict[str, Any] | None = None

    def load_consensus_data(self) -> dict[str, Any]:
        """Loads and caches the Week 2 2026 expert consensus dataset."""
        if self._cache is not None:
            return self._cache
        if not self.data_path.exists():
            logger.warning("Consensus file not found at %s. Using fallback empty dictionary.", self.data_path)
            return {"season": 2026, "week": 2, "positions": {}}
        try:
            with open(self.data_path, encoding="utf-8") as f:
                self._cache = json.load(f)
            return self._cache
        except Exception as e:
            logger.error("Error reading consensus data: %s", e)
            return {"season": 2026, "week": 2, "positions": {}}

    def ensure_consensus_players_in_db(self, db: Session) -> int:
        """Guarantees that all consensus players exist in the SQLite players table."""
        raw_data = self.load_consensus_data()
        pos_dict = raw_data.get("positions", {})
        added = 0

        # Deterministic fallback ESPN ID mappings for consensus players
        KNOWN_IDS: dict[str, int] = {
            "Mike Gesicki": 3116164,
            "Kendre Miller": 4429013,
            "Mack Hollins": 3045144,
            "Michael Mayer": 4430155,
            "David Njoku": 3123076,
            "Drew Lock": 3924327,
            "Tampa Bay Buccaneers D/ST": -16027,
            "Buccaneers D/ST": -16027,
            "San Francisco 49ers D/ST": -16025,
            "49ers D/ST": -16025,
            "Carolina Panthers D/ST": -16029,
            "Panthers D/ST": -16029,
            "Trey Smack": 4882123,
            "Chase McLaughlin": 3128429,
            "Kaelon Black": 4696044,
            "Tyler Allgeier": 4373626,
            "Woody Marks": 4429059,
            "Brian Robinson Jr.": 4241474,
            "Braelon Allen": 4685247,
            "Jonah Coleman": 4702555,
            "Zach Charbonnet": 4426385,
            "Chris Rodriguez Jr.": 4361579,
            "Jalen Coker": 4695883,
            "Devaughn Vele": 4569559,
            "Caleb Douglas": 4869645,
            "Deebo Samuel Sr.": 3126486,
            "Rashod Bateman": 4360939,
            "Tre' Harris": 4686612,
            "Dontayvion Wicks": 4428850,
            "Denzel Boston": 4832800,
            "Adonai Mitchell": 4597500,
            "Demarcus Robinson": 3045147,
            "Kendrick Bourne": 3043093,
            "Hunter Henry": 3046439,
            "Dalton Schultz": 3117256,
            "Pat Freiermuth": 4361411,
            "Brenton Strange": 4430539,
            "Kenyon Sadiq": 5083315,
            "Tyler Shough": 4360689,
            "Baker Mayfield": 3052587,
            "Jordan Love": 4036378,
            "Malik Willis": 4242512,
            "Bryce Young": 4685720,
            "Philadelphia Eagles D/ST": -16021,
            "Eagles D/ST": -16021,
            "Kansas City Chiefs D/ST": -16012,
            "Chiefs D/ST": -16012,
            "Cam Little": 4686361,
            "Ka'imi Fairbairn": 2971573,
            "Cameron Dicker": 4362081,
            "Cairo Santos": 17427,
            "Will Reichard": 4567104,
        }

        PROJECTIONS: dict[str, float] = {
            "Mike Gesicki": 9.8, "Kendre Miller": 7.5, "Mack Hollins": 8.8,
            "Michael Mayer": 8.5, "David Njoku": 8.7, "Drew Lock": 14.5,
            "Tampa Bay Buccaneers D/ST": 8.5, "San Francisco 49ers D/ST": 8.0,
            "Carolina Panthers D/ST": 6.5, "Trey Smack": 8.5, "Chase McLaughlin": 8.5,
            "Chris Rodriguez Jr.": 6.2, "Demarcus Robinson": 7.8, "Kendrick Bourne": 6.5,
        }

        for pos_key, p_list in pos_dict.items():
            for p_info in p_list:
                name = p_info["full_name"]
                pid = KNOWN_IDS.get(name) or (9900000 + abs(hash(name)) % 90000)
                # Check if exists by ID or name
                existing = db.execute(
                    select(PlayerModel).where((PlayerModel.id == pid) | (PlayerModel.full_name == name))
                ).scalars().first()
                if not existing:
                    proj = PROJECTIONS.get(name, 8.0)
                    p = PlayerModel(
                        id=pid,
                        full_name=name,
                        position=p_info["position"],
                        pro_team=p_info["pro_team"],
                        projected_points=proj,
                        projected_points_espn=proj,
                        injury_status="ACTIVE",
                    )
                    db.add(p)
                    added += 1

        if added > 0:
            try:
                db.commit()
                logger.info("Ensured %d consensus players seeded in PlayerModel.", added)
            except Exception as e:
                db.rollback()
                logger.error("Failed to commit seeded consensus players: %s", e)

        return added

    def analyze_team_positional_needs(
        self,
        user_roster_evaluations: list[StartSitEvaluation],
        league_size: int = 8,
    ) -> list[PositionalNeedItem]:
        """Diagnoses team roster health, injuries, projection gaps, and bench depth by position."""
        by_pos: dict[str, list[StartSitEvaluation]] = {
            "QB": [], "RB": [], "WR": [], "TE": [], "D/ST": [], "K": []
        }
        for e in user_roster_evaluations:
            pos = e.position.upper()
            if pos in ("DST", "D/ST"):
                by_pos["D/ST"].append(e)
            elif pos in ("PK", "K"):
                by_pos["K"].append(e)
            elif pos in ("FB", "RB"):
                by_pos["RB"].append(e)
            elif pos in by_pos:
                by_pos[pos].append(e)

        needs: list[PositionalNeedItem] = []

        # 1. Tight End (TE) Diagnosis
        tes = by_pos["TE"]
        out_tes = [t for t in tes if t.injury_status in ("OUT", "IR", "INJURY_RESERVE")]
        questionable_tes = [t for t in tes if t.injury_status in ("QUESTIONABLE", "DOUBTFUL")]
        healthy_tes = [t for t in tes if t.injury_status not in ("OUT", "IR", "INJURY_RESERVE", "QUESTIONABLE", "DOUBTFUL")]
        healthy_tes.sort(key=lambda x: x.start_score, reverse=True)

        if out_tes and (not healthy_tes or healthy_tes[0].projected_points < 11.0):
            inj_names = ", ".join(f"{t.full_name} ({t.injury_status})" for t in out_tes)
            starter_proj = f"{healthy_tes[0].full_name} ({healthy_tes[0].projected_points:.1f} pts)" if healthy_tes else "None"
            needs.append(
                PositionalNeedItem(
                    position="TE",
                    need_level="CRITICAL_NEED",
                    need_score=95.0,
                    primary_driver=f"Emergency Injury Alert: {inj_names}. Active backup {starter_proj} sits below elite 8-team baseline.",
                    starter_summary=f"Starter Out: {starter_proj}. Scarcity demands an immediate consensus add.",
                    recommended_consensus_targets=["Mike Gesicki", "Hunter Henry", "Michael Mayer"],
                )
            )
        elif questionable_tes and (not healthy_tes or healthy_tes[0].projected_points < 10.0):
            q_names = ", ".join(f"{t.full_name} ({t.injury_status})" for t in questionable_tes)
            backup_summary = f"{healthy_tes[0].full_name} ({healthy_tes[0].projected_points:.1f} pts)" if healthy_tes else "No healthy backup"
            needs.append(
                PositionalNeedItem(
                    position="TE",
                    need_level="HIGH_NEED",
                    need_score=88.0,
                    primary_driver=f"Injury Volatility Alert: {q_names} is questionable with a knee ailment. Backup {backup_summary} lacks ceiling in an 8-team format.",
                    starter_summary=f"Questionable Starter: {q_names}. Stashing Mike Gesicki or Hunter Henry is strongly advised.",
                    recommended_consensus_targets=["Mike Gesicki", "Hunter Henry", "Michael Mayer"],
                )
            )
        elif not tes or (healthy_tes and healthy_tes[0].start_score < 70.0):
            needs.append(
                PositionalNeedItem(
                    position="TE",
                    need_level="HIGH_NEED",
                    need_score=80.0,
                    primary_driver="Tight end volume deficit: Starter lacks a top-tier target share or red-zone role.",
                    starter_summary=f"Top TE: {healthy_tes[0].full_name if healthy_tes else 'Vacant'} ({healthy_tes[0].projected_points if healthy_tes else 0:.1f} pts).",
                    recommended_consensus_targets=["Mike Gesicki", "Hunter Henry", "Dalton Schultz"],
                )
            )
        else:
            top_healthy = healthy_tes[0] if healthy_tes else (tes[0] if tes else None)
            needs.append(
                PositionalNeedItem(
                    position="TE",
                    need_level="STABLE",
                    need_score=25.0,
                    primary_driver="Solid tight end baseline with reliable weekly route participation.",
                    starter_summary=f"Starter: {top_healthy.full_name if top_healthy else 'None'} ({top_healthy.projected_points if top_healthy else 0:.1f} pts).",
                    recommended_consensus_targets=["Mike Gesicki"],
                )
            )

        # 2. Wide Receiver (WR) Diagnosis
        wrs = by_pos["WR"]
        wrs.sort(key=lambda x: x.start_score, reverse=True)
        weak_bench_wrs = [w for w in wrs if w.start_score < 56.0 or w.projected_points < 11.5]
        top_wr_proj = wrs[0].projected_points if wrs else 0.0

        if weak_bench_wrs:
            drop_names = ", ".join(w.full_name for w in weak_bench_wrs[:2])
            needs.append(
                PositionalNeedItem(
                    position="WR",
                    need_level="HIGH_NEED",
                    need_score=82.0,
                    primary_driver=f"Low-ceiling bench depth ({drop_names}) provides zero leverage in an 8-team league. Upgrade to Week 1 breakout alphas.",
                    starter_summary=f"Starters: {wrs[0].full_name if wrs else 'N/A'}, {wrs[1].full_name if len(wrs) > 1 else 'N/A'} (Solid starting core, but expendable bench depth).",
                    recommended_consensus_targets=["Jalen Coker", "Devaughn Vele", "Caleb Douglas", "Mack Hollins"],
                )
            )
        elif len(wrs) < 5:
            needs.append(
                PositionalNeedItem(
                    position="WR",
                    need_level="MODERATE_NEED",
                    need_score=68.0,
                    primary_driver="Thin receiver depth across flex positions for upcoming bye weeks and injuries.",
                    starter_summary=f"Top WR: {wrs[0].full_name if wrs else 'N/A'}.",
                    recommended_consensus_targets=["Jalen Coker", "Devaughn Vele"],
                )
            )
        else:
            needs.append(
                PositionalNeedItem(
                    position="WR",
                    need_level="LOW_NEED",
                    need_score=35.0,
                    primary_driver="Deep receiver corps with multiple starter-caliber assets.",
                    starter_summary=f"Anchors: {wrs[0].full_name}, {wrs[1].full_name if len(wrs) > 1 else 'N/A'}.",
                    recommended_consensus_targets=["Jalen Coker"],
                )
            )

        # 3. Running Back (RB) Diagnosis
        rbs = by_pos["RB"]
        rbs.sort(key=lambda x: x.start_score, reverse=True)
        handcuff_rbs = [r for r in rbs if getattr(r, "contingency_score", 0.0) >= 65.0 or r.projected_points < 12.0]

        if len(rbs) < 4 or len(handcuff_rbs) == 0:
            needs.append(
                PositionalNeedItem(
                    position="RB",
                    need_level="HIGH_NEED",
                    need_score=78.0,
                    primary_driver="Contingency vulnerability: Roster lacks elite workhorse handcuffs who inherit 18+ touches upon injury.",
                    starter_summary=f"Starters: {rbs[0].full_name if rbs else 'N/A'}, {rbs[1].full_name if len(rbs) > 1 else 'N/A'} (Elite starting production, but low bench contingency).",
                    recommended_consensus_targets=["Kaelon Black", "Tyler Allgeier", "Kendre Miller"],
                )
            )
        else:
            needs.append(
                PositionalNeedItem(
                    position="RB",
                    need_level="MODERATE_NEED",
                    need_score=55.0,
                    primary_driver="Strong starting running back foundation. High-priority target is acquiring consensus #1 add Kaelon Black for championship ceiling.",
                    starter_summary=f"Anchors: {rbs[0].full_name} ({rbs[0].projected_points:.1f} pts), {rbs[1].full_name if len(rbs) > 1 else 'N/A'}.",
                    recommended_consensus_targets=["Kaelon Black", "Tyler Allgeier"],
                )
            )

        # 4. Quarterback (QB) Diagnosis
        qbs = by_pos["QB"]
        qbs.sort(key=lambda x: x.start_score, reverse=True)
        if not qbs or (qbs and qbs[0].start_score < 72.0) or (qbs and qbs[0].injury_status in ("OUT", "IR", "DOUBTFUL")):
            needs.append(
                PositionalNeedItem(
                    position="QB",
                    need_level="HIGH_NEED",
                    need_score=85.0,
                    primary_driver="Quarterback output lagging behind league median or starter injured. Tyler Shough provides an immediate ceiling surge.",
                    starter_summary=f"Current: {qbs[0].full_name if qbs else 'None'}.",
                    recommended_consensus_targets=["Tyler Shough", "Baker Mayfield", "Jordan Love"],
                )
            )
        elif len(qbs) == 1 and qbs[0].start_score >= 80.0 and qbs[0].injury_status not in ("OUT", "IR", "QUESTIONABLE"):
            needs.append(
                PositionalNeedItem(
                    position="QB",
                    need_level="STABLE",
                    need_score=15.0,
                    primary_driver=f"Single-QB roster anchored by elite healthy starter {qbs[0].full_name} ({qbs[0].projected_points:.1f} pts). Zero waiver urgency at QB in shallow league.",
                    starter_summary=f"Elite Starter: {qbs[0].full_name} ({qbs[0].pro_team}).",
                    recommended_consensus_targets=["Tyler Shough"],
                )
            )
        else:
            needs.append(
                PositionalNeedItem(
                    position="QB",
                    need_level="STABLE",
                    need_score=20.0,
                    primary_driver=f"Secure quarterback room with {qbs[0].full_name}.",
                    starter_summary=f"Starter: {qbs[0].full_name}.",
                    recommended_consensus_targets=["Tyler Shough"],
                )
            )

        # 5. Defense / Special Teams (D/ST) Diagnosis
        dsts = by_pos["D/ST"]
        if not dsts or (dsts and dsts[0].matchup_grade in ("TOUGH", "AVOID") or dsts[0].projected_points < 7.5):
            needs.append(
                PositionalNeedItem(
                    position="D/ST",
                    need_level="MODERATE_NEED",
                    need_score=62.0,
                    primary_driver="Streaming opportunity: Tampa Bay draws Deshaun Watson & Browns, offering higher turnover and sack upside.",
                    starter_summary=f"Current: {dsts[0].full_name if dsts else 'None'} ({dsts[0].projected_points if dsts else 0:.1f} pts).",
                    recommended_consensus_targets=["Tampa Bay Buccaneers D/ST", "San Francisco 49ers D/ST"],
                )
            )
        else:
            needs.append(
                PositionalNeedItem(
                    position="D/ST",
                    need_level="LOW_NEED",
                    need_score=30.0,
                    primary_driver=f"Rostered unit {dsts[0].full_name} has a viable Week 2 matchup.",
                    starter_summary=f"Starter: {dsts[0].full_name}.",
                    recommended_consensus_targets=["Tampa Bay Buccaneers D/ST"],
                )
            )

        # 6. Kicker (K) Diagnosis
        ks = by_pos["K"]
        if not ks or (ks and ks[0].implied_team_total < 21.0 or ks[0].matchup_grade in ("TOUGH", "AVOID")):
            needs.append(
                PositionalNeedItem(
                    position="K",
                    need_level="MODERATE_NEED",
                    need_score=52.0,
                    primary_driver="Kicker streaming upgrade: Target Cam Little or Ka'imi Fairbairn in high-total/dome venues.",
                    starter_summary=f"Current: {ks[0].full_name if ks else 'None'} ({ks[0].projected_points if ks else 0:.1f} pts).",
                    recommended_consensus_targets=["Cam Little", "Ka'imi Fairbairn"],
                )
            )
        else:
            needs.append(
                PositionalNeedItem(
                    position="K",
                    need_level="LOW_NEED",
                    need_score=25.0,
                    primary_driver=f"Steady kicker option {ks[0].full_name} in favorable scoring environment.",
                    starter_summary=f"Starter: {ks[0].full_name}.",
                    recommended_consensus_targets=["Cam Little"],
                )
            )

        # Sort needs by urgency descending
        needs.sort(key=lambda x: x.need_score, reverse=True)
        return needs

    def get_consensus_board_with_availability(
        self,
        db: Session,
        league_id: int,
        user_team_id: int,
        positional_needs: list[PositionalNeedItem],
    ) -> dict[str, list[ExpertConsensusPlayerItem]]:
        """Cross-references expert consensus players with league ownership and team needs."""
        raw_data = self.load_consensus_data()
        pos_dict = raw_data.get("positions", {})

        # Build set of needed positions (scores >= 65.0)
        needed_positions = {n.position.upper() for n in positional_needs if n.need_score >= 65.0}

        # Query all rostered players in this league
        rostered_rows = db.execute(
            select(RosterEntryModel.player_id, RosterEntryModel.team_id, PlayerModel.full_name)
            .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
            .where(RosterEntryModel.league_id == league_id)
        ).all()
        rostered_pids: dict[int, int] = {r[0]: r[1] for r in rostered_rows}
        rostered_names: dict[str, int] = {r[2].lower(): r[1] for r in rostered_rows}

        # Query all players in DB for ID and projection lookup
        all_db_players = db.execute(select(PlayerModel)).scalars().all()
        db_by_name: dict[str, PlayerModel] = {}
        for p in all_db_players:
            db_by_name[p.full_name.lower()] = p
            # Also store normalized without punctuation
            clean_name = p.full_name.replace("'", "").replace(".", "").lower()
            db_by_name[clean_name] = p

        result: dict[str, list[ExpertConsensusPlayerItem]] = {}

        for pos_key, p_list in pos_dict.items():
            ui_pos = "D/ST" if pos_key in ("DST", "D/ST") else pos_key
            result_list: list[ExpertConsensusPlayerItem] = []

            for p_data in p_list:
                full_name = p_data["full_name"]
                name_lower = full_name.lower()
                clean_name = name_lower.replace("'", "").replace(".", "")

                db_player = db_by_name.get(name_lower) or db_by_name.get(clean_name)
                player_id = db_player.id if db_player else None
                proj = db_player.projected_points if db_player else 0.0

                # Determine availability
                team_holding = None
                if player_id and player_id in rostered_pids:
                    team_holding = rostered_pids[player_id]
                elif name_lower in rostered_names:
                    team_holding = rostered_names[name_lower]
                elif clean_name in rostered_names:
                    team_holding = rostered_names[clean_name]

                if team_holding == user_team_id:
                    avail_status = "ROSTERED_USER"
                    is_avail = False
                elif team_holding is not None:
                    avail_status = "ROSTERED_OPPONENT"
                    is_avail = False
                else:
                    avail_status = "AVAILABLE"
                    is_avail = True

                is_tailored = (ui_pos in needed_positions or pos_key in needed_positions) and (p_data.get("rank", 99) <= 3)

                item = ExpertConsensusPlayerItem(
                    rank=p_data["rank"],
                    player_id=player_id,
                    full_name=full_name,
                    position=p_data["position"],
                    pro_team=p_data["pro_team"],
                    consensus_tier=p_data["consensus_tier"],
                    faab_recommended_pct=p_data["faab_recommended_pct"],
                    faab_range=p_data["faab_range"],
                    week_1_metric=p_data["week_1_metric"],
                    expert_rationale=p_data["expert_rationale"],
                    expert_sources=p_data.get("expert_sources", []),
                    is_available=is_avail,
                    availability_status=avail_status,
                    tailored_to_need=is_tailored,
                    projected_points=round(proj, 1),
                )
                result_list.append(item)

            result[ui_pos] = result_list

        return result


expert_consensus_service = ExpertConsensusWaiverService()
