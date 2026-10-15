import pandas as pd

df = pd.read_csv('data/optimized_player_pool.csv')

lineups = {
    "Option 1: The 'Shootout of the Week' Stack (Burrow + Chase + Otton Bring-back + 3 Smash RBs)": [
        ('QB', 'Joe Burrow', 8200),
        ('RB', 'Saquon Barkley', 8100),
        ('RB', 'Omarion Hampton', 7300),
        ('FLEX', 'Ashton Jeanty', 7000),
        ('WR', 'Ja\'Marr Chase', 8900),
        ('WR', 'Ladd McConkey', 6500),
        ('WR', 'Michael Pittman Jr.', 5800),
        ('TE', 'Cade Otton', 5000),
        ('D', 'Tennessee Titans', 3200)
    ],
    "Option 2: The '#1 Implied Total Monopoly' Stack (Herbert + McConkey + Hampton + Harrison Jr. Bring-back)": [
        ('QB', 'Justin Herbert', 7600),
        ('RB', 'Saquon Barkley', 8100),
        ('RB', 'Omarion Hampton', 7300),
        ('FLEX', 'Ashton Jeanty', 7000),
        ('WR', 'Ja\'Marr Chase', 8900),
        ('WR', 'Ladd McConkey', 6500),
        ('WR', 'Marvin Harrison Jr.', 5900),
        ('TE', 'Dallas Goedert', 5300),
        ('D', 'Tennessee Titans', 3200)
    ],
    "Option 3: The 'Ford Field Dome Juggernaut' Stack (Goff + St. Brown + Olave Bring-back + Gibbs)": [
        ('QB', 'Jared Goff', 7800),
        ('RB', 'Jahmyr Gibbs', 9100),
        ('RB', 'Omarion Hampton', 7300),
        ('FLEX', 'Ashton Jeanty', 7000),
        ('WR', 'Amon-Ra St. Brown', 8600),
        ('WR', 'Chris Olave', 7400),
        ('WR', 'Theo Wease Jr.', 4200),
        ('TE', 'Tucker Kraft', 6300),
        ('D', 'Tennessee Titans', 3200)
    ]
}

for title, roster in lineups.items():
    tot_sal = 0
    tot_proj = 0
    print("\n" + "="*80)
    print(f" {title.upper()} ")
    print("="*80)
    for slot, name, sal in roster:
        match = df[df['name'].str.lower() == name.lower()]
        if len(match) > 0:
            r = match.iloc[0]
            tot_sal += r['salary']
            tot_proj += r['proj']
            print(f"  {slot:<5} | {r['name']:<22} | {r['team']:<4} vs {r['opp']:<4} | ${r['salary']:<5} | Proj: {r['proj']:<5.2f} pts | Implied: {r['team_implied']:<4.1f} | Softness: #{r['soft_rank']}")
        else:
            print(f"  NOT FOUND: {name}")
    print("-"*80)
    print(f"  TOTAL SALARY: ${tot_sal:,} / $60,000  (Remaining: ${60000 - tot_sal:,})")
    print(f"  TOTAL PROJECTED POINTS: {tot_proj:.2f} pts")
    print(f"  VALUE MULTIPLIER: {tot_proj / (tot_sal / 1000):.2f}x")
    print("="*80)
