import urllib.request
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np

# Load our slate data
csv_path = "data/FDMAINSLATE9-27-2026SUNDAYGAMES.csv"
import sys
sys.path.insert(0, ".")
from scripts.solve_main_slate_matrix import load_and_enrich_slate

df_slate, vegas = load_and_enrich_slate(csv_path)

# 13 games on Sunday Main Slate
EVENT_IDS = [
    ("401872960", "BAL@DAL"),
    ("401872961", "LV@NO"),
    ("401872953", "LAC@BUF"),
    ("401872949", "CAR@CLE"),
    ("401872954", "NYJ@DET"),
    ("401872951", "HOU@IND"),
    ("401872952", "KC@MIA"),
    ("401872956", "TEN@NYG"),
    ("401872950", "CIN@PIT"),
    ("401872955", "SEA@WSH"),
    ("401872957", "NE@JAX"),
    ("401872958", "ARI@SF"),
    ("401872959", "MIN@TB"),
]

def fetch_summary(event_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

player_actuals = {}
dst_actuals = {}
game_scores = {}

for eid, gname in EVENT_IDS:
    try:
        data = fetch_summary(eid)
        header = data.get("header", {})
        comps = header.get("competitions", [{}])[0]
        tm_scores = {}
        for c in comps.get("competitors", []):
            tm = c.get("team", {}).get("abbreviation")
            sc = int(c.get("score", 0) or 0)
            tm_scores[tm] = sc
        game_scores[gname] = tm_scores

        boxscore = data.get("boxscore", {})
        players_data = boxscore.get("players", [])
        
        # Team stats for D/ST
        teams_box = boxscore.get("teams", [])
        # We also parse individual athlete boxscores
        for team_entry in players_data:
            tm_abbr = team_entry.get("team", {}).get("abbreviation", "")
            for stat_group in team_entry.get("statistics", []):
                cat = stat_group.get("name", "")
                labels = stat_group.get("labels", [])
                for athlete in stat_group.get("athletes", []):
                    name = athlete.get("athlete", {}).get("displayName", "")
                    stats = athlete.get("stats", [])
                    stat_dict = dict(zip(labels, stats))

                    if name not in player_actuals:
                        player_actuals[name] = {
                            "name": name,
                            "team": tm_abbr,
                            "pass_yds": 0, "pass_tds": 0, "ints": 0,
                            "rush_yds": 0, "rush_tds": 0, "carries": 0,
                            "rec_yds": 0, "rec_tds": 0, "receptions": 0, "targets": 0,
                            "fumbles_lost": 0, "two_pt": 0,
                            "half_ppr": 0.0, "full_ppr": 0.0
                        }
                    
                    p = player_actuals[name]
                    if cat == "passing":
                        p["pass_yds"] += float(stat_dict.get("YDS", 0) or 0)
                        p["pass_tds"] += float(stat_dict.get("TD", 0) or 0)
                        p["ints"] += float(stat_dict.get("INT", 0) or 0)
                    elif cat == "rushing":
                        p["carries"] += float(stat_dict.get("CAR", 0) or 0)
                        p["rush_yds"] += float(stat_dict.get("YDS", 0) or 0)
                        p["rush_tds"] += float(stat_dict.get("TD", 0) or 0)
                    elif cat == "receiving":
                        p["receptions"] += float(stat_dict.get("REC", 0) or 0)
                        p["rec_yds"] += float(stat_dict.get("YDS", 0) or 0)
                        p["rec_tds"] += float(stat_dict.get("TD", 0) or 0)
                        p["targets"] += float(stat_dict.get("TGTS", 0) or 0)

        # D/ST points from scoring & defense
        # We can calculate D/ST points roughly or check team defenses
    except Exception as e:
        print(f"Error processing {gname} ({eid}): {e}")

# Calculate fantasy points for each player
for name, p in player_actuals.items():
    # Passing
    pass_pts = (p["pass_yds"] * 0.04) + (p["pass_tds"] * 4.0) - (p["ints"] * 1.0)
    if p["pass_yds"] >= 300.0:
        pass_pts += 3.0
    
    # Rushing
    rush_pts = (p["rush_yds"] * 0.1) + (p["rush_tds"] * 6.0)
    if p["rush_yds"] >= 100.0:
        rush_pts += 3.0
        
    # Receiving
    rec_base = (p["rec_yds"] * 0.1) + (p["rec_tds"] * 6.0)
    if p["rec_yds"] >= 100.0:
        rec_base += 3.0
        
    p["half_ppr"] = round(pass_pts + rush_pts + rec_base + (p["receptions"] * 0.5), 2)
    p["full_ppr"] = round(pass_pts + rush_pts + rec_base + (p["receptions"] * 1.0), 2)

# Save actuals to json
with open("data/week3_sunday_actuals.json", "w") as f:
    json.dump({"game_scores": game_scores, "players": player_actuals}, f, indent=2)

print("Saved actuals. Total players processed:", len(player_actuals))
