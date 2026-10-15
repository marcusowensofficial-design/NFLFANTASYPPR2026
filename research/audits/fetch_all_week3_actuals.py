"""Fetch and calculate all official Week 3 2026 NFL player and D/ST actuals across all 16 games."""

import json
import urllib.request
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EVENT_IDS = [
    ("401872948", "ATL@GB", "TNF"),
    ("401872953", "LAC@BUF", "SUN"),
    ("401872949", "CAR@CLE", "SUN"),
    ("401872954", "NYJ@DET", "SUN"),
    ("401872951", "HOU@IND", "SUN"),
    ("401872952", "KC@MIA", "SUN"),
    ("401872956", "TEN@NYG", "SUN"),
    ("401872950", "CIN@PIT", "SUN"),
    ("401872955", "SEA@WSH", "SUN"),
    ("401872957", "NE@JAX", "SUN"),
    ("401872958", "ARI@SF", "SUN"),
    ("401872959", "MIN@TB", "SUN"),
    ("401872960", "BAL@DAL", "SUN"),
    ("401872961", "LV@NO", "SUN"),
    ("401872962", "LAR@DEN", "SNF"),
    ("401872963", "PHI@CHI", "MNF"),
]

def fetch_summary(event_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={event_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))

def calculate_dst_points(pts_allowed, sacks=0, ints=0, fumbles=0, def_tds=0, safeties=0, blocked=0):
    score = 0.0
    if pts_allowed == 0:
        score += 10.0
    elif 1 <= pts_allowed <= 6:
        score += 7.0
    elif 7 <= pts_allowed <= 13:
        score += 4.0
    elif 14 <= pts_allowed <= 20:
        score += 1.0
    elif 21 <= pts_allowed <= 27:
        score += 0.0
    elif 28 <= pts_allowed <= 34:
        score -= 1.0
    else:
        score -= 4.0
        
    score += sacks * 1.0
    score += ints * 2.0
    score += fumbles * 2.0
    score += def_tds * 6.0
    score += safeties * 2.0
    score += blocked * 2.0
    return max(0.0, score) # standard fantasy floor or raw

player_actuals = {}
dst_actuals = {}
game_scores = {}
sunday_players = {}

for eid, gname, slate_tag in EVENT_IDS:
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
        teams_box = boxscore.get("teams", [])

        # Process D/ST stats
        for t_entry in teams_box:
            tm = t_entry.get("team", {}).get("abbreviation")
            opp = [k for k in tm_scores.keys() if k != tm]
            opp_score = tm_scores[opp[0]] if opp else 0
            stats_dict = {st.get("name"): st.get("displayValue") for st in t_entry.get("statistics", [])}
            
            sacks = int(stats_dict.get("sacks", 0) or 0)
            ints = int(stats_dict.get("interceptions", 0) or 0)
            fum = int(stats_dict.get("fumblesRecovered", 0) or 0)
            def_tds = int(stats_dict.get("defensiveTouchdowns", 0) or 0)
            dst_pts = calculate_dst_points(opp_score, sacks=sacks, ints=ints, fumbles=fum, def_tds=def_tds)
            dst_actuals[tm] = {
                "team": tm,
                "game": gname,
                "pts_allowed": opp_score,
                "sacks": sacks,
                "ints": ints,
                "fumbles_recovered": fum,
                "def_tds": def_tds,
                "fantasy_points": dst_pts
            }

        # Process athlete individual stats
        for team_entry in players_data:
            tm_abbr = team_entry.get("team", {}).get("abbreviation", "")
            for stat_group in team_entry.get("statistics", []):
                cat = stat_group.get("name", "")
                labels = stat_group.get("labels", [])
                for athlete in stat_group.get("athletes", []):
                    name = athlete.get("athlete", {}).get("displayName", "")
                    pos = athlete.get("athlete", {}).get("position", {}).get("abbreviation", "")
                    stats = athlete.get("stats", [])
                    sdict = dict(zip(labels, stats))

                    if name not in player_actuals:
                        player_actuals[name] = {
                            "name": name,
                            "team": tm_abbr,
                            "pos": pos,
                            "game": gname,
                            "pass_yds": 0, "pass_tds": 0, "ints": 0,
                            "rush_yds": 0, "rush_tds": 0, "carries": 0,
                            "rec_yds": 0, "rec_tds": 0, "receptions": 0, "targets": 0,
                            "fumbles_lost": 0, "two_pt": 0,
                            "fg_made": 0, "xp_made": 0,
                            "half_ppr": 0.0, "full_ppr": 0.0
                        }
                    
                    p = player_actuals[name]
                    if cat == "passing":
                        p["pass_yds"] += float(sdict.get("YDS", 0) or 0)
                        p["pass_tds"] += float(sdict.get("TD", 0) or 0)
                        p["ints"] += float(sdict.get("INT", 0) or 0)
                    elif cat == "rushing":
                        p["carries"] += float(sdict.get("CAR", 0) or 0)
                        p["rush_yds"] += float(sdict.get("YDS", 0) or 0)
                        p["rush_tds"] += float(sdict.get("TD", 0) or 0)
                    elif cat == "receiving":
                        p["receptions"] += float(sdict.get("REC", 0) or 0)
                        p["rec_yds"] += float(sdict.get("YDS", 0) or 0)
                        p["rec_tds"] += float(sdict.get("TD", 0) or 0)
                        p["targets"] += float(sdict.get("TGTS", 0) or 0)
                    elif cat == "kicking":
                        fg_str = sdict.get("FG", "0/0")
                        xp_str = sdict.get("XP", "0/0")
                        try:
                            p["fg_made"] += int(fg_str.split("/")[0])
                            p["xp_made"] += int(xp_str.split("/")[0])
                        except:
                            pass
                    elif cat == "fumbles":
                        p["fumbles_lost"] += float(sdict.get("LOST", 0) or 0)

                    if slate_tag == "SUN":
                        sunday_players[name] = p

    except Exception as e:
        print(f"Error processing {gname} ({eid}): {e}")

# Calculate fantasy points for each player
for name, p in player_actuals.items():
    pass_pts = (p["pass_yds"] * 0.04) + (p["pass_tds"] * 4.0) - (p["ints"] * 1.0)
    if p["pass_yds"] >= 300.0: pass_pts += 3.0
    
    rush_pts = (p["rush_yds"] * 0.1) + (p["rush_tds"] * 6.0)
    if p["rush_yds"] >= 100.0: rush_pts += 3.0
        
    rec_base = (p["rec_yds"] * 0.1) + (p["rec_tds"] * 6.0)
    if p["rec_yds"] >= 100.0: rec_base += 3.0

    kicking_pts = (p["fg_made"] * 3.0) + (p["xp_made"] * 1.0)
    fum_loss = p["fumbles_lost"] * 2.0
        
    p["half_ppr"] = round(pass_pts + rush_pts + rec_base + kicking_pts - fum_loss + (p["receptions"] * 0.5), 2)
    p["full_ppr"] = round(pass_pts + rush_pts + rec_base + kicking_pts - fum_loss + (p["receptions"] * 1.0), 2)

# Write all week 3 actuals
out_all = {
    "week": 3,
    "season": 2026,
    "total_games": len(game_scores),
    "game_scores": game_scores,
    "dst_actuals": dst_actuals,
    "players": player_actuals
}

with open("data/week3_all_actuals.json", "w", encoding="utf-8") as f:
    json.dump(out_all, f, indent=2)

print(f"✅ Processed all 16 games. Total players: {len(player_actuals)}. Saved data/week3_all_actuals.json.")
