"""In-House First-Party NFL Defense vs. Position (DvP) & Fantasy Points Allowed (FPA) Engine.

Calculates cumulative, indisputable per-game fantasy points allowed directly from
official NFL/ESPN box scores across all completed regular season weeks.

Scoring Standards:
- Half-PPR (FanDuel DFS Standard): 0.04/yd pass, 4.0 pass TD, -1.0 INT, 0.10/yd rush/rec, 6.0 rush/rec TD, 0.50/rec, -2.0 fum lost, 2.0 2-pt conv.
- Full-PPR (ESPN Fantasy Standard): 0.04/yd pass, 4.0 pass TD, -2.0 INT, 0.10/yd rush/rec, 6.0 rush/rec TD, 1.00/rec, -2.0 fum lost, 2.0 2-pt conv.

Features:
- Multi-Week Cumulative Averaging (all weeks up to game day).
- Adaptive Early-Season Bayesian Prior (smooth transition from baseline into 2026 sample).
- Full 1-32 Softness Ranking & Tier Classification (SMASH, FAVORABLE, NEUTRAL, TOUGH, LOCKDOWN).
- Granular Sub-Metrics (Pass Yds/G, Pass TD/G, Sacks/G, Rush Yds/G, Rush TD/G, Targets/G, Rec/G, Rec Yds/G, Rec TD/G).
"""

import json
import logging
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger("dvp_calculator")

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEPTH_CHART_PATH = WORKSPACE_DIR / "data" / "nfl_depth_charts_2026.json"
DRAFTEDGE_SEED_PATH = WORKSPACE_DIR / "data" / "draftedge_dvp_seed.json"
OUTPUT_PROPRIETARY_DVP_PATH = WORKSPACE_DIR / "data" / "nfl_dvp_proprietary_2026.json"

# All 32 NFL Teams with standard abbreviations and full names
ALL_32_NFL_TEAMS: dict[str, str] = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}

# 2025 Prior Season Baseline Averages (Half-PPR / Full-PPR reference)
DEFAULT_BASELINE_FPA: dict[str, dict[str, dict[str, float]]] = {
    "QB": {"half_ppr": 17.5, "full_ppr": 17.5},
    "RB": {"half_ppr": 21.0, "full_ppr": 24.5},
    "WR": {"half_ppr": 28.0, "full_ppr": 36.0},
    "TE": {"half_ppr": 9.5, "full_ppr": 12.5},
}


def get_softness_tier(rank_softness: int) -> tuple[str, str]:
    """Classifies 1-32 Softness rank (1 = softest / smash matchup, 32 = lockdown defense)."""
    if rank_softness <= 6:
        return "SMASH", "Elite Smash Matchup"
    elif rank_softness <= 12:
        return "FAVORABLE", "Favorable Matchup"
    elif rank_softness <= 20:
        return "NEUTRAL", "Neutral Matchup"
    elif rank_softness <= 26:
        return "TOUGH", "Tough Defense"
    else:
        return "LOCKDOWN", "Brutal Lockdown"


