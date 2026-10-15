"""Script to update data/pff_scouting_2026.json with post-Week 2 realized metrics,

depth charts, trench metrics, and cornerback coverage grades for 2026 Week 3.
Synchronizes directly from official 2026 depth charts to guarantee traded players
are assigned to their true 2026 teams.
"""

from scripts.sync_authoritative_defense_2026 import sync_defense_data

if __name__ == "__main__":
    sync_defense_data()
