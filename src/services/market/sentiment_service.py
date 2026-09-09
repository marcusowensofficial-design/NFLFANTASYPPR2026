"""Market Sentiment & Prediction Intelligence Service.

Combines Polymarket crowd prediction odds, official ESPN depth charts, live injury tracking,
and schedule timing to deliver tactical fantasy guidance:
1. Starter Confidence & Committee Volatility (Item 1)
2. Injury Active Probability & Decoy Risk for Thursday/Sunday Kickoffs (Item 2)
3. Rookie Breakout Pedigree & Role Uncertainty (Item 3)
"""

import logging
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.injuries_client import PlayerInjuryReport, nfl_injuries_client
from src.adapters.nfl.schedule_client import NFLGame, nfl_schedule_client
from src.adapters.polymarket.client import PolymarketMarket, polymarket_client

logger = logging.getLogger(__name__)

# Known premier 2024-2026 rookie class watchlist for Day-1 PPR roles
PREMIER_ROOKIE_CLASS: dict[str, dict[str, Any]] = {
    "marvin harrison jr": {"tier": "DAY1_ALPHA", "oroy_prob": 0.38, "draft_pick": 4},
    "malik nabers": {"tier": "DAY1_ALPHA", "oroy_prob": 0.24, "draft_pick": 6},
    "jayden daniels": {"tier": "DAY1_ALPHA", "oroy_prob": 0.35, "draft_pick": 2},
    "caleb williams": {"tier": "DAY1_ALPHA", "oroy_prob": 0.30, "draft_pick": 1},
    "rome odunze": {"tier": "HIGH_UPSIDE", "oroy_prob": 0.12, "draft_pick": 9},
    "xavier worthy": {"tier": "HIGH_UPSIDE", "oroy_prob": 0.10, "draft_pick": 28},
    "brock bowers": {"tier": "DAY1_ALPHA", "oroy_prob": 0.15, "draft_pick": 13},
    "brian thomas jr": {"tier": "HIGH_UPSIDE", "oroy_prob": 0.08, "draft_pick": 23},
    "trey benson": {"tier": "DEVELOPMENTAL", "oroy_prob": 0.05, "draft_pick": 66},
    "drake maye": {"tier": "DEVELOPMENTAL", "oroy_prob": 0.06, "draft_pick": 3},
}


class PlayerMarketSentiment(BaseModel):
    player_id: int
    player_name: str
    position: str
    pro_team: str
    opponent: str = "TBD"
    is_thursday_kickoff: bool = False
    game_date: str | None = None

    # Item 1: Starter Confidence & Committee Risk
    starter_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    starter_market_question: str | None = None
    has_starter_controversy: bool = False

    # Item 2: Injury Availability & Decoy Risk
    injury_status: str = "ACTIVE"
    practice_status: str | None = None
    decoy_risk: str = "LOW"  # LOW, MODERATE, HIGH
    injury_headline: str | None = None

    # Item 3: Rookie Pedigree & Breakout Tier
    is_rookie: bool = False
    rookie_tier: str | None = None  # DAY1_ALPHA, HIGH_UPSIDE, DEVELOPMENTAL
    oroy_implied_prob: float | None = None

    # Synthesis & Tactical Guidance
    market_headline: str = ""
    tactical_advice: str = ""
    urgency_level: str = "NORMAL"  # CRITICAL_TNF, HIGH, NORMAL


