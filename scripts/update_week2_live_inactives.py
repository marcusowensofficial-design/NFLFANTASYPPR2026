"""Update data/injuries_live_2026.json with tonight's confirmed inactives and verified Week 2 statuses.
"""

import json
from pathlib import Path
from datetime import datetime, timezone


def update_inactives():
    inj_path = Path("data/injuries_live_2026.json")
    with open(inj_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    injuries = data.get("injuries", [])

    # Map of players to update/insert
    inactives_to_sync = {
        "Ed Oliver": {
            "athlete_id": 4038848,
            "name": "Ed Oliver",
            "position": "DT",
            "team": "Buffalo Bills",
            "status": "OUT",
            "headline": "Oliver suffered a hip injury during pregame warmups and has been officially ruled OUT for tonight's Week 2 matchup vs Detroit.",
            "notes": "Starter ruled out late. Massive downgrade to Buffalo interior run defense and pass rush.",
            "is_playable": False,
            "is_out": True,
        },
        "Ty Johnson": {
            "athlete_id": 4040683,
            "name": "Ty Johnson",
            "position": "RB",
            "team": "Buffalo Bills",
            "status": "OUT",
            "headline": "Johnson (hamstring) is officially INACTIVE / OUT for Thursday Night Football vs Detroit.",
            "notes": "Ty Johnson inactive vacates 3rd-down pass-blocking and backup change-of-pace snaps to Ray Davis.",
            "is_playable": False,
            "is_out": True,
        },
        "T.J. Sanders": {
            "athlete_id": 4685456,
            "name": "T.J. Sanders",
            "position": "DL",
            "team": "Buffalo Bills",
            "status": "OUT",
            "headline": "Sanders (knee/illness) did not participate in practice and is officially INACTIVE / OUT tonight.",
            "notes": "Defensive tackle depth further depleted alongside Ed Oliver.",
            "is_playable": False,
            "is_out": True,
        },
        "Ennis Rakestraw Jr.": {
            "athlete_id": 4566092,
            "name": "Ennis Rakestraw Jr.",
            "position": "CB",
            "team": "Detroit Lions",
            "status": "OUT",
            "headline": "Rakestraw (hamstring) is officially INACTIVE / OUT tonight against Buffalo.",
            "notes": "Key boundary cornerback reserve out. Detroit depth down to Khalil Dorsey.",
            "is_playable": False,
            "is_out": True,
        },
        "Keith Abney II": {
            "athlete_id": 5093004,
            "name": "Keith Abney II",
            "position": "CB",
            "team": "Detroit Lions",
            "status": "OUT",
            "headline": "Abney is officially INACTIVE / OUT tonight against Buffalo.",
            "notes": "Cornerback depth severely compromised for Detroit.",
            "is_playable": False,
            "is_out": True,
        },
        "Juice Scruggs": {
            "athlete_id": 4361543,
            "name": "Juice Scruggs",
            "position": "C",
            "team": "Detroit Lions",
            "status": "OUT",
            "headline": "Scruggs is officially INACTIVE / OUT tonight against Buffalo.",
            "notes": "Offensive line interior depth inactive.",
            "is_playable": False,
            "is_out": True,
        },
        "Christian Mahogany": {
            "athlete_id": 4430739,
            "name": "Christian Mahogany",
            "position": "G",
            "team": "Detroit Lions",
            "status": "OUT",
            "headline": "Mahogany (knee) is officially INACTIVE / OUT tonight against Buffalo.",
            "notes": "Guard depth inactive.",
            "is_playable": False,
            "is_out": True,
        },
        "Tyrell Shavers": {
            "athlete_id": 4241477,
            "name": "Tyrell Shavers",
            "position": "WR",
            "team": "Buffalo Bills",
            "status": "OUT",
            "headline": "Shavers is officially INACTIVE / OUT tonight.",
            "notes": "Depth receiver out.",
            "is_playable": False,
            "is_out": True,
        },
        "Josh Jacobs": {
            "athlete_id": 4040715,
            "name": "Josh Jacobs",
            "position": "RB",
            "team": "Green Bay Packers",
            "status": "OUT",
            "headline": "Jacobs remains on the Commissioner's Exempt List and is OUT for Week 2.",
            "notes": "MarShawn Lloyd and Emanuel Wilson will handle the Green Bay backfield.",
            "is_playable": False,
            "is_out": True,
        },
        "James Conner": {
            "athlete_id": 3045147,
            "name": "James Conner",
            "position": "RB",
            "team": "Arizona Cardinals",
            "status": "INJURED RESERVE",
            "headline": "Conner (foot) placed on Injured Reserve.",
            "notes": "Trey Benson elevates to full starting bellcow workload for Arizona.",
            "is_playable": False,
            "is_out": True,
        },
    }

    found_names = set()
    for inj in injuries:
        p_name = inj.get("name")
        if p_name in inactives_to_sync:
            found_names.add(p_name)
            patch = inactives_to_sync[p_name]
            inj.update(patch)

    for p_name, patch in inactives_to_sync.items():
        if p_name not in found_names:
            injuries.append(patch)

    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["total_injuries"] = len(injuries)

    with open(inj_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[OK] Successfully updated {len(inactives_to_sync)} inactives/injuries in data/injuries_live_2026.json!")


if __name__ == "__main__":
    update_inactives()
