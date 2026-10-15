import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from solve_det_buf_slate import build_calibrated_player_pool

# Import the ranked lineups from find_optimal_top3_showdown
from find_optimal_top3_showdown import valid_lineups

no_vaki = [lu for lu in valid_lineups if 'Sione Vaki' not in lu['flex'] and lu['mvp'] != 'Sione Vaki']
print(f"Total valid lineups WITHOUT Sione Vaki: {len(no_vaki):,}")

no_vaki_ranked = sorted(no_vaki, key=lambda x: x['gpp_score'], reverse=True)
print("\n" + "=" * 90)
print("TOP 10 LINEUPS COMPLETELY EXCLUDING SIONE VAKI")
print("=" * 90)
for idx, lu in enumerate(no_vaki_ranked[:10], 1):
    print(f"Rank {idx}: [MVP] {lu['mvp']} ({lu['mvp_team']} {lu['mvp_pos']}) | Salary: ${lu['salary']:,} (Buf: ${lu['buffer']:,}) | Teams: {lu['team_counts']}")
    print(f"         FLEX: {', '.join(lu['flex'])}")
    print(f"         Mean: {lu['mean']:.2f} | 90th%: {lu['p90']:.2f} | 99th%: {lu['p99']:.2f} | >=130pt: {lu['p130']:.1f}% | >=150pt: {lu['p150']:.1f}% | GPP Score: {lu['gpp_score']:.2f}")
    print("-" * 90)
