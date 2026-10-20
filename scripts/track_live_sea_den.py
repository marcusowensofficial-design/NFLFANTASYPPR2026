"""
Live In-Game Scoring & Portfolio Auditor for Seattle Seahawks @ Denver Broncos.

Event ID: 401872995 (ESPN API)
Features:
1. Connects to ESPN live summary API in real time.
2. Computes official FanDuel Half-PPR scoring for all players and D/STs.
3. Computes MVP (1.5x) and FLEX (1.0x) scoring for:
   - Our Quant Portfolio (150 lineups)
   - Mike McClure's Portfolio (150 lineups)
4. Displays Top Lineups, Head-to-Head Scoreboard, and Current Slate Optimal.
"""

import sys
import os
import json
import urllib.request
import pandas as pd
from typing import Dict, Any, List, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUR_LINEUPS_CSV = os.path.join(DATA_DIR, "fanduel_sea_den_150_readable.csv")
MIKE_LINEUPS_CSV = os.path.join(DATA_DIR, "MIKE_MCCLURES_LINEUPS_readable.csv")

EVENT_ID = "401872995"
URL = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={EVENT_ID}"


def fetch_live_summary() -> Dict[str, Any]:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_fanduel_points(summary: Dict[str, Any]) -> Dict[str, float]:
    """Calculates official FanDuel Half-PPR fantasy scoring from live ESPN boxscore."""
    scores: Dict[str, float] = {
        "Seattle Seahawks": 0.0,
        "Denver Broncos": 0.0,
        "Jason Myers": 0.0,
        "Wil Lutz": 0.0
    }

    boxscore = summary.get("boxscore", {})
    players_data = boxscore.get("players", [])
    teams_data = boxscore.get("teams", [])

    # 1. Parse Offensive & Kicking Player Stats
    for team_entry in players_data:
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
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    ints = float(stat_dict.get("INT", 0) or 0)
                    pts = (yds * 0.04) + (tds * 4.0) - (ints * 1.0)
                    if yds >= 300.0:
                        pts += 3.0
                    scores[name] += pts

                elif cat == "rushing":
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    pts = (yds * 0.1) + (tds * 6.0)
                    if yds >= 100.0:
                        pts += 3.0
                    scores[name] += pts

                elif cat == "receiving":
                    rec = float(stat_dict.get("REC", 0) or 0)
                    yds = float(stat_dict.get("YDS", 0) or 0)
                    tds = float(stat_dict.get("TD", 0) or 0)
                    pts = (rec * 0.5) + (yds * 0.1) + (tds * 6.0)
                    if yds >= 100.0:
                        pts += 3.0
                    scores[name] += pts

                elif cat == "kicking":
                    xp_str = str(stat_dict.get("XP", "0/0"))
                    xp_made = float(xp_str.split("/")[0]) if "/" in xp_str else float(xp_str or 0)
                    fg_str = str(stat_dict.get("FG", "0/0"))
                    fg_made = float(fg_str.split("/")[0]) if "/" in fg_str else 0.0
                    pts = (fg_made * 3.0) + (xp_made * 1.0)
                    scores[name] += pts

                elif cat == "fumbles":
                    fum_lost = float(stat_dict.get("LOST", 0) or 0)
                    scores[name] -= (fum_lost * 2.0)

    # 2. Parse Team D/ST Stats
    # Extract opponent score, sacks, turnovers
    comp = summary.get("header", {}).get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    team_scores = {}
    for c in competitors:
        t_name = c.get("team", {}).get("displayName", "")
        pts = float(c.get("score", 0) or 0)
        team_scores[t_name] = pts

    for team_entry in players_data:
        team_info = team_entry.get("team", {})
        team_display = team_info.get("displayName", "")
        opp_display = "Denver Broncos" if "Seahawks" in team_display else "Seattle Seahawks"
        opp_points = team_scores.get(opp_display, 0.0)

        # Base Points Allowed scoring
        if opp_points == 0:
            dst_pts = 10.0
        elif opp_points <= 6:
            dst_pts = 7.0
        elif opp_points <= 13:
            dst_pts = 4.0
        elif opp_points <= 20:
            dst_pts = 1.0
        elif opp_points <= 27:
            dst_pts = 0.0
        elif opp_points <= 34:
            dst_pts = -1.0
        else:
            dst_pts = -4.0

        for stat_group in team_entry.get("statistics", []):
            cat = stat_group.get("name", "")
            labels = stat_group.get("labels", [])
            for athlete in stat_group.get("athletes", []):
                stats = athlete.get("stats", [])
                stat_dict = dict(zip(labels, stats))
                if cat == "defensive":
                    sacks = float(stat_dict.get("SACKS", 0) or 0)
                    ff = float(stat_dict.get("FF", 0) or 0)
                    dst_pts += sacks * 1.0
                elif cat == "interceptions":
                    ints = float(stat_dict.get("INT", 0) or 0)
                    int_tds = float(stat_dict.get("TD", 0) or 0)
                    dst_pts += (ints * 2.0) + (int_tds * 6.0)

        scores[team_display] = dst_pts

    # Normalize name keys
    alias_map = {
        "Marvin Mims": "Marvin Mims Jr.",
        "Lil’Jordan Humphrey": "Lil'Jordan Humphrey",
        "J.K. Dobbins": "J.K. Dobbins",
        "AJ Barner": "AJ Barner",
        "Jaxon Smith-Njigba": "Jaxon Smith-Njigba"
    }
    for alias, standard in alias_map.items():
        if alias in scores and standard not in scores:
            scores[standard] = scores[alias]

    return {k: round(v, 2) for k, v in scores.items()}


