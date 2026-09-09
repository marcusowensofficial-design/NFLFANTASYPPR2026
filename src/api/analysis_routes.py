"""API routes for advanced matchup intelligence (WR/CB Matrix, Vegas Game Script Environments, and Live Depth Charts)."""

import logging
import math
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.betting.props_client import PlayerPropsData, vegas_props_client
from src.adapters.borischen.client import BorisChenTierItem, boris_chen_client
from src.adapters.nfl.depthchart_client import TeamDepthChart, nfl_depthchart_client
from src.adapters.nfl.dvp_client import dvp_client
from src.adapters.nfl.injuries_client import nfl_injuries_client
from src.adapters.nfl.schedule_client import nfl_schedule_client
from src.core.config import settings
from src.services.market.sentiment_service import PlayerMarketSentiment, market_sentiment_service
from src.db.models import LeagueModel, MatchupModel, PlayerModel, RosterEntryModel, TeamModel
from src.db.session import get_db
from src.services.matchup.vegas_gamescript import (
    VegasIntelligenceResponse,
    vegas_gamescript_analyzer,
)
from src.services.matchup.wrcb_matrix import (
    WRCBMatchupAnalysis,
    wrcb_analyzer,
)
from src.services.optimizer.lineup_optimizer import SLOT_ORDER
from src.services.recommendation.scoring_engine import scoring_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["Matchup Intel"])


class TaleOfTheTapeSlot(BaseModel):
    slot_name: str
    position: str
    user_player: dict[str, Any]
    opp_player: dict[str, Any]
    point_delta: float
    advantage: str  # USER, OPPONENT, EVEN
    leverage_label: str


class OpponentVulnerabilityItem(BaseModel):
    player_id: int
    player_name: str
    position: str
    pro_team: str
    slot_name: str
    projected_points: float
    injury_status: str
    vulnerability_type: str
    severity: str
    description: str


class SharedGameCorrelation(BaseModel):
    game_matchup: str
    user_players: list[str]
    opp_players: list[str]
    correlation_type: str
    strategic_takeaway: str


class OpponentScoutingReport(BaseModel):
    week: int
    user_team_id: int
    user_team_name: str
    user_projected_total: float
    opp_team_id: int
    opp_team_name: str
    opp_primary_owner: str | None = None
    opp_projected_total: float
    spread: float
    win_probability: float
    recommended_stance: str
    stance_headline: str
    stance_rationale: str
    vulnerabilities: list[OpponentVulnerabilityItem]
    correlations: list[SharedGameCorrelation]
    head_to_head_slots: list[TaleOfTheTapeSlot]
    key_action_items: list[str]


class H2HTaleOfTheTapeResponse(BaseModel):
    week: int
    user_team_name: str
    user_team_id: int
    user_projected_total: float
    opp_team_name: str
    opp_team_id: int
    opp_projected_total: float
    spread: float
    posture: str
    slots: list[TaleOfTheTapeSlot]
    key_leverage_summary: str



