"""Audit and Synchronize All 32 Teams' Depth Charts, PFF Scouting, and WR-CB Matrix.

Pulls directly from data/nfl_depth_charts_2026.json (the verified 2026 active depth charts)
and updates:
1. data/pff_scouting_2026.json (all 32 teams' starting & backup CBs, safeties, tackles, disruptors)
2. src/services/matchup/wrcb_matrix.py (all 32 teams in NFL_CB_DEPTH_CHARTS)
"""

from scripts.sync_authoritative_defense_2026 import sync_defense_data

if __name__ == "__main__":
    sync_defense_data()
