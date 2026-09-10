"""Live NFL Game Telemetry and Single-Game Fantasy Tracker."""

import logging
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
KICKOFF_EVENT_ID = "401872657"  # SF @ LAR 2026 Season Opener

DEFAULT_SHOWDOWN_ROSTER = {
    "Davante Adams": {"slot": "MVP", "is_mvp": True, "team": "LAR"},
    "Christian McCaffrey": {"slot": "FLEX", "is_mvp": False, "team": "SF"},
    "Puka Nacua": {"slot": "FLEX", "is_mvp": False, "team": "LAR"},
    "Matthew Stafford": {"slot": "FLEX", "is_mvp": False, "team": "LAR"},
    "Harrison Mevis": {"slot": "FLEX", "is_mvp": False, "team": "LAR"},
    "Terrance Ferguson": {"slot": "FLEX", "is_mvp": False, "team": "LAR"},
}


class LivePlayerScore(BaseModel):
    name: str
    team: str
    slot: str  # MVP or FLEX
    is_mvp: bool = False
    receptions: int = 0
    rec_yards: float = 0.0
    rec_tds: int = 0
    carries: int = 0
    rush_yards: float = 0.0
    rush_tds: int = 0
    pass_yards: float = 0.0
    pass_tds: int = 0
    interceptions: int = 0
    fg_made: int = 0
    pat_made: int = 0
    raw_fpts: float = 0.0
    multiplier_fpts: float = 0.0


class LiveGameStatus(BaseModel):
    event_id: str
    game_name: str
    state: str  # pre, in, post
    detail: str  # e.g., "1st - 9:42", "Halftime", "Final"
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    down_distance_text: str | None = None
    possession_team: str | None = None
    roster_scores: list[LivePlayerScore] = Field(default_factory=list)
    total_lineup_fpts: float = 0.0