@router.get("/opponent-scouting", response_model=OpponentScoutingReport)
async def get_opponent_scouting(
    team_id: int | None = Query(default=None, description="User team ID (defaults to active user team)"),
    week: int | None = Query(default=None, description="Matchup week (defaults to league current week)"),
    db: Session = Depends(get_db),
) -> OpponentScoutingReport:
    """Analyze weekly head-to-head opponent starting lineup, pinpoint vulnerabilities, identify shared game correlation hedges, and prescribe AI game-theory stance."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    if not league:
        raise HTTPException(status_code=404, detail="No active league found in database.")

    target_week = week if (week and week > 0) else (league.current_week or 1)
    target_team_id = team_id or league.user_team_id or 1

    # Find matchup for this week involving target team
    matchup = db.execute(
        select(MatchupModel).where(
            MatchupModel.league_id == league.id,
            MatchupModel.week == target_week,
            (MatchupModel.home_team_id == target_team_id) | (MatchupModel.away_team_id == target_team_id),
        )
    ).scalars().first()

    if not matchup:
        # Fallback: pick any other team in the league
        other_team = db.execute(
            select(TeamModel).where(TeamModel.league_id == league.id, TeamModel.id != target_team_id)
        ).scalars().first()
        opp_team_id = other_team.id if other_team else 2
    else:
        opp_team_id = matchup.away_team_id if matchup.home_team_id == target_team_id else matchup.home_team_id

    # Retrieve teams
    user_team = db.execute(
        select(TeamModel).where(TeamModel.id == target_team_id, TeamModel.league_id == league.id)
    ).scalar_one_or_none()
    opp_team = db.execute(
        select(TeamModel).where(TeamModel.id == opp_team_id, TeamModel.league_id == league.id)
    ).scalar_one_or_none()

    user_team_name = user_team.name if user_team else f"Team {target_team_id}"
    opp_team_name = opp_team.name if opp_team else f"Team {opp_team_id}"
    opp_owner = opp_team.primary_owner if opp_team else None

    # Retrieve active starters
    user_entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == target_team_id,
            RosterEntryModel.is_starter == True,
        )
        .order_by(RosterEntryModel.lineup_slot_id)
    ).all()

    opp_entries = db.execute(
        select(RosterEntryModel, PlayerModel)
        .join(PlayerModel, RosterEntryModel.player_id == PlayerModel.id)
        .where(
            RosterEntryModel.league_id == league.id,
            RosterEntryModel.team_id == opp_team_id,
            RosterEntryModel.is_starter == True,
        )
        .order_by(RosterEntryModel.lineup_slot_id)
    ).all()

    # Sort in standard fantasy order
    user_entries_sorted = sorted(user_entries, key=lambda pair: (SLOT_ORDER.get(pair[0].slot_name.upper(), 99), -pair[1].projected_points))
    opp_entries_sorted = sorted(opp_entries, key=lambda pair: (SLOT_ORDER.get(pair[0].slot_name.upper(), 99), -pair[1].projected_points))

    user_proj_total = round(sum(p.projected_points for _, p in user_entries_sorted), 1)
    opp_proj_total = round(sum(p.projected_points for _, p in opp_entries_sorted), 1)
    spread = round(user_proj_total - opp_proj_total, 1)

    # Calculate Win Probability via logistic distribution calibrated to 12 pt fantasy standard deviation
    win_probability = round(1.0 / (1.0 + math.exp(-spread / 12.0)) * 100, 1)

    # Strategic Stance & Posture
    if spread >= 7.0:
        recommended_stance = "FLOOR"
        stance_headline = f"Heavily Favored (+{spread} pts) — Secure Safe Touch Floor"
        stance_rationale = (
            f"You hold an estimated +{spread} point projected lead over {opp_team_name}. "
            "Mitigate outcome variance by benching volatile boom/bust darts in favor of high-floor route earners and goal-line touch anchors."
        )
    elif spread <= -6.0:
        recommended_stance = "CEILING"
        stance_headline = f"Projected Underdog ({spread} pts) — Deploy High-Ceiling Upside"
        stance_rationale = (
            f"You are projected {abs(spread)} points behind {opp_team_name}. "
            "To overcome this deficit, activate Ceiling Mode to prioritize high-total shootout environments, deep air-yards, and explosive touchdown equity."
        )
    else:
        recommended_stance = "BALANCED"
        stance_headline = f"Competitive Matchup ({'+' if spread > 0 else ''}{spread} pts) — Optimize Sharpe Efficiency"
        stance_rationale = (
            "This matchup is projected within a single touchdown. "
            "Start your highest-ranked overall StartScore players to maximize risk-adjusted point expectation."
        )

    # Pinpoint Opponent Vulnerabilities
    vulnerabilities: list[OpponentVulnerabilityItem] = []
    for re, p in opp_entries_sorted:
        raw_status = (p.injury_status or "ACTIVE").upper()
        if raw_status in ("QUESTIONABLE", "DOUBTFUL"):
            vulnerabilities.append(
                OpponentVulnerabilityItem(
                    player_id=p.id,
                    player_name=p.full_name,
                    position=p.position,
                    pro_team=p.pro_team,
                    slot_name=re.slot_name,
                    projected_points=p.projected_points,
                    injury_status=raw_status,
                    vulnerability_type="INJURY_RISK",
                    severity="HIGH" if raw_status == "DOUBTFUL" else "MODERATE",
                    description=f"Carries {raw_status} status. Elevated in-game re-injury or snap-count limitation risk.",
                )
            )

        # Check DvP ratings
        # Check DvP ratings directly from database
        try:
            from src.db.models import DefenseVsPositionModel
            dvp_row = db.execute(
                select(DefenseVsPositionModel).where(
                    DefenseVsPositionModel.pro_team == p.pro_team.upper().strip(),
                    DefenseVsPositionModel.position == p.position.upper().strip(),
                )
            ).scalars().first()
            if dvp_row and dvp_row.rank <= 8:
                vulnerabilities.append(
                    OpponentVulnerabilityItem(
                        player_id=p.id,
                        player_name=p.full_name,
                        position=p.position,
                        pro_team=p.pro_team,
                        slot_name=re.slot_name,
                        projected_points=p.projected_points,
                        injury_status=raw_status,
                        vulnerability_type="TOUGH_DVP",
                        severity="MODERATE",
                        description=f"Faces #{dvp_row.rank} defense vs {p.position} ({dvp_row.matchup_grade}). Restricted fantasy scoring environment.",
                    )
                )
        except Exception:
            pass

    # Detect Shared Game Correlations & Hedges
    correlations: list[SharedGameCorrelation] = []
    user_team_map: dict[str, list[str]] = {}
    for _, p in user_entries_sorted:
        user_team_map.setdefault(p.pro_team.upper().strip(), []).append(f"{p.full_name} ({p.position})")

    opp_team_map: dict[str, list[str]] = {}
    for _, p in opp_entries_sorted:
        opp_team_map.setdefault(p.pro_team.upper().strip(), []).append(f"{p.full_name} ({p.position})")

    # Direct same-NFL-team overlap check (instant)
    for pro_team, u_players in user_team_map.items():
        if pro_team in opp_team_map and pro_team != "FA":
            correlations.append(
                SharedGameCorrelation(
                    game_matchup=f"{pro_team} Team Stack",
                    user_players=u_players,
                    opp_players=opp_team_map[pro_team],
                    correlation_type="SAME_TEAM_OPPONENT",
                    strategic_takeaway=f"Both managers start assets on {pro_team}. Scoring events directly cannibalize ceiling expectations between you.",
                )
            )

    # Fast schedule check with timeout guard
    try:
        import asyncio
        sched = await asyncio.wait_for(
            nfl_schedule_client.fetch_week_schedule(season=league.season, week=target_week),
            timeout=0.6,
        )
        for game in sched:
            h = game.home_team.upper().strip()
            a = game.away_team.upper().strip()
            user_in_game = user_team_map.get(h, []) + user_team_map.get(a, [])
            opp_in_game = opp_team_map.get(h, []) + opp_team_map.get(a, [])

            if user_in_game and opp_in_game and h != a:
                already_covered = any(c.game_matchup == f"{a} @ {h}" for c in correlations)
                if not already_covered:
                    correlations.append(
                        SharedGameCorrelation(
                            game_matchup=f"{a} @ {h}",
                            user_players=user_in_game,
                            opp_players=opp_in_game,
                            correlation_type="OPPOSING_SHOOTOUT",
                            strategic_takeaway=f"Cross-matchup in {a} @ {h}. High pace and scoring directly lifts projected totals for both teams.",
                        )
                    )
    except Exception:
        pass

    # Head-to-Head Positional Slots comparison
    h2h_slots: list[TaleOfTheTapeSlot] = []
    max_slots = max(len(user_entries_sorted), len(opp_entries_sorted))
    for i in range(max_slots):
        u_pair = user_entries_sorted[i] if i < len(user_entries_sorted) else None
        o_pair = opp_entries_sorted[i] if i < len(opp_entries_sorted) else None

        u_p = u_pair[1] if u_pair else None
        u_re = u_pair[0] if u_pair else None
        o_p = o_pair[1] if o_pair else None
        o_re = o_pair[0] if o_pair else None

        slot_name = (u_re.slot_name if u_re else (o_re.slot_name if o_re else f"Slot {i+1}"))
        pos_name = (u_p.position if u_p else (o_p.position if o_p else "FLEX"))

        u_pts = u_p.projected_points if u_p else 0.0
        o_pts = o_p.projected_points if o_p else 0.0
        p_delta = round(u_pts - o_pts, 1)

        if p_delta > 1.5:
            adv = "USER"
            lev = f"+{p_delta} pts advantage"
        elif p_delta < -1.5:
            adv = "OPPONENT"
            lev = f"{p_delta} pts disadvantage"
        else:
            adv = "EVEN"
            lev = "Even matchup"

        h2h_slots.append(
            TaleOfTheTapeSlot(
                slot_name=slot_name,
                position=pos_name,
                user_player={
                    "id": u_p.id if u_p else 0,
                    "player_id": u_p.id if u_p else 0,
                    "name": u_p.full_name if u_p else "Empty Slot",
                    "full_name": u_p.full_name if u_p else "Empty Slot",
                    "position": pos_name,
                    "pro_team": u_p.pro_team if u_p else "—",
                    "opponent": "VS",
                    "projected_points": u_pts,
                    "opp_dvp_rank": 16,
                    "matchup_stars": 3,
                    "matchup_grade": "C",
                    "injury_status": u_p.injury_status if u_p else "ACTIVE",
                },
                opp_player={
                    "id": o_p.id if o_p else 0,
                    "player_id": o_p.id if o_p else 0,
                    "name": o_p.full_name if o_p else "Empty Slot",
                    "full_name": o_p.full_name if o_p else "Empty Slot",
                    "position": pos_name,
                    "pro_team": o_p.pro_team if o_p else "—",
                    "opponent": "VS",
                    "projected_points": o_pts,
                    "opp_dvp_rank": 16,
                    "matchup_stars": 3,
                    "matchup_grade": "C",
                    "injury_status": o_p.injury_status if o_p else "ACTIVE",
                },
                point_delta=p_delta,
                advantage=adv,
                leverage_label=lev,
            )
        )

    # Synthesize actionable prescriptions
    key_actions = []
    if spread >= 7.0:
        key_actions.append(f"Run Floor Mode: Lock in your +{spread} pt edge by prioritizing high-snap, high-carry running backs.")
    elif spread <= -6.0:
        key_actions.append(f"Run Ceiling Mode: Overcome your {abs(spread)} pt deficit by deploying high-air-yards boom wideouts.")
    else:
        key_actions.append("Run Balanced Mode: Point projection is razor-close; optimize overall StartScore efficiency.")

    if len(vulnerabilities) > 0:
        key_actions.append(f"Target Opponent Weakness: {vulnerabilities[0].player_name} ({vulnerabilities[0].position}) is compromised ({vulnerabilities[0].description}).")

    if len(correlations) > 0:
        key_actions.append(f"Game Correlation In Play: Monitor {correlations[0].game_matchup}; live game script directly impacts both teams.")

    return OpponentScoutingReport(
        week=target_week,
        user_team_id=target_team_id,
        user_team_name=user_team_name,
        user_projected_total=user_proj_total,
        opp_team_id=opp_team_id,
        opp_team_name=opp_team_name,
        opp_primary_owner=opp_owner,
        opp_projected_total=opp_proj_total,
        spread=spread,
        win_probability=win_probability,
        recommended_stance=recommended_stance,
        stance_headline=stance_headline,
        stance_rationale=stance_rationale,
        vulnerabilities=vulnerabilities,
        correlations=correlations,
        head_to_head_slots=h2h_slots,
        key_action_items=key_actions,
    )


@router.get("/wrcb-matrix", response_model=list[WRCBMatchupAnalysis])
async def get_wrcb_matrix(
    league_id: int | None = Query(default=None),
    team_id: int | None = Query(default=None),
    week: int = Query(default=1, ge=1, le=18),
    only_rostered: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[WRCBMatchupAnalysis]:
    """Retrieve PFF-style WR vs CB matchup analysis with route alignments, shadow alerts, and advantage ratings."""
    eff_lid = league_id if isinstance(league_id, int) else None
    eff_tid = team_id if isinstance(team_id, int) else None

    effective_league_id = eff_lid or settings.espn_league_id
    if not effective_league_id:
        league_row = db.execute(select(LeagueModel)).scalars().first()
        if league_row:
            effective_league_id = league_row.id

    effective_team_id = eff_tid
    if effective_league_id and not effective_team_id:
        league_row = db.execute(
            select(LeagueModel).where(LeagueModel.id == effective_league_id)
        ).scalar_one_or_none()
        if league_row and league_row.user_team_id:
            effective_team_id = league_row.user_team_id
        elif league_row:
            first_team = db.execute(
                select(TeamModel).where(TeamModel.league_id == effective_league_id)
            ).scalars().first()
            if first_team:
                effective_team_id = first_team.id

    user_roster_pids: set[int] = set()
    user_starter_pids: set[int] = set()

    if effective_league_id and effective_team_id:
        user_entries = db.execute(
            select(RosterEntryModel).where(
                RosterEntryModel.league_id == effective_league_id,
                RosterEntryModel.team_id == effective_team_id,
            )
        ).scalars().all()
        user_roster_pids = {e.player_id for e in user_entries}
        user_starter_pids = {e.player_id for e in user_entries if e.is_starter}

    # Query all active WRs in the database
    query = select(PlayerModel).where(PlayerModel.position.in_(["WR"]))
    if only_rostered and user_roster_pids:
        query = query.where(PlayerModel.id.in_(user_roster_pids))

    wr_players = db.execute(query).scalars().all()

    # Fetch NFL schedule for the week to ensure accurate opponent assignment
    schedule_games = await nfl_schedule_client.fetch_week_schedule(
        season=settings.espn_season, week=week
    )
    team_opp_map: dict[str, str] = {}
    for g in schedule_games:
        team_opp_map[g.home_team] = g.away_team
        team_opp_map[g.away_team] = g.home_team

    results: list[WRCBMatchupAnalysis] = []
    for wr in wr_players:
        opp = team_opp_map.get(wr.pro_team.upper().strip(), "UNK")
        is_user_rostered = wr.id in user_roster_pids
        is_user_starter = wr.id in user_starter_pids

        # Analyze individual matchup
        analysis = wrcb_analyzer.analyze_matchup(
            player_id=wr.id,
            full_name=wr.full_name,
            pro_team=wr.pro_team,
            opponent=opp,
            projected_points=wr.projected_points or 10.0,
            is_user_rostered=is_user_rostered,
            is_user_starter=is_user_starter,
        )
        results.append(analysis)

    # Sort: User starters first, then user rostered, then highest projected points
    results.sort(
        key=lambda x: (
            1 if x.is_user_starter else (2 if x.is_user_rostered else 3),
            -x.projected_points,
        )
    )

    return results


@router.get("/vegas-environments", response_model=VegasIntelligenceResponse)
async def get_vegas_environments(
    league_id: int | None = Query(default=None),
    team_id: int | None = Query(default=None),
    week: int = Query(default=1, ge=1, le=18),
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
) -> VegasIntelligenceResponse:
    """Retrieve Vegas betting market intelligence, implied totals, game scripts, and user roster exposure."""
    eff_lid = league_id if isinstance(league_id, int) else None
    eff_tid = team_id if isinstance(team_id, int) else None

    effective_league_id = eff_lid or settings.espn_league_id
    if not effective_league_id:
        league_row = db.execute(select(LeagueModel)).scalars().first()
        if league_row:
            effective_league_id = league_row.id

    effective_team_id = eff_tid
    if effective_league_id and not effective_team_id:
        league_row = db.execute(
            select(LeagueModel).where(LeagueModel.id == effective_league_id)
        ).scalar_one_or_none()
        if league_row and league_row.user_team_id:
            effective_team_id = league_row.user_team_id
        elif league_row:
            first_team = db.execute(
                select(TeamModel).where(TeamModel.league_id == effective_league_id)
            ).scalars().first()
            if first_team:
                effective_team_id = first_team.id

    user_roster_data: list[dict[str, Any]] = []

    if effective_league_id and effective_team_id:
        user_entries = db.execute(
            select(RosterEntryModel).where(
                RosterEntryModel.league_id == effective_league_id,
                RosterEntryModel.team_id == effective_team_id,
            )
        ).scalars().all()
        pids = [e.player_id for e in user_entries]
        entry_map = {e.player_id: e for e in user_entries}

        if pids:
            players = db.execute(
                select(PlayerModel).where(PlayerModel.id.in_(pids))
            ).scalars().all()
            for p in players:
                entry = entry_map.get(p.id)
                user_roster_data.append({
                    "player_id": p.id,
                    "full_name": p.full_name,
                    "position": p.position,
                    "pro_team": p.pro_team,
                    "is_starter": entry.is_starter if entry else False,
                    "projected_points": p.projected_points or 0.0,
                })

    # Fetch weekly schedule with spreads and totals
    schedule_games = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)

    response = vegas_gamescript_analyzer.analyze_week(
        games=schedule_games,
        season=season,
        week=week,
        user_roster_players=user_roster_data,
    )

    return response


@router.get("/vegas-slate-props", response_model=list[PlayerPropsData])
async def get_vegas_slate_props(
    week: int = Query(default=1, ge=1, le=18),
    season: int = Query(default=2026),
    limit: int = Query(default=60, ge=1, le=150),
    team: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[PlayerPropsData]:
    """Retrieve consensus sportsbook proposition lines and market-implied PPR points for players on the slate."""
    eff_week = week if isinstance(week, int) else 1
    eff_season = season if isinstance(season, int) else 2026
    eff_limit = limit if isinstance(limit, int) else 60
    eff_team = team if isinstance(team, str) else None

    schedule_games = await nfl_schedule_client.fetch_week_schedule(season=eff_season, week=eff_week)

    # Map each team to its game environment parameters
    team_games: dict[str, dict[str, Any]] = {}
    for g in schedule_games:
        team_games[g.home_team.upper().strip()] = {
            "opponent": g.away_team,
            "implied_total": g.home_implied_total,
            "spread": g.spread,
            "over_under": g.over_under,
        }
        team_games[g.away_team.upper().strip()] = {
            "opponent": g.home_team,
            "implied_total": g.away_implied_total,
            "spread": -g.spread,
            "over_under": g.over_under,
        }

    query = select(PlayerModel).where(
        PlayerModel.position.in_(["QB", "RB", "WR", "TE"]),
        PlayerModel.projected_points >= 4.0,
    )
    if eff_team:
        clean_team = eff_team.upper().strip()
        query = query.where(PlayerModel.pro_team == clean_team)

    players = db.execute(query.order_by(PlayerModel.projected_points.desc())).scalars().all()

    props_results: list[PlayerPropsData] = []
    for p in players:
        p_team = (p.pro_team or "").upper().strip()
        g_info = team_games.get(p_team)
        if not g_info:
            continue

        prop_item = await vegas_props_client.get_player_props(
            player_id=p.id,
            player_name=p.full_name,
            position=p.position,
            team=p_team,
            opponent=g_info["opponent"],
            week=eff_week,
            season=eff_season,
            implied_team_total=g_info["implied_total"],
            spread=g_info["spread"],
            over_under=g_info["over_under"],
            projected_points=p.projected_points or 10.0,
        )
        props_results.append(prop_item)
        if len(props_results) >= eff_limit:
            break

    return props_results


@router.get("/depth-chart/{team}", response_model=TeamDepthChart | None)
async def get_team_depth_chart(team: str) -> TeamDepthChart | None:
    """Fetch official 2026-2027 NFL depth chart for a specific franchise."""
    chart = await nfl_depthchart_client.fetch_team_depth_chart(team)
    if not chart:
        raise HTTPException(status_code=404, detail=f"Depth chart for team {team} not found.")
    return chart


@router.get("/h2h-tale-of-the-tape", response_model=H2HTaleOfTheTapeResponse)
async def get_h2h_tale_of_the_tape(
    league_id: int | None = Query(default=None),
    team_id: int | None = Query(default=None),
    week: int = Query(default=1, ge=1, le=18),
    db: Session = Depends(get_db),
) -> H2HTaleOfTheTapeResponse:
    """Retrieve slot-by-slot starter positional Tale of the Tape against the week's opponent."""
    eff_lid = league_id if isinstance(league_id, int) else None
    eff_tid = team_id if isinstance(team_id, int) else None

    league = db.execute(select(LeagueModel)).scalars().first()
    effective_league_id = eff_lid or (league.id if league else settings.espn_league_id)
    user_team_id = eff_tid or (league.user_team_id if league else 6)

    # Find the H2H matchup for this week
    match = db.execute(
        select(MatchupModel).where(
            MatchupModel.league_id == effective_league_id,
            MatchupModel.week == week,
            (MatchupModel.home_team_id == user_team_id) | (MatchupModel.away_team_id == user_team_id),
        )
    ).scalars().first()

    if not match:
        raise HTTPException(status_code=404, detail=f"No matchup found for team {user_team_id} in week {week}")

    is_user_home = match.home_team_id == user_team_id
    opp_team_id = match.away_team_id if is_user_home else match.home_team_id

    teams = db.execute(select(TeamModel).where(TeamModel.league_id == effective_league_id)).scalars().all()
    team_name_map = {t.id: t.name for t in teams}

    user_team_name = team_name_map.get(user_team_id, "My Team")
    opp_team_name = team_name_map.get(opp_team_id, "Opponent Team")

    # Fetch starter entries for both teams
    user_entries = db.execute(
        select(RosterEntryModel).where(
            RosterEntryModel.league_id == effective_league_id,
            RosterEntryModel.team_id == user_team_id,
            RosterEntryModel.is_starter == True,
        )
    ).scalars().all()

    opp_entries = db.execute(
        select(RosterEntryModel).where(
            RosterEntryModel.league_id == effective_league_id,
            RosterEntryModel.team_id == opp_team_id,
            RosterEntryModel.is_starter == True,
        )
    ).scalars().all()

    all_pids = [e.player_id for e in user_entries] + [e.player_id for e in opp_entries]
    players_by_id: dict[int, PlayerModel] = {}
    if all_pids:
        players = db.execute(select(PlayerModel).where(PlayerModel.id.in_(all_pids))).scalars().all()
        players_by_id = {p.id: p for p in players}

    # Fetch weekly schedule to map opponents
    schedule_games = await nfl_schedule_client.fetch_week_schedule(season=settings.espn_season, week=week)
    team_opp_map: dict[str, str] = {}
    for g in schedule_games:
        team_opp_map[g.home_team] = g.away_team
        team_opp_map[g.away_team] = g.home_team

    # Group players by slot/position
    def categorize_starters(entries: list[RosterEntryModel]) -> dict[str, list[dict[str, Any]]]:
        categorized: dict[str, list[dict[str, Any]]] = {
            "QB": [], "RB": [], "WR": [], "TE": [], "FLEX": [], "D/ST": [], "K": []
        }
        for e in entries:
            p = players_by_id.get(e.player_id)
            if not p:
                continue
            opp = team_opp_map.get(p.pro_team.upper().strip(), "UNK")
            rank = dvp_client.get_position_rank(opp, p.position)
            stars = dvp_client.get_matchup_stars(rank)
            score, grade = dvp_client.calculate_matchup_score(opp, p.position)

            p_data = {
                "player_id": p.id,
                "full_name": p.full_name,
                "position": p.position,
                "pro_team": p.pro_team,
                "opponent": opp,
                "projected_points": round(p.projected_points or 0.0, 1),
                "opp_dvp_rank": rank,
                "matchup_stars": stars,
                "matchup_grade": grade,
                "slot_id": e.lineup_slot_id,
            }

            if e.lineup_slot_id == 23:
                categorized["FLEX"].append(p_data)
            elif p.position in categorized:
                categorized[p.position].append(p_data)
            else:
                categorized["FLEX"].append(p_data)

        # Sort within position groups by projected points descending
        for k in categorized:
            categorized[k].sort(key=lambda x: -x["projected_points"])
        return categorized

    user_roster = categorize_starters(user_entries)
    opp_roster = categorize_starters(opp_entries)

    # Standard Fantasy Lineup Slots (8-man: QB, RB1, RB2, WR1, WR2, TE, FLEX, D/ST, K)
    slot_specs = [
        ("QB", "QB", 0),
        ("RB1", "RB", 0),
        ("RB2", "RB", 1),
        ("WR1", "WR", 0),
        ("WR2", "WR", 1),
        ("TE", "TE", 0),
        ("FLEX", "FLEX", 0),
        ("D/ST", "D/ST", 0),
        ("K", "K", 0),
    ]

    slots_output: list[TaleOfTheTapeSlot] = []
    user_tot = 0.0
    opp_tot = 0.0

    for slot_name, pos_key, idx in slot_specs:
        user_list = user_roster.get(pos_key, [])
        opp_list = opp_roster.get(pos_key, [])

        u_p = user_list[idx] if idx < len(user_list) else {
            "player_id": 0, "full_name": "Empty Slot", "position": pos_key, "pro_team": "FA",
            "opponent": "-", "projected_points": 0.0, "opp_dvp_rank": 16, "matchup_stars": 3, "matchup_grade": "NEUTRAL"
        }
        o_p = opp_list[idx] if idx < len(opp_list) else {
            "player_id": 0, "full_name": "Empty Slot", "position": pos_key, "pro_team": "FA",
            "opponent": "-", "projected_points": 0.0, "opp_dvp_rank": 16, "matchup_stars": 3, "matchup_grade": "NEUTRAL"
        }

        user_tot += u_p["projected_points"]
        opp_tot += o_p["projected_points"]

        diff = round(u_p["projected_points"] - o_p["projected_points"], 1)
        if diff >= 1.5:
            adv = "USER"
            label = f"+{diff:.1f} pt Edge"
        elif diff <= -1.5:
            adv = "OPPONENT"
            label = f"{diff:.1f} pt Deficit"
        else:
            adv = "EVEN"
            label = "Even Toss-Up"

        slots_output.append(
            TaleOfTheTapeSlot(
                slot_name=slot_name,
                position=pos_key,
                user_player=u_p,
                opp_player=o_p,
                point_delta=diff,
                advantage=adv,
                leverage_label=label,
            )
        )

    spread = round(user_tot - opp_tot, 1)
    posture = "HIGH_FLOOR" if spread >= 8.0 else ("AGGRESSIVE_CEILING" if spread <= -8.0 else "BALANCED")

    # Generate strategic summary
    biggest_edge = max(slots_output, key=lambda s: s.point_delta)
    biggest_deficit = min(slots_output, key=lambda s: s.point_delta)
    leverage_summary = (
        f"Favored by +{spread:.1f} pts. Primary positional leverage: {biggest_edge.slot_name} ({biggest_edge.user_player['full_name']} {biggest_edge.leverage_label}). "
        f"Key opponent threat: {biggest_deficit.slot_name} ({biggest_deficit.opp_player['full_name']} {biggest_deficit.leverage_label})."
    )

    return H2HTaleOfTheTapeResponse(
        week=week,
        user_team_name=user_team_name,
        user_team_id=user_team_id,
        user_projected_total=round(user_tot, 1),
        opp_team_name=opp_team_name,
        opp_team_id=opp_team_id,
        opp_projected_total=round(opp_tot, 1),
        spread=spread,
        posture=posture,
        slots=slots_output,
        key_leverage_summary=leverage_summary,
    )