def clean_player_name(val: Any) -> str:
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return ""
    if ":" in s:
        # Format "Id:Nickname"
        return s.split(":", 1)[1].strip()
    if " (" in s:
        # Format "Jaxon Smith-Njigba (SEA WR) - $19,500"
        return s.split(" (", 1)[0].strip()
    return s


def score_lineups(csv_path: str, scores: Dict[str, float]) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    # Standardize column names
    col_map = {}
    for col in df.columns:
        c_clean = col.replace(" ", "").upper()
        if c_clean == "MVP":
            col_map[col] = "MVP"
        elif c_clean in ["FLEX1", "ANYFLEX"]:
            col_map[col] = "FLEX1"
        elif c_clean in ["FLEX2", "ANYFLEX.1"]:
            col_map[col] = "FLEX2"
        elif c_clean in ["FLEX3", "ANYFLEX.2"]:
            col_map[col] = "FLEX3"
        elif c_clean in ["FLEX4", "ANYFLEX.3"]:
            col_map[col] = "FLEX4"
        elif c_clean in ["FLEX5", "ANYFLEX.4"]:
            col_map[col] = "FLEX5"
    df = df.rename(columns=col_map)
    
    results = []
    
    for idx, row in df.iterrows():
        mvp = clean_player_name(row.get('MVP', ''))
        mvp_score = scores.get(mvp, 0.0) * 1.5
        
        flex_names = [clean_player_name(row.get(f'FLEX{i}', '')) for i in range(1, 6)]
        f_scores = [scores.get(p, 0.0) for p in flex_names]
        
        total_score = round(mvp_score + sum(f_scores), 2)
        
        salary_spent = row.get('Salary Spent') or row.get('Salary_Spent') or 0
        
        results.append({
            'Lineup_Num': idx + 1,
            'MVP': mvp,
            'MVP_FP': round(mvp_score, 2),
            'FLEX1': f"{flex_names[0]} ({f_scores[0]:.1f})",
            'FLEX2': f"{flex_names[1]} ({f_scores[1]:.1f})",
            'FLEX3': f"{flex_names[2]} ({f_scores[2]:.1f})",
            'FLEX4': f"{flex_names[3]} ({f_scores[3]:.1f})",
            'FLEX5': f"{flex_names[4]} ({f_scores[4]:.1f})",
            'Total_FP': total_score,
            'Salary_Spent': salary_spent
        })
        
    df_res = pd.DataFrame(results).sort_values(by='Total_FP', ascending=False)
    df_res['Rank'] = range(1, len(df_res) + 1)
    return df_res