class MarketSentimentService:
    """Service generating synthesized prediction market sentiment and tactical advice."""

    async def get_player_sentiment(
        self,
        player_id: int,
        player_name: str,
        position: str,
        pro_team: str,
        week: int = 1,
        season: int = 2026,
        schedule: list[NFLGame] | None = None,
        injuries: dict[int, PlayerInjuryReport] | None = None,
    ) -> PlayerMarketSentiment:
        norm_name = player_name.strip().lower().replace(".", "")

        # 1. Schedule & Thursday Kickoff Check
        is_thursday = False
        opponent = "BYE"
        game_date = None

        if schedule is None:
            schedule = await nfl_schedule_client.fetch_week_schedule(season=season, week=week)

        game = next((g for g in schedule if g.home_team == pro_team or g.away_team == pro_team), None)
        if game:
            opponent = game.get_opponent_for_team(pro_team)
            game_date = game.date
            # Check if game is Thursday kickoff (first game of the week)
            if schedule:
                sorted_games = sorted(schedule, key=lambda x: x.date or "")
                earliest_date = sorted_games[0].date if sorted_games else None
                if game.date == earliest_date or "thu" in (game.date or "").lower():
                    is_thursday = True

        # 2. Check Polymarket for Starter Battles or Direct Player Markets
        matched_markets = await polymarket_client.get_market_for_player(player_name)
        starter_confidence = 0.95
        starter_question = None
        has_controversy = False

        starter_market = next(
            (m for m in matched_markets if "starter" in m.question.lower() or "start" in m.question.lower()),
            None,
        )

        if starter_market:
            has_controversy = True
            starter_question = starter_market.question
            starter_confidence = starter_market.yes_probability
        else:
            # Fallback to Depth Chart starter ranking
            team_dc = await nfl_depthchart_client.fetch_team_depth_chart(pro_team)
            if team_dc:
                p_status = team_dc.get_player_status(player_name, position)
                rank = p_status.get("rank")
                if rank == 1:
                    starter_confidence = 0.95
                elif rank == 2:
                    starter_confidence = 0.35
                    has_controversy = True
                elif rank and rank > 2:
                    starter_confidence = 0.10

        # 3. Check Injury Status & Decoy Risk
        injury_status = "ACTIVE"
        practice_status = None
        decoy_risk = "LOW"
        injury_headline = None

        if injuries is None:
            injuries = await nfl_injuries_client.fetch_injuries()

        inj_report = injuries.get(player_id)
        if not inj_report:
            # Fuzzy match by name if athlete_id doesn't match
            inj_report = next((inj for inj in injuries.values() if inj.name.lower() == norm_name), None)

        if inj_report:
            injury_status = inj_report.status.upper()
            practice_status = inj_report.practice_status
            injury_headline = inj_report.headline or inj_report.notes

            if injury_status in ("OUT", "DOUBTFUL", "IR"):
                decoy_risk = "HIGH"
                starter_confidence = 0.0
            elif injury_status == "QUESTIONABLE":
                if practice_status == "DNP":
                    decoy_risk = "HIGH"
                    starter_confidence = min(starter_confidence, 0.45)
                elif practice_status == "LIMITED":
                    decoy_risk = "MODERATE"
                    starter_confidence = min(starter_confidence, 0.70)
                elif practice_status == "FULL":
                    decoy_risk = "LOW"
                    starter_confidence = min(starter_confidence, 0.88)
                else:
                    decoy_risk = "MODERATE"

        # 4. Check Rookie Pedigree & Breakout Tier
        is_rookie = False
        rookie_tier = None
        oroy_prob = None

        rookie_info = PREMIER_ROOKIE_CLASS.get(norm_name)
        if rookie_info:
            is_rookie = True
            rookie_tier = rookie_info["tier"]
            oroy_prob = rookie_info["oroy_prob"]
        elif any("draft" in m.question.lower() or "rookie" in m.question.lower() for m in matched_markets):
            is_rookie = True
            rookie_tier = "HIGH_UPSIDE"

        # 5. Synthesize Headline, Tactical Advice, and Urgency
        urgency = "NORMAL"
        headline_parts = []
        advice_parts = []

        if is_thursday:
            urgency = "CRITICAL_TNF"
            headline_parts.append("THURSDAY KICKOFF ALERT")
            advice_parts.append(
                "Kickoff is tomorrow. Never start in FLEX slot; lock into primary position to keep Sunday FLEX flexibility."
            )

        if has_controversy:
            urgency = "CRITICAL_TNF" if is_thursday else "HIGH"
            pct = int(starter_confidence * 100)
            headline_parts.append(f"Market Starter Odds: {pct}%")
            if starter_confidence < 0.70:
                advice_parts.append(
                    f"Active depth chart controversy. Market prices only {pct}% starting likelihood; volatile floor."
                )
            else:
                advice_parts.append(f"Favored starter ({pct}% market confidence), but watch snap rotation.")

        if decoy_risk == "HIGH":
            urgency = "CRITICAL_TNF" if is_thursday else "HIGH"
            headline_parts.append("HIGH DECOY / PITCH COUNT RISK")
            advice_parts.append("DNP/LP practice trend indicates limited snap count if active. Prepare Sunday pivot.")
        elif decoy_risk == "MODERATE":
            headline_parts.append("Moderate Injury Decoy Risk")
            advice_parts.append("Monitoring practice progression; has upside but carry contingency.")

        if is_rookie and rookie_tier == "DAY1_ALPHA":
            headline_parts.append(f"Elite Rookie Pedigree ({rookie_tier})")
            advice_parts.append("High ceiling standard deviation. Elite play in CEILING/GPP modes.")

        if not headline_parts:
            headline_parts.append("Locked Starter - Stable Market Sentiment")
            advice_parts.append("Full role security and clear baseline expectations.")

        return PlayerMarketSentiment(
            player_id=player_id,
            player_name=player_name,
            position=position,
            pro_team=pro_team,
            opponent=opponent,
            is_thursday_kickoff=is_thursday,
            game_date=game_date,
            starter_confidence=round(starter_confidence, 2),
            starter_market_question=starter_question,
            has_starter_controversy=has_controversy,
            injury_status=injury_status,
            practice_status=practice_status,
            decoy_risk=decoy_risk,
            injury_headline=injury_headline,
            is_rookie=is_rookie,
            rookie_tier=rookie_tier,
            oroy_implied_prob=oroy_prob,
            market_headline=" • ".join(headline_parts),
            tactical_advice=" ".join(advice_parts),
            urgency_level=urgency,
        )


market_sentiment_service = MarketSentimentService()
