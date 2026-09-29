import urllib.request
import json
import pandas as pd

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

dst_results = []

for eid, gname in EVENT_IDS:
    try:
        data = fetch_summary(eid)
        header = data.get("header", {})
        comps = header.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        
        # Team scores
        scores = {}
        for c in competitors:
            tm = c.get("team", {}).get("abbreviation")
            sc = int(c.get("score", 0) or 0)
            scores[tm] = sc

        boxscore = data.get("boxscore", {})
        teams_stats = boxscore.get("teams", [])
        
        # Calculate for each team
        for t_idx, t_box in enumerate(teams_stats):
            tm_abbr = t_box.get("team", {}).get("abbreviation")
            opp_abbr = competitors[1 - t_idx].get("team", {}).get("abbreviation")
            pts_allowed = scores.get(opp_abbr, 0)
            
            # PA points on FanDuel:
            # 0: +10, 1-6: +7, 7-13: +4, 14-20: +1, 21-27: 0, 28-34: -1, 35+: -4
            if pts_allowed == 0:
                pa_pts = 10
            elif pts_allowed <= 6:
                pa_pts = 7
            elif pts_allowed <= 13:
                pa_pts = 4
            elif pts_allowed <= 20:
                pa_pts = 1
            elif pts_allowed <= 27:
                pa_pts = 0
            elif pts_allowed <= 34:
                pa_pts = -1
            else:
                pa_pts = -4
                
            sacks = 0
            turnovers_forced = 0
            def_tds = 0
            safeties = 0
            blocked_kicks = 0
            
            # Check team statistics
            for st in t_box.get("statistics", []):
                name = st.get("name")
                val = st.get("displayValue")
                if name == "sacks":
                    sacks = float(val or 0)
                elif name == "turnovers": # this is turnovers committed by team, opp turnovers committed = turnovers forced
                    pass
            
            # Look at players defensive stats
            # In ESPN boxscore, players has defensive stats
            for p_entry in boxscore.get("players", []):
                if p_entry.get("team", {}).get("abbreviation") == tm_abbr:
                    for sg in p_entry.get("statistics", []):
                        if sg.get("name") == "defensive":
                            lbls = sg.get("labels", [])
                            for ath in sg.get("athletes", []):
                                s_dict = dict(zip(lbls, ath.get("stats", [])))
                                # SACKS, INT, TD
                                def_tds += float(s_dict.get("TD", 0) or 0)
                        elif sg.get("name") == "interceptions":
                            lbls = sg.get("labels", [])
                            for ath in sg.get("athletes", []):
                                s_dict = dict(zip(lbls, ath.get("stats", [])))
                                turnovers_forced += float(s_dict.get("INT", 0) or 0)
                                def_tds += float(s_dict.get("TD", 0) or 0)

            fd_dst_score = pa_pts + (sacks * 1.0) + (turnovers_forced * 2.0) + (def_tds * 6.0)
            dst_results.append({
                "team": tm_abbr,
                "opp": opp_abbr,
                "pa": pts_allowed,
                "sacks": sacks,
                "turnovers": turnovers_forced,
                "def_tds": def_tds,
                "fd_pts": fd_dst_score
            })
    except Exception as e:
        print(f"Error {gname}: {e}")

df_dst = pd.DataFrame(dst_results)
df_dst = df_dst.sort_values(by="fd_pts", ascending=False)
print("--- D/ST SCORES TODAY ---")
print(df_dst.to_string(index=False))
