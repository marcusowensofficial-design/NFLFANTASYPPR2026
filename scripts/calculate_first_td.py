import json

# Implied probabilities from American Odds
def american_to_prob(odds_str):
    if not odds_str:
        return 0.0
    val = float(odds_str)
    if val < 0:
        return abs(val) / (abs(val) + 100.0)
    else:
        return 100.0 / (val + 100.0)

def prob_to_american(prob):
    if prob <= 0:
        return "+99999"
    if prob >= 1.0:
        return "-99999"
    if prob >= 0.5:
        return f"-{int(round((prob / (1 - prob)) * 100))}"
    else:
        return f"+{int(round(((1 - prob) / prob) * 100))}"

players_data = [
    {"name": "Bijan Robinson", "team": "ATL", "pos": "RB", "atd_odds": -145, "scrimmage_yds": 117.0, "hvt_share": 0.75, "rz_run_pct": 0.68},
    {"name": "Chris Olave", "team": "NO", "pos": "WR", "atd_odds": 147, "scrimmage_yds": 77.5, "hvt_share": 0.36, "rz_run_pct": 0.0},
    {"name": "Alvin Kamara", "team": "NO", "pos": "RB", "atd_odds": 180, "scrimmage_yds": 41.0, "hvt_share": 0.35, "rz_run_pct": 0.58},
    {"name": "Drake London", "team": "ATL", "pos": "WR", "atd_odds": 190, "scrimmage_yds": 66.5, "hvt_share": 0.28, "rz_run_pct": 0.0},
    {"name": "Tyler Shough", "team": "NO", "pos": "QB", "atd_odds": 295, "scrimmage_yds": 14.5, "hvt_share": 0.20, "rz_run_pct": 0.58},
    {"name": "Juwan Johnson", "team": "NO", "pos": "TE", "atd_odds": 290, "scrimmage_yds": 35.5, "hvt_share": 0.22, "rz_run_pct": 0.0},
    {"name": "Devaughn Vele", "team": "NO", "pos": "WR", "atd_odds": 305, "scrimmage_yds": 48.5, "hvt_share": 0.18, "rz_run_pct": 0.0},
    {"name": "Kyle Pitts", "team": "ATL", "pos": "TE", "atd_odds": 380, "scrimmage_yds": 36.5, "hvt_share": 0.15, "rz_run_pct": 0.0},
    {"name": "Bryce Lance", "team": "NO", "pos": "WR", "atd_odds": 550, "scrimmage_yds": 15.5, "hvt_share": 0.10, "rz_run_pct": 0.0},
    {"name": "Brian Robinson Jr.", "team": "ATL", "pos": "RB", "atd_odds": 450, "scrimmage_yds": 25.0, "hvt_share": 0.18, "rz_run_pct": 0.68},
    {"name": "Noah Fant", "team": "NO", "pos": "TE", "atd_odds": 600, "scrimmage_yds": 12.5, "hvt_share": 0.08, "rz_run_pct": 0.0},
    {"name": "Jahan Dotson", "team": "ATL", "pos": "WR", "atd_odds": 700, "scrimmage_yds": 17.5, "hvt_share": 0.10, "rz_run_pct": 0.0},
    {"name": "Kendre Miller", "team": "NO", "pos": "RB", "atd_odds": 900, "scrimmage_yds": 15.0, "hvt_share": 0.15, "rz_run_pct": 0.58}
]

# Team Implied Totals
no_total = 25.0
atl_total = 22.5
p_team_first_td = {
    "NO": no_total / (no_total + atl_total),
    "ATL": atl_total / (no_total + atl_total)
}

print(f"Team 1st TD Probabilities: NO={p_team_first_td['NO']:.1%}, ATL={p_team_first_td['ATL']:.1%}")

# Calculate individual anytime TD probabilities
for p in players_data:
    p['atd_prob'] = american_to_prob(str(p['atd_odds']))

# Normalize within team to calculate share of team's TDs
for team in ['ATL', 'NO']:
    team_players = [p for p in players_data if p['team'] == team]
    total_team_atd_prob = sum(p['atd_prob'] for p in team_players)
    for p in team_players:
        # Raw team share
        raw_share = p['atd_prob'] / total_team_atd_prob
        # Script / HVT weight adjustment (First TD is heavily skewed toward goal-line rushers vs air yards)
        # Inside-the-5 bellcows convert early scripted goal line opportunities at 1.25x the rate of pass-catchers
        if p['pos'] == 'RB' and p['name'] == 'Bijan Robinson':
            script_mult = 1.20
        elif p['pos'] == 'RB':
            script_mult = 1.05
        elif p['pos'] == 'QB':
            script_mult = 0.85
        else:
            script_mult = 0.95
        p['adjusted_team_share'] = raw_share * script_mult

# Re-normalize adjusted team share within team
for team in ['ATL', 'NO']:
    team_players = [p for p in players_data if p['team'] == team]
    sum_adj = sum(p['adjusted_team_share'] for p in team_players)
    for p in team_players:
        p['final_team_share'] = p['adjusted_team_share'] / sum_adj
        # Overall Game First TD Probability
        p['first_td_prob'] = p['final_team_share'] * p_team_first_td[team]
        p['fair_first_td_odds'] = prob_to_american(p['first_td_prob'])

# Sort by First TD Probability
ranked = sorted(players_data, key=lambda x: x['first_td_prob'], reverse=True)

print("\n" + "=" * 80)
print(f"{'PLAYER':<20} | {'TEAM':<4} | {'POS':<3} | {'ATD ODDS':<8} | {'ATD PROB':<8} | {'1ST TD PROB':<11} | {'FAIR 1ST TD ODDS'}")
print("=" * 80)
for p in ranked:
    print(f"{p['name']:<20} | {p['team']:<4} | {p['pos']:<3} | {p['atd_odds']:<8} | {p['atd_prob']:>7.1%} | {p['first_td_prob']:>10.1%} | {p['fair_first_td_odds']}")
print("=" * 80)
