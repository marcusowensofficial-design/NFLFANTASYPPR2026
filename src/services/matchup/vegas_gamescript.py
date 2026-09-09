"""Vegas Implied Team Totals & Game Script Intelligence (Action Network / ETR Model).

Categorizes game environments into high-ceiling shootouts, positive run funnels,
trailing pass funnels, and defensive slugfests based on DraftKings lines.
"""

import logging
from typing import Any
from pydantic import BaseModel, Field

from src.adapters.nfl.schedule_client import NFLGame

logger = logging.getLogger(__name__)


class GameRosterExposurePlayer(BaseModel):
    player_id: int
    full_name: str
    position: str
    pro_team: str
    is_starter: bool = False
    projected_points: float = 0.0


class VegasGameEnvironment(BaseModel):
    game_id: str
    game_name: str
    game_date: str
    venue_name: str
    is_dome: bool
    over_under: float
    spread: float  # Home perspective (negative = home favored)
    favorite_team: str
    underdog_team: str
    spread_magnitude: float
    home_team: str
    away_team: str
    home_implied_total: float
    away_implied_total: float
    highest_implied_total: float
    game_script: str  # SHOOTOUT, FAVORITE_RUN_FUNNEL, UNDERDOG_PASS_FUNNEL, DEFENSIVE_SLUGFEST, BALANCED
    game_script_label: str
    pace_index: str  # FAST, ABOVE_AVERAGE, NEUTRAL, SLOW
    expected_total_plays: int
    tactical_advice: str
    user_roster_exposure: list[GameRosterExposurePlayer] = Field(default_factory=list)


class TeamImpliedRanking(BaseModel):
    rank: int
    pro_team: str
    implied_total: float
    opponent: str
    opponent_implied_total: float = 0.0
    spread_diff: float = 0.0
    is_home: bool
    is_favorite: bool
    over_under: float
    game_script: str


class VegasIntelligenceResponse(BaseModel):
    season: int
    week: int
    total_games: int
    shootout_count: int
    games: list[VegasGameEnvironment]
    team_rankings: list[TeamImpliedRanking]
    top_target_games: list[str]