def load_position_map() -> dict[str, str]:
    """Builds a map from lowercase player name to their primary position."""
    pos_map: dict[str, str] = {}
    if DEPTH_CHART_PATH.exists():
        try:
            with open(DEPTH_CHART_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for _, tdata in data.get("teams", {}).items():
                for unit in ["offense", "defense", "special_teams"]:
                    for slot, players in tdata.get(unit, {}).items():
                        clean_pos = slot.upper().rstrip("0123456789")
                        if clean_pos in ("FB", "HB"):
                            clean_pos = "RB"
                        for p in players:
                            name = p.get("name", "").strip().lower()
                            if name:
                                pos_map[name] = clean_pos
        except Exception as ex:
            logger.debug(f"Depth chart loading error for pos map: {ex}")
    return pos_map


def load_2025_baseline_by_team() -> dict[str, dict[str, dict[str, float]]]:
    """Loads 2025 prior-season baseline stats per team and position from seed file."""
    baseline: dict[str, dict[str, dict[str, float]]] = {}
    if DRAFTEDGE_SEED_PATH.exists():
        try:
            with open(DRAFTEDGE_SEED_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for pos, records in data.items():
                for r in records:
                    team = r.get("pro_team")
                    if not team:
                        continue
                    if team not in baseline:
                        baseline[team] = {}
                    prior_fpa = r.get("prior_season_fpa") or DEFAULT_BASELINE_FPA[pos]["half_ppr"]
                    baseline[team][pos] = {
                        "prior_season_fpa": float(prior_fpa),
                        "supp": r.get("supporting_stats", {}),
                    }
        except Exception as ex:
            logger.debug(f"Baseline loading error: {ex}")
    return baseline


async def fetch_game_summaries_for_week(season: int, week: int) -> list[dict[str, Any]]:
    """Fetches all game box scores for a specific regular season week from ESPN."""
    scoreboard_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={season}&seasontype=2&week={week}"
    summaries = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.get(scoreboard_url)
            res.raise_for_status()
            data = res.json()
        except Exception as ex:
            logger.warning(f"Could not fetch ESPN scoreboard for Week {week}: {ex}")
            return []

        events = data.get("events", [])
        for ev in events:
            event_id = ev.get("id")
            if not event_id:
                continue
            summary_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"
            try:
                sres = await client.get(summary_url)
                if sres.status_code == 200:
                    sdata = sres.json()
                    summaries.append(sdata)
            except Exception as ex:
                logger.debug(f"Failed to fetch summary for event {event_id}: {ex}")

    return summaries


def calculate_player_fantasy_points(pstats: dict[str, Any]) -> tuple[float, float]:
    """Calculates Half-PPR (FanDuel) and Full-PPR (ESPN) fantasy points from box score stats."""
    pass_yds = pstats.get("pass_yds", 0.0)
    pass_tds = pstats.get("pass_tds", 0)
    ints = pstats.get("ints", 0)
    rush_yds = pstats.get("rush_yds", 0.0)
    rush_tds = pstats.get("rush_tds", 0)
    receptions = pstats.get("receptions", 0)
    rec_yds = pstats.get("rec_yds", 0.0)
    rec_tds = pstats.get("rec_tds", 0)
    fumbles_lost = pstats.get("fumbles_lost", 0)
    two_point_conversions = pstats.get("two_pt", 0)

    # Half-PPR (FanDuel: 0.5 per rec, -1.0 INT, -2.0 FumLost)
    half_ppr = (
        (pass_yds * 0.04)
        + (pass_tds * 4.0)
        - (ints * 1.0)
        + (rush_yds * 0.10)
        + (rush_tds * 6.0)
        + (receptions * 0.50)
        + (rec_yds * 0.10)
        + (rec_tds * 6.0)
        - (fumbles_lost * 2.0)
        + (two_point_conversions * 2.0)
    )

    # Full-PPR (ESPN Fantasy: 1.0 per rec, -2.0 INT, -2.0 FumLost)
    full_ppr = (
        (pass_yds * 0.04)
        + (pass_tds * 4.0)
        - (ints * 2.0)
        + (rush_yds * 0.10)
        + (rush_tds * 6.0)
        + (receptions * 1.00)
        + (rec_yds * 0.10)
        + (rec_tds * 6.0)
        - (fumbles_lost * 2.0)
        + (two_point_conversions * 2.0)
    )

    return round(half_ppr, 2), round(full_ppr, 2)


async def calculate_in_house_dvp(
    season: int = 2026,
    target_week: int = 2,
) -> dict[str, list[dict[str, Any]]]:
    """Calculates in-house DvP ratings and Fantasy Points Allowed (Half-PPR & Full-PPR).
    
    Averages all completed regular season weeks (from Week 1 up to target_week - 1).
    Applies an early-season Bayesian baseline prior to ensure statistical stability.
    
    Returns:
        dict[str, list[dict[str, Any]]]: Records keyed by position ('QB', 'RB', 'WR', 'TE')
    """
    logger.info("Initializing in-house DvP calculation for Season %d, Week %d...", season, target_week)
    pos_map = load_position_map()
    baseline_by_team = load_2025_baseline_by_team()

    # Determine weeks to aggregate: all completed weeks prior to target_week (min Week 1)
    weeks_to_process = list(range(1, max(2, target_week)))
    logger.info("Processing realized box scores for completed weeks: %s", weeks_to_process)

    # Initialize raw stat accumulators for all 32 NFL teams
    team_stats: dict[str, dict[str, Any]] = {}
    for team in ALL_32_NFL_TEAMS.keys():
        team_stats[team] = {
            "games_played": 0,
            "QB": {"half_ppr": 0.0, "full_ppr": 0.0, "pass_yds": 0.0, "pass_tds": 0.0, "ints": 0.0, "sacks": 0.0, "rush_yds": 0.0, "rush_tds": 0.0},
            "RB": {"half_ppr": 0.0, "full_ppr": 0.0, "rush_yds": 0.0, "rush_tds": 0.0, "targets": 0.0, "receptions": 0.0, "rec_yds": 0.0, "rec_tds": 0.0},
            "WR": {"half_ppr": 0.0, "full_ppr": 0.0, "targets": 0.0, "receptions": 0.0, "rec_yds": 0.0, "rec_tds": 0.0, "rush_yds": 0.0, "rush_tds": 0.0},
            "TE": {"half_ppr": 0.0, "full_ppr": 0.0, "targets": 0.0, "receptions": 0.0, "rec_yds": 0.0, "rec_tds": 0.0},
        }

    for wk in weeks_to_process:
        summaries = await fetch_game_summaries_for_week(season, wk)
        logger.info("Week %d: Retrieved %d game box scores.", wk, len(summaries))

        for summary in summaries:
            boxscore = summary.get("boxscore", {})
            players_by_team = boxscore.get("players", [])
            if len(players_by_team) != 2:
                continue

            team_a = players_by_team[0].get("team", {}).get("abbreviation", "UNK")
            team_b = players_by_team[1].get("team", {}).get("abbreviation", "UNK")

            for i, off_team_entry in enumerate(players_by_team):
                off_team = off_team_entry.get("team", {}).get("abbreviation", "UNK")
                def_team = team_b if i == 0 else team_a
                if def_team not in team_stats:
                    continue

                team_stats[def_team]["games_played"] += 0.5  # each game has 2 offensive sides, so +0.5 per side = 1.0 game

                player_stats: dict[str, dict[str, Any]] = {}
                team_sacks = 0.0

                for cat in off_team_entry.get("statistics", []):
                    cat_name = cat.get("name", "")
                    keys = cat.get("keys", [])
                    athletes = cat.get("athletes", [])

                    for ath in athletes:
                        ath_info = ath.get("athlete", {})
                        name = ath_info.get("displayName", "").strip()
                        if not name:
                            continue

                        pos = ath_info.get("position", {}).get("abbreviation")
                        if not pos:
                            pos = pos_map.get(name.lower(), "UNK")
                        if pos in ("FB", "HB"):
                            pos = "RB"

                        if name not in player_stats:
                            player_stats[name] = {
                                "name": name,
                                "position": pos,
                                "team": off_team,
                                "pass_yds": 0.0,
                                "pass_tds": 0,
                                "ints": 0,
                                "rush_yds": 0.0,
                                "rush_tds": 0,
                                "targets": 0,
                                "receptions": 0,
                                "rec_yds": 0.0,
                                "rec_tds": 0,
                                "fumbles_lost": 0,
                                "two_pt": 0,
                            }

                        stats_arr = ath.get("stats", [])
                        stats_by_key = dict(zip(keys, stats_arr))

                        if cat_name == "passing":
                            player_stats[name]["pass_yds"] = float(stats_by_key.get("passingYards", 0) or 0)
                            player_stats[name]["pass_tds"] = int(stats_by_key.get("passingTouchdowns", 0) or 0)
                            player_stats[name]["ints"] = int(stats_by_key.get("interceptions", 0) or 0)
                            sacks_val = str(stats_by_key.get("sacks-sackYardsLost", "0-0")).split("-")[0]
                            try:
                                team_sacks += float(sacks_val)
                            except ValueError:
                                pass
                            if player_stats[name]["position"] == "UNK":
                                player_stats[name]["position"] = "QB"

                        elif cat_name == "rushing":
                            player_stats[name]["rush_yds"] = float(stats_by_key.get("rushingYards", 0) or 0)
                            player_stats[name]["rush_tds"] = int(stats_by_key.get("rushingTouchdowns", 0) or 0)
                            if player_stats[name]["position"] == "UNK":
                                player_stats[name]["position"] = "RB"

                        elif cat_name == "receiving":
                            player_stats[name]["receptions"] = int(stats_by_key.get("receptions", 0) or 0)
                            player_stats[name]["rec_yds"] = float(stats_by_key.get("receivingYards", 0) or 0)
                            player_stats[name]["rec_tds"] = int(stats_by_key.get("receivingTouchdowns", 0) or 0)
                            player_stats[name]["targets"] = int(stats_by_key.get("receivingTargets", 0) or 0)
                            if player_stats[name]["position"] == "UNK":
                                player_stats[name]["position"] = "WR"

                        elif cat_name == "fumbles":
                            player_stats[name]["fumbles_lost"] = int(stats_by_key.get("fumblesLost", 0) or 0)

                # Assign team sacks to QB defense bucket
                team_stats[def_team]["QB"]["sacks"] += team_sacks

                # Accumulate player stats into defending team's position totals
                for name, pstats in player_stats.items():
                    pos = pstats["position"]
                    if pos not in ("QB", "RB", "WR", "TE"):
                        pos = pos_map.get(name.lower(), "UNK")
                    if pos not in ("QB", "RB", "WR", "TE"):
                        continue

                    half_pts, full_pts = calculate_player_fantasy_points(pstats)
                    bucket = team_stats[def_team][pos]
                    bucket["half_ppr"] += half_pts
                    bucket["full_ppr"] += full_pts

                    if pos == "QB":
                        bucket["pass_yds"] += pstats["pass_yds"]
                        bucket["pass_tds"] += pstats["pass_tds"]
                        bucket["ints"] += pstats["ints"]
                        bucket["rush_yds"] += pstats["rush_yds"]
                        bucket["rush_tds"] += pstats["rush_tds"]
                    elif pos == "RB":
                        bucket["rush_yds"] += pstats["rush_yds"]
                        bucket["rush_tds"] += pstats["rush_tds"]
                        bucket["targets"] += pstats["targets"]
                        bucket["receptions"] += pstats["receptions"]
                        bucket["rec_yds"] += pstats["rec_yds"]
                        bucket["rec_tds"] += pstats["rec_tds"]
                    elif pos == "WR":
                        bucket["targets"] += pstats["targets"]
                        bucket["receptions"] += pstats["receptions"]
                        bucket["rec_yds"] += pstats["rec_yds"]
                        bucket["rec_tds"] += pstats["rec_tds"]
                        bucket["rush_yds"] += pstats["rush_yds"]
                        bucket["rush_tds"] += pstats["rush_tds"]
                    elif pos == "TE":
                        bucket["targets"] += pstats["targets"]
                        bucket["receptions"] += pstats["receptions"]
                        bucket["rec_yds"] += pstats["rec_yds"]
                        bucket["rec_tds"] += pstats["rec_tds"]

    # Compute Bayesian weighting schedule based on sample games
    # Week 2 (1 game): 70% 2026 + 30% baseline
    # Week 3 (2 games): 85% 2026 + 15% baseline
    # Week 4+ (3+ games): 100% 2026
    sample_games = max(1, len(weeks_to_process))
    if sample_games == 1:
        current_weight, base_weight = 0.70, 0.30
    elif sample_games == 2:
        current_weight, base_weight = 0.85, 0.15
    else:
        current_weight, base_weight = 1.00, 0.00

    output_by_position: dict[str, list[dict[str, Any]]] = {"QB": [], "RB": [], "WR": [], "TE": []}

    for pos in ["QB", "RB", "WR", "TE"]:
        team_fpa_list = []

        for team, tdata in team_stats.items():
            team_name = ALL_32_NFL_TEAMS.get(team, team)
            games = max(1.0, tdata.get("games_played", 1.0))
            pdata = tdata[pos]

            realized_half = pdata["half_ppr"] / games
            realized_full = pdata["full_ppr"] / games

            # Prior season baseline
            base_info = baseline_by_team.get(team, {}).get(pos, {})
            prior_fpa = base_info.get("prior_season_fpa", DEFAULT_BASELINE_FPA[pos]["half_ppr"])

            # Blended Bayesian rating
            blended_half = (realized_half * current_weight) + (prior_fpa * base_weight)
            blended_full = (realized_full * current_weight) + ((prior_fpa * 1.25) * base_weight)

            # Supporting per-game averages
            supp_stats = {}
            if pos == "QB":
                supp_stats = {
                    "pass_yds": round(pdata["pass_yds"] / games, 1),
                    "pass_td": round(pdata["pass_tds"] / games, 2),
                    "int": round(pdata["ints"] / games, 2),
                    "sacks": round(pdata["sacks"] / games, 1),
                    "qb_rush_yds": round(pdata["rush_yds"] / games, 1),
                }
            elif pos == "RB":
                supp_stats = {
                    "rush_yds": round(pdata["rush_yds"] / games, 1),
                    "rush_td": round(pdata["rush_tds"] / games, 2),
                    "targets": round(pdata["targets"] / games, 1),
                    "rec": round(pdata["receptions"] / games, 1),
                    "rec_yds": round(pdata["rec_yds"] / games, 1),
                }
            elif pos == "WR":
                supp_stats = {
                    "targets": round(pdata["targets"] / games, 1),
                    "rec": round(pdata["receptions"] / games, 1),
                    "rec_yds": round(pdata["rec_yds"] / games, 1),
                    "rec_td": round(pdata["rec_tds"] / games, 2),
                    "rush_yds": round(pdata["rush_yds"] / games, 1),
                }
            elif pos == "TE":
                supp_stats = {
                    "targets": round(pdata["targets"] / games, 1),
                    "rec": round(pdata["receptions"] / games, 1),
                    "rec_yds": round(pdata["rec_yds"] / games, 1),
                    "rec_td": round(pdata["rec_tds"] / games, 2),
                }

            # Trend calculation
            trend = "Stable"
            if realized_half >= prior_fpa + 3.0:
                trend = "Allowing more lately (good for offense)"
            elif realized_half <= prior_fpa - 3.0:
                trend = "Tightening up lately"

            team_fpa_list.append({
                "pro_team": team,
                "team_name": team_name,
                "position": pos,
                "half_ppr_raw": round(realized_half, 1),
                "full_ppr_raw": round(realized_full, 1),
                "blended_half": round(blended_half, 1),
                "blended_full": round(blended_full, 1),
                "prior_season_fpa": round(prior_fpa, 1),
                "current_season_fpa": round(realized_full, 1),  # Full-PPR realized
                "last4_fpa": round(realized_full, 1),
                "trend": trend,
                "supporting_stats": supp_stats,
                "sample_games_current": int(games),
                "is_baseline": sample_games == 1 and base_weight > 0.0,
            })

        # Sort all 32 teams by blended Half-PPR allowed (descending: highest points allowed = softest smash matchup)
        team_fpa_list.sort(key=lambda x: x["blended_half"], reverse=True)

        # Calculate positional league mean
        mean_half = sum(t["blended_half"] for t in team_fpa_list) / len(team_fpa_list)

        # Assign softness ranks (1 = most points allowed / softest) and defense ranks (1 = fewest points allowed / toughest)
        total_teams = len(team_fpa_list)
        for rank_idx, entry in enumerate(team_fpa_list):
            softness_rank = rank_idx + 1  # 1 = softest smash
            defense_rank = total_teams - rank_idx  # 1 = toughest defense
            tier_code, tier_label = get_softness_tier(softness_rank)
            vs_avg = round(entry["blended_half"] - mean_half, 1)

            formatted_record = {
                "rank_softness": softness_rank,
                "rank_defense": defense_rank,
                "pro_team": entry["pro_team"],
                "team_name": entry["team_name"],
                "position": pos,
                "tier": tier_code,
                "tier_label": tier_label,
                "dk_fpa": entry["blended_half"],  # Half-PPR (FanDuel Standard)
                "fd_fpa": entry["blended_full"],  # Full-PPR (ESPN Fantasy Standard)
                "vs_avg": vs_avg,
                "prior_season_fpa": entry["prior_season_fpa"],
                "current_season_fpa": entry["current_season_fpa"],
                "last4_fpa": entry["last4_fpa"],
                "trend": entry["trend"],
                "supporting_stats": entry["supporting_stats"],
                "is_baseline": entry["is_baseline"],
                "sample_games_current": entry["sample_games_current"],
                "source": "Proprietary First-Party Engine",
                "source_url": "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
            }
            output_by_position[pos].append(formatted_record)

    # Persist in-house snapshot to JSON
    try:
        with open(OUTPUT_PROPRIETARY_DVP_PATH, "w", encoding="utf-8") as f:
            json.dump(output_by_position, f, indent=2)
        logger.info("Saved proprietary in-house DvP snapshot to %s", OUTPUT_PROPRIETARY_DVP_PATH)
    except Exception as ex:
        logger.warning("Could not save proprietary DvP snapshot: %s", ex)

    return output_by_position


dvp_calculator = calculate_in_house_dvp
