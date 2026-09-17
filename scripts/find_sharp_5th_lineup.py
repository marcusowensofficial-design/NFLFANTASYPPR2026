import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from find_optimal_top3_showdown import valid_lineups

# Exclude James Cook III AND Sione Vaki
sharp_lus = [
    lu for lu in valid_lineups 
    if 'James Cook III' not in lu['flex'] and lu['mvp'] != 'James Cook III' 
    and 'Sione Vaki' not in lu['flex'] and lu['mvp'] != 'Sione Vaki'
]

print(f"Total sharp lineups without Cook & Vaki: {len(sharp_lus)}")

# Also exclude the 4 lineups we already created:
# 1. Kincaid MVP + Allen, Gibbs, Moore, LaPorta, Bass
# 2. Gibbs MVP + Allen, Moore, Kincaid, LaPorta, Knox
# 3. Allen MVP + Gibbs, Moore, Kincaid, Bass, Knox
# 4. Gibbs MVP + St. Brown, Goff, LaPorta, Bass, Knox

def is_existing(lu):
    flex_set = set(lu['flex'])
    if lu['mvp'] == 'Dalton Kincaid' and flex_set == set(["Josh Allen", "Jahmyr Gibbs", "DJ Moore", "Sam LaPorta", "Tyler Bass"]):
        return True
    if lu['mvp'] == 'Jahmyr Gibbs' and flex_set == set(["Josh Allen", "DJ Moore", "Dalton Kincaid", "Sam LaPorta", "Dawson Knox"]):
        return True
    if lu['mvp'] == 'Josh Allen' and flex_set == set(["Jahmyr Gibbs", "DJ Moore", "Dalton Kincaid", "Tyler Bass", "Dawson Knox"]):
        return True
    if lu['mvp'] == 'Jahmyr Gibbs' and flex_set == set(["Amon-Ra St. Brown", "Jared Goff", "Sam LaPorta", "Tyler Bass", "Dawson Knox"]):
        return True
    return False

unentered = [lu for lu in sharp_lus if not is_existing(lu)]
print(f"Unentered sharp options: {len(unentered)}")

ranked_unentered = sorted(unentered, key=lambda x: x['gpp_score'], reverse=True)

print("\n" + "=" * 90)
print("TOP 5 CANDIDATES FOR OUR 5TH LINEUP (NO COOK, NO VAKI, PURE GPP LEVERAGE)")
print("=" * 90)
for idx, lu in enumerate(ranked_unentered[:6], 1):
    print(f"Option {idx}: [MVP] {lu['mvp']} ({lu['mvp_pos']}) | Salary: ${lu['salary']:,} (Buf: ${lu['buffer']:,}) | Teams: {lu['team_counts']}")
    print(f"          FLEX: {', '.join(lu['flex'])}")
    print(f"          Mean: {lu['mean']:.2f} | 90th%: {lu['p90']:.2f} | 99th%: {lu['p99']:.2f} | GPP Score: {lu['gpp_score']:.2f}")
    print("-" * 90)