@router.get("/player-props", response_model=list[PlayerPropsData])
async def get_player_props(
    team_id: int | None = Query(default=None),
    week: int = Query(default=1, ge=1, le=18),
    db: Session = Depends(get_db),
) -> list[PlayerPropsData]:
    """Retrieve consensus sportsbook proposition lines & implied PPR points for rostered players."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    league_id = league.id if league else settings.espn_league_id

    query = select(PlayerModel)
    if league_id and team_id:
        pids = db.execute(
            select(RosterEntryModel.player_id).where(
                RosterEntryModel.league_id == league_id,
                RosterEntryModel.team_id == team_id,
            )
        ).scalars().all()
        query = query.where(PlayerModel.id.in_(pids))

    players = db.execute(query).scalars().all()
    nfl_games = await nfl_schedule_client.fetch_week_schedule(season=2026, week=week)
    game_map = {g.home_team: g for g in nfl_games}
    game_map.update({g.away_team: g for g in nfl_games})

    out: list[PlayerPropsData] = []
    for p in players:
        game = game_map.get(p.pro_team)
        itt = game.get_implied_total_for_team(p.pro_team) if game else 21.5
        opp = game.get_opponent_for_team(p.pro_team) if game else "BYE"
        spread = (game.spread if game.is_home_for_team(p.pro_team) else -game.spread) if game else 0.0
        ou = game.over_under if game else 44.0

        props = await vegas_props_client.get_player_props(
            player_id=p.id,
            player_name=p.full_name,
            position=p.position,
            team=p.pro_team,
            opponent=opp or "BYE",
            week=week,
            season=2026,
            implied_team_total=itt,
            spread=spread,
            over_under=ou,
            projected_points=p.projected_points,
        )
        out.append(props)
    return out


@router.get("/boris-chen-tiers", response_model=dict[str, list[BorisChenTierItem]])
async def get_boris_chen_tiers(
    week: int = Query(default=1, ge=1, le=18),
) -> dict[str, list[BorisChenTierItem]]:
    """Retrieve Boris Chen GMM statistical tier clusters grouped by position."""
    positions = ["QB", "PPR-RB", "PPR-WR", "PPR-TE", "DST", "K"]
    out: dict[str, list[BorisChenTierItem]] = {}
    for pos in positions:
        tier_dict = await boris_chen_client.get_position_tiers(position=pos, week=week)
        out[pos] = list(tier_dict.values())
    return out


# ============================================================================
# DEFENSE VS POSITION (DVP) FANTASY POINTS ALLOWED (FPA) ENDPOINTS
# ============================================================================

from src.services.matchup.dvp_service import dvp_service


class DvPRecordItem(BaseModel):
    id: str
    season: int
    week: int
    pro_team: str
    team_name: str
    position: str
    rank_softness: int
    rank_defense: int
    tier: str
    tier_label: str
    dk_fpa: float
    fd_fpa: float | None = None
    vs_avg: float
    prior_season_fpa: float
    current_season_fpa: float | None = None
    last4_fpa: float | None = None
    trend: str
    supporting_stats: dict[str, float]
    is_baseline: bool
    sample_games_current: int
    source: str
    source_url: str
    updated_at: str | None = None


class DvPStatusResponse(BaseModel):
    total_records: int
    is_seeded: bool
    last_updated: str | None = None
    hours_since_sync: float = 0.0
    is_stale: bool = False
    is_baseline: bool = True
    baseline_context: str


@router.get("/dvp-ratings", response_model=list[DvPRecordItem])
def get_dvp_ratings(
    season: int = Query(default=2026),
    week: int = Query(default=1, ge=1, le=18),
    position: str | None = Query(default=None, description="Position filter: QB, RB, WR, TE, or ALL"),
    team: str | None = Query(default=None, description="Team abbreviation filter: DAL, KC, etc., or ALL"),
) -> list[dict[str, Any]]:
    """Retrieve normalized Defense vs Position Fantasy Points Allowed ratings (DraftEdge FPA model)."""
    return dvp_service.get_dvp_ratings(season=season, week=week, position=position, pro_team=team)


@router.post("/dvp-sync")
async def sync_dvp_ratings(
    season: int = Query(default=2026),
    week: int = Query(default=1, ge=1, le=18),
) -> dict[str, Any]:
    """Trigger live scrape and database update for Defense vs Position ratings."""
    try:
        res = await dvp_service.sync_dvp_data(season=season, week=week)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync DvP data: {str(e)}")


@router.get("/dvp-status", response_model=DvPStatusResponse)
def get_dvp_status(
    season: int = Query(default=2026),
    week: int = Query(default=1, ge=1, le=18),
) -> dict[str, Any]:
    """Check Defense vs Position data freshness, record counts, and Week 1 baseline status."""
    return dvp_service.get_dvp_status(season=season, week=week)


# ============================================================================
# PREDICTION MARKET SENTIMENT (POLYMARKET) ENDPOINTS
# ============================================================================

@router.get("/market-sentiment", response_model=list[PlayerMarketSentiment])
async def get_market_sentiment(
    team_id: int | None = Query(default=None),
    week: int = Query(default=1, ge=1, le=18),
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
) -> list[PlayerMarketSentiment]:
    """Retrieve synthesized prediction market sentiment (Polymarket), starter confidence, and decoy risk."""
    league = db.execute(select(LeagueModel).order_by(LeagueModel.last_synced_at.desc())).scalars().first()
    league_id = league.id if league else settings.espn_league_id

    query = select(PlayerModel)
    if league_id and team_id:
        pids = db.execute(
            select(RosterEntryModel.player_id).where(
                RosterEntryModel.league_id == league_id,
                RosterEntryModel.team_id == team_id,
            )
        ).scalars().all()
        query = query.where(PlayerModel.id.in_(pids))

    players = db.execute(query).scalars().all()
    schedule = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)
    injuries = await nfl_injuries_client.fetch_injuries()

    sentiments: list[PlayerMarketSentiment] = []
    for p in players:
        sent = await market_sentiment_service.get_player_sentiment(
            player_id=p.id,
            player_name=p.full_name,
            position=p.position,
            pro_team=p.pro_team,
            week=week,
            season=season,
            schedule=schedule,
            injuries=injuries,
        )
        sentiments.append(sent)

    return sentiments


@router.get("/market-sentiment/player/{player_id}", response_model=PlayerMarketSentiment)
async def get_player_market_sentiment(
    player_id: int,
    week: int = Query(default=1, ge=1, le=18),
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
) -> PlayerMarketSentiment:
    """Retrieve detailed prediction market sentiment (Polymarket) for a specific player."""
    player = db.execute(select(PlayerModel).where(PlayerModel.id == player_id)).scalars().first()
    if not player:
        raise HTTPException(status_code=404, detail=f"Player with ID {player_id} not found.")

    schedule = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)
    injuries = await nfl_injuries_client.fetch_injuries()

    return await market_sentiment_service.get_player_sentiment(
        player_id=player.id,
        player_name=player.full_name,
        position=player.position,
        pro_team=player.pro_team,
        week=week,
        season=season,
        schedule=schedule,
        injuries=injuries,
    )


@router.get("/market-sentiment/buzz", response_model=list[PlayerMarketSentiment])
async def get_market_sentiment_buzz(
    week: int = Query(default=1, ge=1, le=18),
    season: int = Query(default=2026),
    db: Session = Depends(get_db),
) -> list[PlayerMarketSentiment]:
    """Retrieve high-priority market sentiment buzz (starter controversies, decoy risks, top rookies) across all NFL teams."""
    players = db.execute(select(PlayerModel)).scalars().all()
    schedule = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)
    injuries = await nfl_injuries_client.fetch_injuries()

    buzz: list[PlayerMarketSentiment] = []
    for p in players:
        sent = await market_sentiment_service.get_player_sentiment(
            player_id=p.id,
            player_name=p.full_name,
            position=p.position,
            pro_team=p.pro_team,
            week=week,
            season=season,
            schedule=schedule,
            injuries=injuries,
        )
        if (
            sent.has_starter_controversy
            or sent.decoy_risk in ("HIGH", "MODERATE")
            or sent.is_thursday_kickoff
            or sent.is_rookie
        ):
            buzz.append(sent)

    priority_order = {"CRITICAL_TNF": 0, "HIGH": 1, "NORMAL": 2}
    buzz.sort(key=lambda x: (priority_order.get(x.urgency_level, 3), -x.starter_confidence))
    return buzz[:25]