class VegasGameScriptAnalyzer:
    """Derives actionable fantasy game environment classifications from Vegas betting markets."""

    def classify_team_script(
        self,
        implied_total: float,
        over_under: float,
        is_favorite: bool,
        spread_magnitude: float,
    ) -> str:
        """Classify an individual team's expected environment for fantasy PPR scoring.

        Empirical Principles:
        - SCORING_BONANZA: Implied total >= 26.0, or (implied total >= 25.0 and is_favorite and spread >= 5.0).
          Elite scoring expectation (~3.7 to 4.2+ TDs). Even if heavily favored, passing efficiency is high early,
          followed by 4th-quarter rushing volume and goal-line plunge equity.
        - UNDERDOG_PASS_FUNNEL: Underdogs with spread >= 5.5 (or trailing scripts with sub-21 ITT facing spread >= 4.0).
          Trailing game scripts induce elevated Pass Rate Over Expectation (PROE +8% to +14%), hurry-up tempo,
          and high PPR target volume for pass-catching RBs and slot WRs.
        - SHOOTOUT: High game total (O/U >= 47.0) with tight spread (<= 4.5) and team ITT >= 21.5.
          Both teams are forced into aggressive 4-quarter passing; neither can nurse a lead with conservative runs.
        - FAVORITE_RUN_FUNNEL: Favorites with spread >= 5.0 in moderate/lower total games (< 26.0).
          Positive game script where the team protects a lead with heavy ground volume.
        - DEFENSIVE_SLUGFEST: Team implied total < 20.5 or game O/U <= 40.5 (and not an elite favorite).
          Touchdown desert, sluggish pace, suppressed scoring ceiling.
        - BALANCED: Standard balanced game script.
        """
        if implied_total >= 26.0 or (implied_total >= 25.0 and is_favorite and spread_magnitude >= 5.0):
            return "SCORING_BONANZA"

        if not is_favorite and (spread_magnitude >= 5.5 or (implied_total < 21.0 and spread_magnitude >= 4.0)):
            return "UNDERDOG_PASS_FUNNEL"

        if over_under >= 47.0 and spread_magnitude <= 4.5 and implied_total >= 21.5:
            return "SHOOTOUT"

        if is_favorite and spread_magnitude >= 5.0:
            return "FAVORITE_RUN_FUNNEL"

        if implied_total < 20.5 or over_under <= 40.5:
            return "DEFENSIVE_SLUGFEST"

        return "BALANCED"

    def classify_game(self, game: NFLGame) -> tuple[str, str, str, int, str]:
        ou = game.over_under
        spread_abs = abs(game.spread)
        fav = game.home_team if game.spread < 0 else game.away_team
        dog = game.away_team if game.spread < 0 else game.home_team
        fav_total = max(game.home_implied_total, game.away_implied_total)

        # 1. Classify Game Script
        if ou >= 47.5 and spread_abs <= 4.5:
            script = "SHOOTOUT"
            label = "High-Ceiling Shootout"
            pace = "FAST"
            plays = 135
            advice = (
                f"🔥 SHOOTOUT ENVIRONMENT (O/U {ou:.1f}, {spread_abs:.1f} spread). "
                f"Elevated passing tempo and multi-touchdown ceiling for both QBs and primary WRs."
            )
        elif spread_abs >= 6.0 and ou >= 46.0:
            script = "UNDERDOG_PASS_FUNNEL"
            label = "High-Scoring Mismatch / Trailing Pass"
            pace = "FAST"
            plays = 132
            advice = (
                f"⚡ HIGH-SCORING MISMATCH: {fav} has an elite implied total ({fav_total:.1f} pts) "
                f"while {dog} (+{spread_abs:.1f}) is projected into aggressive trailing pass mode. "
                f"Elite TD ceiling for {fav}; elevated PPR dump-offs and catch-up volume for {dog} pass-catchers."
            )
        elif spread_abs >= 6.5 and ou <= 44.5:
            script = "FAVORITE_RUN_FUNNEL"
            label = "Positive Run Script / Pass Funnel"
            pace = "NEUTRAL"
            plays = 122
            advice = (
                f"🏃 POSITIVE RUN SCRIPT: {fav} is favored by {spread_abs:.1f}. "
                f"Expect heavy 2nd-half rushing volume for {fav}'s primary RB; {dog} in pass-heavy trailing mode."
            )
        elif spread_abs >= 6.5:
            script = "UNDERDOG_PASS_FUNNEL"
            label = "High-Volume Trailing Script"
            pace = "ABOVE_AVERAGE"
            plays = 128
            advice = (
                f"📈 TRAILING PASS SCRIPT: {dog} (+{spread_abs:.1f} underdog) is projected to chase points. "
                f"Boosts PPR dump-offs to {dog}'s pass-catching RBs and slot receivers."
            )
        elif ou <= 40.5:
            script = "DEFENSIVE_SLUGFEST"
            label = "Low-Scoring Defensive Battle"
            pace = "SLOW"
            plays = 116
            advice = (
                f"🛡️ DEFENSIVE SLUGFEST (O/U {ou:.1f}). Lower touchdown equity for skill players; "
                f"prime streaming spot for opposing D/STs."
            )
        else:
            script = "BALANCED"
            label = "Balanced Environment"
            pace = "NEUTRAL"
            plays = 124
            advice = (
                f"Balanced neutral game script ({ou:.1f} O/U, {spread_abs:.1f} spread). "
                f"Standard positional usage distribution expected."
            )

        return script, label, pace, plays, advice

    def analyze_week(
        self,
        games: list[NFLGame],
        season: int = 2026,
        week: int = 1,
        user_roster_players: list[dict[str, Any]] | None = None,
    ) -> VegasIntelligenceResponse:
        environments: list[VegasGameEnvironment] = []
        team_implied_list: list[dict[str, Any]] = []

        # Index user players by pro_team
        team_to_players: dict[str, list[GameRosterExposurePlayer]] = {}
        if user_roster_players:
            for p in user_roster_players:
                t = str(p.get("pro_team", "")).upper().strip()
                if t:
                    team_to_players.setdefault(t, []).append(
                        GameRosterExposurePlayer(
                            player_id=p.get("player_id", 0),
                            full_name=p.get("full_name", ""),
                            position=p.get("position", ""),
                            pro_team=t,
                            is_starter=bool(p.get("is_starter", False)),
                            projected_points=float(p.get("projected_points", 0.0) or 0.0),
                        )
                    )

        shootout_count = 0
        top_targets: list[str] = []

        for g in games:
            script, label, pace, plays, advice = self.classify_game(g)
            if script == "SHOOTOUT":
                shootout_count += 1
                top_targets.append(g.name)

            is_home_fav = g.spread < 0
            fav_team = g.home_team if is_home_fav else g.away_team
            dog_team = g.away_team if is_home_fav else g.home_team
            spread_mag = round(abs(g.spread), 1)

            # Roster exposure
            seen_pids: set[int] = set()
            exposed_players: list[GameRosterExposurePlayer] = []
            home_key = str(g.home_team).upper().strip()
            away_key = str(g.away_team).upper().strip()
            for cand in team_to_players.get(home_key, []) + team_to_players.get(away_key, []):
                if cand.player_id not in seen_pids:
                    seen_pids.add(cand.player_id)
                    exposed_players.append(cand)

            env = VegasGameEnvironment(
                game_id=g.id,
                game_name=g.name,
                game_date=g.date,
                venue_name=g.venue_name,
                is_dome=g.is_dome,
                over_under=g.over_under,
                spread=g.spread,
                favorite_team=fav_team,
                underdog_team=dog_team,
                spread_magnitude=spread_mag,
                home_team=g.home_team,
                away_team=g.away_team,
                home_implied_total=round(g.home_implied_total, 2),
                away_implied_total=round(g.away_implied_total, 2),
                highest_implied_total=round(max(g.home_implied_total, g.away_implied_total), 2),
                game_script=script,
                game_script_label=label,
                pace_index=pace,
                expected_total_plays=plays,
                tactical_advice=advice,
                user_roster_exposure=exposed_players,
            )
            environments.append(env)

            # Record individual team totals with role-specific environment scripts
            home_script = self.classify_team_script(
                implied_total=g.home_implied_total,
                over_under=g.over_under,
                is_favorite=is_home_fav,
                spread_magnitude=spread_mag,
            )
            away_script = self.classify_team_script(
                implied_total=g.away_implied_total,
                over_under=g.over_under,
                is_favorite=not is_home_fav,
                spread_magnitude=spread_mag,
            )

            team_implied_list.append({
                "pro_team": g.home_team,
                "implied_total": g.home_implied_total,
                "opponent": g.away_team,
                "opponent_implied_total": g.away_implied_total,
                "spread_diff": round(g.home_implied_total - g.away_implied_total, 2),
                "is_home": True,
                "is_favorite": is_home_fav,
                "over_under": g.over_under,
                "game_script": home_script,
            })
            team_implied_list.append({
                "pro_team": g.away_team,
                "implied_total": g.away_implied_total,
                "opponent": g.home_team,
                "opponent_implied_total": g.home_implied_total,
                "spread_diff": round(g.away_implied_total - g.home_implied_total, 2),
                "is_home": False,
                "is_favorite": not is_home_fav,
                "over_under": g.over_under,
                "game_script": away_script,
            })

        # Sort team implied totals descending to assign ranks 1-32
        team_implied_list.sort(key=lambda x: x["implied_total"], reverse=True)
        ranked_teams: list[TeamImpliedRanking] = []
        for idx, item in enumerate(team_implied_list, start=1):
            ranked_teams.append(
                TeamImpliedRanking(
                    rank=idx,
                    pro_team=item["pro_team"],
                    implied_total=round(item["implied_total"], 2),
                    opponent=item["opponent"],
                    opponent_implied_total=round(item.get("opponent_implied_total", 0.0), 2),
                    spread_diff=round(item.get("spread_diff", 0.0), 2),
                    is_home=item["is_home"],
                    is_favorite=item["is_favorite"],
                    over_under=item["over_under"],
                    game_script=item["game_script"],
                )
            )

        # Sort environments by highest over/under descending
        environments.sort(key=lambda x: x.over_under, reverse=True)

        return VegasIntelligenceResponse(
            season=season,
            week=week,
            total_games=len(environments),
            shootout_count=shootout_count,
            games=environments,
            team_rankings=ranked_teams,
            top_target_games=top_targets,
        )


vegas_gamescript_analyzer = VegasGameScriptAnalyzer()
