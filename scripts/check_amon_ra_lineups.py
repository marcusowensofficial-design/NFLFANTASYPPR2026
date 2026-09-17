import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from find_optimal_top3_showdown import valid_lineups

st_brown_lus = [lu for lu in valid_lineups if lu['mvp'] == 'Amon-Ra St. Brown' or 'Amon-Ra St. Brown' in lu['flex']]
st_brown_no_vaki = [lu for lu in st_brown_lus if 'Sione Vaki' not in lu['flex'] and lu['mvp'] != 'Sione Vaki']

print(f"Total St. Brown lineups: {len(st_brown_lus)} (without Vaki: {len(st_brown_no_vaki)})")

ranked = sorted(st_brown_no_vaki, key=lambda x: x['gpp_score'], reverse=True)
print("\n" + "=" * 80)
print("TOP 5 AMON-RA ST. BROWN LINEUPS (NO VAKI)")
print("=" * 80)
for idx, lu in enumerate(ranked[:5], 1):
    print(f"Rank {idx}: [MVP] {lu['mvp']} ({lu['mvp_team']}) | Salary: ${lu['salary']:,} (Buf: ${lu['buffer']:,}) | Teams: {lu['team_counts']}")
    print(f"         FLEX: {', '.join(lu['flex'])}")
    print(f"         Mean: {lu['mean']:.2f} | 90th%: {lu['p90']:.2f} | 99th%: {lu['p99']:.2f} | GPP Score: {lu['gpp_score']:.2f}")
    print("-" * 80)
