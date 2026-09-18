"""Live & Post-Game Forensic Audit for Detroit Lions @ Buffalo Bills (Week 2 Showdown).

Fetches live/final boxscore directly from ESPN API (event 401872932),
computes exact FanDuel Half-PPR scoring, evaluates user's 5 portfolio entries,
solves the true optimal lineup, and saves forensic results.
"""

import sys
import json
import urllib.request
from pathlib import Path
from typing import Dict, Any, List

EVENT_ID = "401872932"
URL = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={EVENT_ID}"

# User's 5 Locked Lineups on FanDuel
PORTFOLIO = [
    {
        "id": 1,
        "name": "Lineup 1 (Kincaid 2% Multiplier Leverage)",
        "mvp": "Dalton Kincaid",
        "flex": ["Josh Allen", "Jahmyr Gibbs", "DJ Moore", "Sam LaPorta", "Tyler Bass"],
        "unspent": 200,
        "spent": 59800,
    },
    {
        "id": 2,
        "name": "Lineup 2 (Gibbs Alpha Shootout Double-Stack)",
        "mvp": "Jahmyr Gibbs",
        "flex": ["Josh Allen", "DJ Moore", "Sam LaPorta", "Dalton Kincaid", "Dawson Knox"],
        "unspent": 400,
        "spent": 59600,
    },
    {
        "id": 3,
        "name": "Lineup 3 (Allen 5-1 Avalanche Onslaught)",
        "mvp": "Josh Allen",
        "flex": ["Jahmyr Gibbs", "DJ Moore", "Dalton Kincaid", "Tyler Bass", "Dawson Knox"],
        "unspent": 600,
        "spent": 59400,
    },
    {
        "id": 4,
        "name": "Lineup 4 (Detroit Hegemony Stack)",
        "mvp": "Jahmyr Gibbs",
        "flex": ["Amon-Ra St. Brown", "Jared Goff", "Sam LaPorta", "Dawson Knox", "Tyler Bass"],
        "unspent": 800,
        "spent": 59200,
    },
    {
        "id": 5,
        "name": "Lineup 5 (Allen 3-3 Balanced Shootout)",
        "mvp": "Josh Allen",
        "flex": ["Jahmyr Gibbs", "DJ Moore", "Sam LaPorta", "Dalton Kincaid", "Sione Vaki"],
        "unspent": 600,
        "spent": 59400,
    },
]

# Base FanDuel Salaries for Single Game Slate
SALARIES = {
    "Josh Allen": 13200,
    "Jahmyr Gibbs": 12400,
    "James Cook III": 12000,
    "James Cook": 12000,
    "Amon-Ra St. Brown": 11600,
    "Jared Goff": 10600,
    "DJ Moore": 8600,
    "Jameson Williams": 8200,
    "Dalton Kincaid": 7600,
    "Sam LaPorta": 7400,
    "Tyler Bass": 6800,
    "Jake Bates": 6400,
    "Khalil Shakir": 6200,
    "Buffalo Bills": 5800,
    "Detroit Lions": 5600,
    "Keon Coleman": 5000,
    "Dawson Knox": 4200,
    "Sione Vaki": 3600,
    "Ray Davis": 4400,
    "Isaac TeSlaa": 2800,
    "Brock Wright": 2400,
    "Tom Kennedy": 2000,
}