def run_live_audit():
    print("=" * 115)
    print("      REAL-TIME LIVE IN-GAME AUDITOR: SEATTLE SEAHAWKS @ DENVER BRONCOS (WEEK 6 SHOWDOWN)")
    print("=" * 115)
    
    try:
        summary = fetch_live_summary()
    except Exception as e:
        print(f"Error connecting to live ESPN feed: {e}")
        return

    comp = summary.get("header", {}).get("competitions", [{}])[0]
    status = comp.get("status", {}).get("type", {})
    status_desc = status.get("description", "Scheduled")
    detail = status.get("detail", "")
    
    print(f"\n[LIVE CLOCK]: {status_desc} | {detail}")
    for c in comp.get("competitors", []):
        t_name = c.get("team", {}).get("displayName", "")
        pts = c.get("score", "0")
        print(f"  {t_name:<20}: {pts} pts")

    scores = parse_fanduel_points(summary)
    
    # Active players output
    active_scorers = {k: v for k, v in scores.items() if v > 0.0 or "Seahawks" in k or "Broncos" in k}
    print(f"\n[LIVE SCORERS] ({len(active_scorers)} tracked):")
    sorted_players = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    for p, s in sorted_players:
        if s > 0:
            print(f"  {p:<24}: {s:>5.2f} FP (1.5x MVP: {s*1.5:>5.2f} FP)")

    # Score Our 150 Lineups
    df_our = score_lineups(OUR_LINEUPS_CSV, scores)
    # Score Mike McClure's 150 Lineups
    df_mike = score_lineups(MIKE_LINEUPS_CSV, scores)

    print("\n" + "=" * 115)
    print("OUR QUANT MODEL (150 LINEUPS) - CURRENT TOP 5 LINEUPS")
    print("=" * 115)
    if not df_our.empty:
        cols = ['Rank', 'Lineup_Num', 'MVP', 'MVP_FP', 'FLEX1', 'FLEX2', 'FLEX3', 'FLEX4', 'FLEX5', 'Total_FP']
        print(df_our.head(5)[cols].to_string(index=False))
        our_best = df_our.iloc[0]['Total_FP']
        our_top10_avg = df_our.head(10)['Total_FP'].mean()
        our_mean = df_our['Total_FP'].mean()
    else:
        print("  Our lineups file not found.")
        our_best = our_top10_avg = our_mean = 0.0

    print("\n" + "=" * 115)
    print("MIKE MCCLURE SPORTSLINE MODEL (150 LINEUPS) - CURRENT TOP 5 LINEUPS")
    print("=" * 115)
    if not df_mike.empty:
        cols = ['Rank', 'Lineup_Num', 'MVP', 'MVP_FP', 'FLEX1', 'FLEX2', 'FLEX3', 'FLEX4', 'FLEX5', 'Total_FP']
        print(df_mike.head(5)[cols].to_string(index=False))
        mike_best = df_mike.iloc[0]['Total_FP']
        mike_top10_avg = df_mike.head(10)['Total_FP'].mean()
        mike_mean = df_mike['Total_FP'].mean()
    else:
        print("  Mike McClure lineups file not found.")
        mike_best = mike_top10_avg = mike_mean = 0.0

    print("\n" + "=" * 115)
    print("HEAD-TO-HEAD MATCH SCORECARD: QUANT ENGINE VS. MIKE MCCLURE")
    print("=" * 115)
    print(f"  Our #1 Best Lineup:         {our_best:>6.2f} FP  vs.  Mike's #1 Best Lineup:         {mike_best:>6.2f} FP")
    print(f"  Our Top 10 Lineups Average: {our_top10_avg:>6.2f} FP  vs.  Mike's Top 10 Lineups Average: {mike_top10_avg:>6.2f} FP")
    print(f"  Our 150-Portfolio Average:  {our_mean:>6.2f} FP  vs.  Mike's 150-Portfolio Average:  {mike_mean:>6.2f} FP")
    
    if our_best > mike_best:
        print(f"\n  >>> LEADER: OUR QUANT ENGINE IS WINNING BY +{our_best - mike_best:.2f} FP! <<<")
    elif mike_best > our_best:
        print(f"\n  >>> LEADER: MIKE MCCLURE IS LEADING BY +{mike_best - our_best:.2f} FP! <<<")
    else:
        print("\n  >>> STATUS: TIED (PRE-GAME OR IDENTICAL SCORES) <<<")
    print("=" * 115)


if __name__ == "__main__":
    run_live_audit()
