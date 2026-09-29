"""Sync official live NFL injuries from ESPN API for all 32 teams into data/injuries_live_2026.json."""

import json
import urllib.request
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

def sync_injuries():
    print(f"Connecting to ESPN Live Injuries API: {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    season_info = data.get("season", {})
    team_injuries_list = data.get("injuries", [])

    all_injuries = []
    out_statuses = {"out", "injured reserve", "ir", "pup", "suspended"}

    for team_block in team_injuries_list:
        team_name = team_block.get("displayName", "Unknown Team")
        injuries = team_block.get("injuries", [])
        
        for item in injuries:
            athlete = item.get("athlete", {})
            athlete_id = int(athlete.get("id", 0) or 0)
            player_name = athlete.get("displayName", "")
            pos = athlete.get("position", {}).get("abbreviation", "")
            
            status_raw = item.get("status", "Questionable")
            status_upper = status_raw.upper()
            
            long_comment = item.get("longComment", "")
            short_comment = item.get("shortComment", "")
            headline = short_comment or f"{player_name} is listed as {status_raw}."
            notes = long_comment or headline
            
            is_out = status_raw.lower() in out_statuses or "out" in status_raw.lower() or "reserve" in status_raw.lower()
            is_playable = not is_out

            inj_obj = {
                "athlete_id": athlete_id,
                "name": player_name,
                "position": pos,
                "team": team_name,
                "status": status_upper,
                "headline": headline,
                "notes": notes,
                "practice_status": "NOT_REPORTED",
                "practice_trend": short_comment.upper(),
                "is_playable": is_playable,
                "is_out": is_out,
                "backup_athlete_name": None,
                "vacated_opportunity_note": None
            }
            all_injuries.append(inj_obj)

    output = {
        "season": season_info.get("year", 2026),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_injuries": len(all_injuries),
        "injuries": all_injuries
    }

    out_path = Path("data/injuries_live_2026.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Successfully synchronized {len(all_injuries)} official live injuries across {len(team_injuries_list)} teams into {out_path}.")

if __name__ == "__main__":
    sync_injuries()
