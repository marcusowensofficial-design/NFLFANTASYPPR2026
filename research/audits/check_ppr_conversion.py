import pandas as pd

lineup = [
    ('QB', 'Joe Burrow', 'CIN', 'TB', 8200, 21.14, 0.0),
    ('RB', 'Saquon Barkley', 'PHI', 'WAS', 8100, 21.23, 4.0),
    ('RB', 'Omarion Hampton', 'LAC', 'ARI', 7300, 22.21, 3.5),
    ('FLEX', 'Ashton Jeanty', 'LV', 'MIA', 7000, 20.40, 3.5),
    ('WR', 'Ja\'Marr Chase', 'CIN', 'TB', 8900, 21.02, 7.5),
    ('WR', 'Ladd McConkey', 'LAC', 'ARI', 6500, 15.16, 5.5),
    ('WR', 'Michael Pittman Jr.', 'PIT', 'ATL', 5800, 13.70, 5.5),
    ('TE', 'Cade Otton', 'TB', 'CIN', 5000, 8.41, 4.5),
    ('D', 'Tennessee Titans', 'TEN', 'NYJ', 3200, 7.75, 0.0)
]

print("="*75)
print("LINEUP SCORING CONVERSION: HALF-PPR (FANDUEL) VS. FULL-PPR (SEASON-LONG)")
print("="*75)
print(f"{'Slot':<6} | {'Player':<20} | {'Proj Rec':<9} | {'Half-PPR (0.5)':<15} | {'Full-PPR (1.0)':<15}")
print("-"*75)

tot_half = 0.0
tot_full = 0.0
tot_recs = 0.0

for slot, name, team, opp, sal, half_pts, recs in lineup:
    full_pts = half_pts + (recs * 0.5)
    tot_half += half_pts
    tot_full += full_pts
    tot_recs += recs
    print(f"{slot:<6} | {name:<20} | {recs:<9.1f} | {half_pts:<15.2f} | {full_pts:<15.2f}")

print("-"*75)
print(f"Total Team Receptions:        {tot_recs:.1f} catches")
print(f"Half-PPR Projected Score:     {tot_half:.2f} pts  (2.52x value)")
print(f"Full-PPR Projected Score:     {tot_full:.2f} pts  (2.80x value - +17.0 pts boost!)")
print("="*75)