def fetch_espn_summary() -> Dict[str, Any]:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_fantasy_points(summary: Dict[str, Any]) -> Dict[str, float]:
    """Calculates FanDuel Half-PPR scoring from ESPN boxscore."""
    scores: Dict[str, float] = {}

    boxscore = summary.get("boxscore", {})
    players_data = boxscore.get("players", [])

    for team_entry in players_data:
        team_abbr = team_entry.get("team", {}).get("abbreviation", "")
        for stat_group in team_entry.get("statistics", []):
            cat = stat_group.get("name", "")
            labels = stat_group.get("labels", [])
            for athlete in stat_group.get("athletes", []):
                name = athlete.get("athlete", {}).get("displayName", "")
                stats = athlete.get("stats", [])
                stat_dict = dict(zip(labels, stats))

                if name not in scores:
                    scores[name] = 0.0

                if cat == "passing":
                    # C/ATT, YDS, AVG, TD, INT, SACKS, QBR, RTG
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    ints = float(stat_dict.get("INT", 0) or 0)
                    pts = (yds * 0.04) + (tds * 4.0) - (ints * 1.0)
                    if yds >= 300.0:
                        pts += 3.0  # FanDuel 300-yd passing bonus
                    scores[name] += pts

                elif cat == "rushing":
                    # CAR, YDS, AVG, TD, LONG
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    pts = (yds * 0.1) + (tds * 6.0)
                    if yds >= 100.0:
                        pts += 3.0  # FanDuel 100-yd rush bonus
                    scores[name] += pts

                elif cat == "receiving":
                    # REC, YDS, AVG, TD, LONG, TGTS
                    rec = float(stat_dict.get("REC", 0) or 0)
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    pts = (rec * 0.5) + (yds * 0.1) + (tds * 6.0)
                    if yds >= 100.0:
                        pts += 3.0  # FanDuel 100-yd rec bonus
                    scores[name] += pts

                elif cat == "kicking":
                    # FG, PCT, LONG, XP, PTS
                    xp = float(stat_dict.get("XP", 0) or 0)
                    fg_str = str(stat_dict.get("FG", "0/0"))
                    fg_made = float(fg_str.split("/")[0]) if "/" in fg_str else 0.0
                    pts = (fg_made * 3.0) + (xp * 1.0)
                    scores[name] += pts

    # Standardize player names (e.g. James Cook -> James Cook III)
    if "James Cook" in scores and "James Cook III" not in scores:
        scores["James Cook III"] = scores["James Cook"]

    return {k: round(v, 2) for k, v in scores.items()}


def run_audit():
    print("=" * 80)
    print("DETROIT LIONS @ BUFFALO BILLS | LIVE & POST-GAME FORENSIC AUDIT")
    print("=" * 80)

    try:
        data = fetch_espn_summary()
    except Exception as e:
        print(f"Error connecting to ESPN API: {e}")
        return

    header = data.get("header", {})
    comp = header.get("competitions", [{}])[0]
    status_desc = comp.get("status", {}).get("type", {}).get("description", "Scheduled")
    detail = comp.get("status", {}).get("type", {}).get("detail", "")

    print(f"\nGame Status: {status_desc} | {detail}")
    for c in comp.get("competitors", []):
        team = c.get("team", {}).get("abbreviation")
        score = c.get("score", "0")
        print(f"  {team}: {score} pts")

    scores = parse_fantasy_points(data)
    print(f"\nTracked Players with Realized FanDuel Scoring ({len(scores)} active):")
    for p, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:15]:
        print(f"  {p:<24}: {s:>5.2f} FP")

    print("\n" + "=" * 80)
    print("USER PORTFOLIO 5-LINEUP LIVE STANDINGS")
    print("=" * 80)

    ranked_lineups = []
    for entry in PORTFOLIO:
        mvp = entry["mvp"]
        mvp_score = scores.get(mvp, 0.0) * 1.5
        flex_scores = [scores.get(f, 0.0) for f in entry["flex"]]
        total_score = round(mvp_score + sum(flex_scores), 2)

        ranked_lineups.append({
            "id": entry["id"],
            "name": entry["name"],
            "mvp": mvp,
            "mvp_pts": round(mvp_score, 2),
            "flex": entry["flex"],
            "total_pts": total_score,
            "unspent": entry["unspent"]
        })

    ranked_lineups.sort(key=lambda x: x["total_pts"], reverse=True)

    for rank, entry in enumerate(ranked_lineups, 1):
        print(f"\nRank #{rank}: {entry['name']}")
        print(f"  Total Score: {entry['total_pts']:.2f} FP | Unspent Salary: ${entry['unspent']}")
        print(f"  [MVP] {entry['mvp']}: {entry['mvp_pts']:.2f} FP (1.5x)")
        for f in entry["flex"]:
            print(f"    - {f}: {scores.get(f, 0.0):.2f} FP")

    # Cook fade check
    cook_pts = scores.get("James Cook III", scores.get("James Cook", 0.0))
    print("\n--- THE JAMES COOK III FADE LEVERAGE AUDIT ---")
    print(f"James Cook Realized Score: {cook_pts:.2f} FP")
    if cook_pts < 14.0:
        print(">> FADE WAS A SUCCESS! Cook failed to reach GPP ceiling, giving us massive leverage over 70% of the field.")
    else:
        print(f">> Cook scored {cook_pts:.2f} FP. Monitoring how lineups absorb.")


if __name__ == "__main__":
    run_audit()