class LiveGameTracker:
    """Tracks live game telemetry, drive summaries, and our FanDuel Showdown score."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def fetch_live_game(
        self,
        event_id: str = KICKOFF_EVENT_ID,
        roster: dict[str, dict[str, Any]] | None = None,
    ) -> LiveGameStatus:
        our_roster = roster or DEFAULT_SHOWDOWN_ROSTER
        url = f"https://cdn.espn.com/core/nfl/game?xhr=1&gameId={event_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                raw_json = resp.json()
                data = raw_json.get("gamepackageJSON", raw_json)
            except Exception as e:
                logger.warning(f"Error fetching live game {event_id}: {e}")
                data = {}



        header = data.get("header", {})
        comps = header.get("competitions", [{}])[0]
        status = comps.get("status", {})
        status_type = status.get("type", {})
        state = status_type.get("state", "pre")
        detail = status_type.get("shortDetail") or status_type.get("detail", "Scheduled")

        competitors = comps.get("competitors", [])
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), {})

        home_team = home_comp.get("team", {}).get("abbreviation", "SEA")
        away_team = away_comp.get("team", {}).get("abbreviation", "NE")
        home_score = int(home_comp.get("score") or 0)
        away_score = int(away_comp.get("score") or 0)

        # Situation
        situation = comps.get("situation", {})
        down_dist = situation.get("downDistanceText")
        possession_id = situation.get("possession")
        possession_team = None
        if possession_id:
            if str(possession_id) == str(home_comp.get("id")):
                possession_team = home_team
            elif str(possession_id) == str(away_comp.get("id")):
                possession_team = away_team

        # Parse player stats from boxscore
        boxscore = data.get("boxscore", {})
        players_data = boxscore.get("players", [])

        player_stats_map: dict[str, dict[str, Any]] = {name: {} for name in our_roster}


        for team_block in players_data:
            stat_categories = team_block.get("statistics", [])
            for cat in stat_categories:
                cat_name = cat.get("name")
                labels = [label.lower() for label in cat.get("labels", [])]
                athletes = cat.get("athletes", [])
                for ath in athletes:
                    ath_info = ath.get("athlete", {})
                    ath_name = ath_info.get("displayName", "")
                    # Match name against our roster
                    matched_name = next(
                        (n for n in our_roster if n.lower() in ath_name.lower() or ath_name.lower() in n.lower()),
                        None
                    )
                    if not matched_name:
                        continue

                    stats_vals = ath.get("stats", [])
                    st_dict = dict(zip(labels, stats_vals))

                    if matched_name not in player_stats_map:
                        player_stats_map[matched_name] = {}

                    # Accumulate stats
                    if cat_name == "receiving":
                        player_stats_map[matched_name]["rec"] = int(st_dict.get("rec", 0))
                        player_stats_map[matched_name]["rec_yds"] = float(st_dict.get("yds", 0.0))
                        player_stats_map[matched_name]["rec_td"] = int(st_dict.get("td", 0))
                    elif cat_name == "rushing":
                        player_stats_map[matched_name]["car"] = int(st_dict.get("car", 0))
                        player_stats_map[matched_name]["rush_yds"] = float(st_dict.get("yds", 0.0))
                        player_stats_map[matched_name]["rush_td"] = int(st_dict.get("td", 0))
                    elif cat_name == "passing":
                        player_stats_map[matched_name]["pass_yds"] = float(st_dict.get("yds", 0.0))
                        player_stats_map[matched_name]["pass_td"] = int(st_dict.get("td", 0))
                        player_stats_map[matched_name]["int"] = int(st_dict.get("int", 0))
                    elif cat_name == "fumbles":
                        player_stats_map[matched_name]["fumbles_lost"] = int(st_dict.get("lost", 0))
                    elif cat_name == "kicking":
                        fg_str = st_dict.get("fg", "0/0")
                        fg_m = int(fg_str.split("/")[0]) if "/" in fg_str else 0
                        pat_str = st_dict.get("xp", "0/0")
                        pat_m = int(pat_str.split("/")[0]) if "/" in pat_str else 0
                        player_stats_map[matched_name]["fg"] = fg_m
                        player_stats_map[matched_name]["pat"] = pat_m

        # Parse scoring plays for exact Field Goal distances and 2-point conversions
        import re
        fg_points_map: dict[str, float] = {name: 0.0 for name in our_roster}
        two_pt_map: dict[str, int] = {name: 0 for name in our_roster}

        for sp in data.get("scoringPlays", []):
            sp_text = sp.get("text", "")
            for name in our_roster:
                last_name = name.split()[-1]
                if name.lower() in sp_text.lower() or last_name.lower() in sp_text.lower():
                    # Field Goal distance tiers: 0-39 yds: 3 pts, 40-49 yds: 4 pts, 50+ yds: 5 pts
                    if "field goal" in sp_text.lower():
                        match = re.search(r"(\d+)\s*(?:yd|yard)\s*field goal", sp_text, re.I)
                        if match:
                            dist = int(match.group(1))
                            if dist >= 50:
                                fg_points_map[name] += 5.0
                            elif dist >= 40:
                                fg_points_map[name] += 4.0
                            else:
                                fg_points_map[name] += 3.0
                        else:
                            fg_points_map[name] += 3.0
                    elif "two-point" in sp_text.lower() or "2pt" in sp_text.lower():
                        two_pt_map[name] += 1

        roster_scores: list[LivePlayerScore] = []
        total_fpts = 0.0

        for name, meta in our_roster.items():
            st = player_stats_map.get(name, {})
            receptions = st.get("rec", 0)
            rec_yds = st.get("rec_yds", 0.0)
            rec_tds = st.get("rec_td", 0)
            carries = st.get("car", 0)
            rush_yds = st.get("rush_yds", 0.0)
            rush_tds = st.get("rush_td", 0)
            pass_yds = st.get("pass_yds", 0.0)
            pass_tds = st.get("pass_td", 0)
            interceptions = st.get("int", 0)
            fumbles_lost = st.get("fumbles_lost", 0)
            fg_made = st.get("fg", 0)
            pat_made = st.get("pat", 0)
            two_pts = two_pt_map.get(name, 0)

            # 100-yard & 300-yard milestone bonuses (+3.0 AnyFLEX, +4.5 MVP)
            pass_bonus = 3.0 if pass_yds >= 300.0 else 0.0
            rush_bonus = 3.0 if rush_yds >= 100.0 else 0.0
            rec_bonus = 3.0 if rec_yds >= 100.0 else 0.0

            # Kicking points: use precise yardage tier if available from scoringPlays, else default 3.0/FG
            kicking_pts = fg_points_map.get(name, 0.0)
            if kicking_pts == 0.0 and fg_made > 0:
                kicking_pts = fg_made * 3.0
            kicking_pts += (pat_made * 1.0)

            # FanDuel Official Scoring Formula
            raw = (
                (pass_yds * 0.04)
                + (pass_tds * 4.0)
                - (interceptions * 1.0)
                + pass_bonus
                + (rush_yds * 0.10)
                + (rush_tds * 6.0)
                + rush_bonus
                + (receptions * 0.5)
                + (rec_yds * 0.10)
                + (rec_tds * 6.0)
                + rec_bonus
                - (fumbles_lost * 2.0)
                + (two_pts * 2.0)
                + kicking_pts
            )

            is_mvp = meta["is_mvp"]
            mult_fpts = round(raw * 1.5, 2) if is_mvp else round(raw, 2)
            total_fpts += mult_fpts

            roster_scores.append(
                LivePlayerScore(
                    name=name,
                    team=meta["team"],
                    slot=meta["slot"],
                    is_mvp=is_mvp,
                    receptions=receptions,
                    rec_yards=rec_yds,
                    rec_tds=rec_tds,
                    carries=carries,
                    rush_yards=rush_yds,
                    rush_tds=rush_tds,
                    pass_yards=pass_yds,
                    pass_tds=pass_tds,
                    interceptions=interceptions,
                    fg_made=fg_made,
                    pat_made=pat_made,
                    raw_fpts=round(raw, 2),
                    multiplier_fpts=mult_fpts,
                )
            )

        return LiveGameStatus(
            event_id=event_id,
            game_name=f"{away_team} @ {home_team}",
            state=state,
            detail=detail,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            down_distance_text=down_dist,
            possession_team=possession_team,
            roster_scores=roster_scores,
            total_lineup_fpts=round(total_fpts, 2),
        )


live_game_tracker = LiveGameTracker()
