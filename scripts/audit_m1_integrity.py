"""Forensic audit of Milestone M1 data integrity."""
import json
from pathlib import Path
import sys
sys.path.insert(0, ".")
from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.injuries_client import resolve_team_abbrev

DATA_PATH = Path("data/injuries_live_2026.json")
with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

injuries = data.get("injuries", [])
charts = nfl_depthchart_client._load_all_from_disk()

print(f"Total injuries: {len(injuries)}")
non_zero = sum(1 for i in injuries if i.get("athlete_id", 0) > 0)
print(f"Non-zero athlete IDs: {non_zero}/{len(injuries)} ({non_zero/len(injuries)*100:.1f}%)")

# Duplicate check
id_counts = {}
for i in injuries:
    aid = i["athlete_id"]
    id_counts[aid] = id_counts.get(aid, 0) + 1

dups = {aid: count for aid, count in id_counts.items() if count > 1}
print(f"Unique athlete IDs: {len(id_counts)} / {len(injuries)}")
print(f"Duplicate athlete ID count: {len(dups)}")
for aid, count in list(dups.items())[:5]:
    names = [i["name"] for i in injuries if i["athlete_id"] == aid]
    print(f"  ID {aid} appeared {count} times: {names}")

# Positions
positions = set(i.get("position") for i in injuries)
print(f"Distinct positions ({len(positions)}): {sorted(list(positions))}")

# Next-man-up enrichment
total_enriched = sum(1 for i in injuries if i.get("backup_athlete_name"))
print(f"Total enriched across all injuries: {total_enriched}")

# Map offensive rank 1 starters
starters = {}
for tabbr, chart in charts.items():
    for slot, athletes in chart.offense.items():
        if any(p in slot.lower() for p in ("qb", "rb", "wr", "te")):
            for ath in athletes:
                if ath.rank == 1:
                    starters[(tabbr, ath.display_name.lower().strip())] = (slot, ath)

sidelined_starters = []
for i in injuries:
    tabbr = resolve_team_abbrev(i["team"])
    pos = i.get("position", "").upper()
    if pos in ("QB", "RB", "WR", "TE") and (i.get("is_out") or "QUESTIONABLE" in i.get("status", "").upper()):
        n_name = i["name"].lower().strip()
        matched = None
        for (t, sname), (slot, ath) in starters.items():
            if t == tabbr and (n_name in sname or sname in n_name):
                matched = (slot, ath)
                break
        if matched:
            sidelined_starters.append((i, matched))

enriched_starters = [s for s in sidelined_starters if s[0].get("backup_athlete_name")]
unenriched_starters = [s for s in sidelined_starters if not s[0].get("backup_athlete_name")]

print(f"Sidelined/Questionable Rank-1 Starters: {len(sidelined_starters)}")
print(f"Enriched Starters: {len(enriched_starters)} ({len(enriched_starters)/len(sidelined_starters)*100:.1f}%)")
print(f"Unenriched Starters: {len(unenriched_starters)}")
for u, (slot, ath) in unenriched_starters:
    print(f"  Unenriched: {u['name']} ({u['position']} - {u['team']}) status={u['status']} is_out={u['is_out']} slot={slot}")
    # Inspect why it was not enriched:
    chart = charts.get(resolve_team_abbrev(u["team"]))
    if chart:
        next_up = chart.get_next_man_up(u["name"], u["position"])
        print(f"    Direct get_next_man_up result: {next_up}")
