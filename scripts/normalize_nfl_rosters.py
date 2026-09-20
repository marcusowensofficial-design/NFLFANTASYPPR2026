"""Master NFL Roster & Team Normalizer.

Ensures all NFL players are accurately mapped to their real-world active NFL franchises,
removes non-slate players (Thursday TNF, Sunday Night SNF, Monday Night MNF) from Sunday Main Slate CSVs,
and updates data/fantasy.db and data/player_crosswalk.json.
"""

import json
import os
import re
import sqlite3
import pandas as pd
from pathlib import Path

# Canonical Real-World NFL Team Mapping
CANONICAL_REAL_TEAMS: dict[str, str] = {
    # QBs
    "Lamar Jackson": "BAL",
    "Jalen Hurts": "PHI",
    "Caleb Williams": "CHI",
    "Joe Burrow": "CIN",
    "Brock Purdy": "SF",
    "Dak Prescott": "DAL",
    "Jayden Daniels": "WAS",
    "Trevor Lawrence": "JAC",
    "Jordan Love": "GB",
    "Baker Mayfield": "TB",
    "Drake Maye": "NE",
    "Justin Herbert": "LAC",
    "Bo Nix": "DEN",
    "Bryce Young": "CAR",
    "C.J. Stroud": "HOU",
    "Aaron Rodgers": "NYJ",
    "Kyler Murray": "ARI",
    "Tua Tagovailoa": "MIA",
    "Sam Darnold": "MIN",
    "Kirk Cousins": "ATL",
    "Geno Smith": "SEA",
    "Deshaun Watson": "CLE",
    "Jacoby Brissett": "NE",
    "Drew Lock": "SEA",
    "Cooper Rush": "DAL",
    "Carson Wentz": "KC",
    "Kenny Pickett": "PHI",
    "Mac Jones": "JAC",
    "Gardner Minshew II": "LV",
    "Gardner Minshew": "LV",
    "Aidan O'Connell": "LV",
    "Sam Howell": "SEA",
    "Zach Wilson": "DEN",
    "Jarrett Stidham": "DEN",
    "Mason Rudolph": "TEN",
    "Davis Mills": "HOU",
    "Joe Flacco": "IND",
    "Nick Mullens": "MIN",
    "Marcus Mariota": "WAS",
    "Mitchell Trubisky": "BUF",
    "Andy Dalton": "CAR",
    "Spencer Rattler": "NO",
    "J.J. McCarthy": "MIN",
    "Michael Penix Jr.": "ATL",
    "Patrick Mahomes": "KC",
    "Josh Allen": "BUF",
    "Jared Goff": "DET",
    "Matthew Stafford": "LAR",
    "Daniel Jones": "NYG",
    "Anthony Richardson": "IND",

    # RBs
    "Christian McCaffrey": "SF",
    "Bijan Robinson": "ATL",
    "Derrick Henry": "BAL",
    "Saquon Barkley": "PHI",
    "De'Von Achane": "MIA",
    "Bucky Irving": "TB",
    "Ashton Jeanty": "LV",
    "Chase Brown": "CIN",
    "Javonte Williams": "DEN",
    "Omarion Hampton": "LAC",
    "Breece Hall": "NYJ",
    "D'Andre Swift": "CHI",
    "David Montgomery": "DET",
    "Jahmyr Gibbs": "DET",
    "James Cook": "BUF",
    "Jonathan Taylor": "IND",
    "Isiah Pacheco": "KC",
    "Kyren Williams": "LAR",
    "Devin Singletary": "NYG",
    "Tyrone Tracy Jr.": "NYG",
    "Travis Etienne Jr.": "JAX",
    "Travis Etienne": "JAX",
    "Rhamondre Stevenson": "NE",
    "Chuba Hubbard": "CAR",
    "J.K. Dobbins": "LAC",
    "Jaylen Warren": "PIT",
    "MarShawn Lloyd": "GB",
    "Aaron Jones Sr.": "MIN",
    "Aaron Jones": "MIN",
    "Kyle Monangai": "CHI",
    "Tony Pollard": "TEN",
    "Tyjae Spears": "TEN",
    "Tyler Allgeier": "ATL",
    "Rico Dowdle": "DAL",
    "Jordan Mason": "SF",
    "Ezekiel Elliott": "DAL",
    "Najee Harris": "PIT",
    "Rachaad White": "TB",
    "Jerome Ford": "CLE",
    "Nick Chubb": "CLE",
    "Brian Robinson Jr.": "WAS",
    "Austin Ekeler": "WAS",
    "James Conner": "ARI",
    "Trey Benson": "ARI",
    "Raheem Mostert": "MIA",
    "Jaylen Wright": "MIA",
    "Kenneth Walker III": "SEA",
    "Kenneth Walker": "SEA",
    "Zach Charbonnet": "SEA",
    "Gus Edwards": "LAC",
    "Kimani Vidal": "LAC",
    "Zamir White": "LV",
    "Alexander Mattison": "LV",
    "Alvin Kamara": "NO",
    "Jamaal Williams": "NO",
    "Kendre Miller": "NO",
    "Tank Bigsby": "JAX",
    "Miles Sanders": "CAR",
    "Jonathon Brooks": "CAR",
    "Antonio Gibson": "NE",
    "Cam Akers: HOU": "MIN",
    "Dameon Pierce": "HOU",
    "Joe Mixon": "HOU",
    "Ty Chandler": "MIN",
    "Roschon Johnson": "CHI",
    "Emanuel Wilson": "GB",
    "Braelon Allen": "NYJ",
    "Ray Davis": "BUF",
    "Blake Corum": "LAR",
    "Trey Sermon": "IND",
    "Carson Steele": "KC",
    "Kareem Hunt": "KC",
    "Cam Skattebo": "NYG",

    # WRs
    "Jaxon Smith-Njigba": "SEA",
    "Ja'Marr Chase": "CIN",
    "Justin Jefferson": "MIN",
    "CeeDee Lamb": "DAL",
    "Mike Evans": "TB",
    "George Pickens": "PIT",
    "Chris Olave": "NO",
    "Nico Collins": "HOU",
    "Drake London": "ATL",
    "Zay Flowers": "BAL",
    "DeVonta Smith": "PHI",
    "A.J. Brown": "PHI",
    "Garrett Wilson": "NYJ",
    "Tee Higgins": "CIN",
    "DK Metcalf": "SEA",
    "Christian Watson": "GB",
    "Jaylen Waddle": "MIA",
    "Tyreek Hill": "MIA",
    "Ladd McConkey": "LAC",
    "Rome Odunze": "CHI",
    "Keenan Allen": "CHI",
    "DJ Moore": "CHI",
    "Deebo Samuel Sr.": "SF",
    "Deebo Samuel": "SF",
    "Brandon Aiyuk": "SF",
    "Courtland Sutton": "DEN",
    "Stefon Diggs": "HOU",
    "Tank Dell": "HOU",
    "Terry McLaurin": "WAS",
    "Michael Pittman Jr.": "IND",
    "Michael Pittman": "IND",
    "Josh Downs": "IND",
    "Alec Pierce": "IND",
    "AD Mitchell": "IND",
    "Adonai Mitchell": "IND",
    "Rashee Rice": "KC",
    "Xavier Worthy": "KC",
    "Hollywood Brown": "KC",
    "Marquise Brown": "KC",
    "JuJu Smith-Schuster": "KC",
    "Puka Nacua": "LAR",
    "Cooper Kupp": "LAR",
    "Demarcus Robinson": "LAR",
    "Jordan Whittington": "LAR",
    "Tutu Atwell": "LAR",
    "Malik Nabers": "NYG",
    "Wan'Dale Robinson": "NYG",
    "Darius Slayton": "NYG",
    "Jalin Hyatt": "NYG",
    "Amon-Ra St. Brown": "DET",
    "Jameson Williams": "DET",
    "Tim Patrick": "DET",
    "Kalif Raymond": "DET",
    "Khalil Shakir": "BUF",
    "Keon Coleman": "BUF",
    "Curtis Samuel": "BUF",
    "Mack Hollins": "BUF",
    "Marquez Valdes-Scantling": "BUF",
    "Romeo Doubs": "GB",
    "Jayden Reed": "GB",
    "Dontayvion Wicks": "GB",
    "Jordan Addison": "MIN",
    "Jalen Nailor": "MIN",
    "Chris Godwin Jr.": "TB",
    "Chris Godwin": "TB",
    "Jalen McMillan": "TB",
    "Quentin Johnston": "LAC",
    "Joshua Palmer": "LAC",
    "Marvin Harrison Jr.": "ARI",
    "Michael Wilson": "ARI",
    "Greg Dortch": "ARI",
    "Brian Thomas Jr.": "JAX",
    "Christian Kirk": "JAX",
    "Gabe Davis": "JAX",
    "Parker Washington": "JAX",
    "Jauan Jennings": "SF",
    "Ricky Pearsall": "SF",
    "Malik Washington": "MIA",
    "Odell Beckham Jr.": "MIA",
    "Devaughn Vele": "DEN",
    "Josh Reynolds": "DEN",
    "Marvin Mims Jr.": "DEN",
    "Troy Franklin": "DEN",
    "Jakobi Meyers": "LV",
    "Tre Tucker": "LV",
    "Rashid Shaheed": "NO",
    "Calvin Ridley": "TEN",
    "DeAndre Hopkins": "TEN",
    "Tyler Boyd": "TEN",
    "Nick Westbrook-Ikhine": "TEN",
    "Diontae Johnson": "CAR",
    "Adam Thielen": "CAR",
    "Xavier Legette": "CAR",
    "Jalen Coker": "CAR",
    "Jerry Jeudy": "CLE",
    "Amari Cooper": "CLE",
    "Elijah Moore": "CLE",
    "Cedric Tillman": "CLE",
    "Tyler Lockett": "SEA",
    "Demario Douglas": "NE",
    "Kendrick Bourne": "NE",
    "Ja'Lynn Polk": "NE",
    "K.J. Osborn": "NE",
    "Calvin Austin III": "PIT",
    "Van Jefferson": "PIT",
    "Roman Wilson": "PIT",
    "Luke McCaffrey": "WAS",
    "Dyami Brown": "WAS",
    "Noah Brown": "WAS",
    "Brandin Cooks": "DAL",
    "Jalen Tolbert": "DAL",
    "KaVontae Turpin": "DAL",
    "Rashod Bateman": "BAL",
    "Nelson Agholor": "BAL",
    "Devontez Walker": "BAL",
    "Tylan Wallace": "BAL",
    "Andrei Iosivas": "CIN",
    "Trenton Irwin": "CIN",
    "Jermaine Burton": "CIN",
    "Darnell Mooney": "ATL",
    "Ray-Ray McCloud": "ATL",
    "KhaDarel Hodge": "ATL",
    "Casey Washington": "ATL",
    "Allen Lazard": "NYJ",
    "Mike Williams": "NYJ",
    "Malachi Corley": "NYJ",
    "Xavier Gipson": "NYJ",

    # TEs
    "Trey McBride": "ARI",
    "Brock Bowers": "LV",
    "Tucker Kraft": "GB",
    "Luke Musgrave": "GB",
    "George Kittle": "SF",
    "Dallas Goedert": "PHI",
    "Juwan Johnson": "NO",
    "Taysom Hill": "NO",
    "Foster Moreau": "NO",
    "Dalton Kincaid": "BUF",
    "Dawson Knox": "BUF",
    "Sam LaPorta": "DET",
    "Brock Wright": "DET",
    "Travis Kelce": "KC",
    "Noah Gray": "KC",
    "Colby Parkinson": "LAR",
    "Davis Allen": "LAR",
    "Theo Johnson": "NYG",
    "Daniel Bellinger": "NYG",
    "Kylen Granson": "IND",
    "Mo Alie-Cox": "IND",
    "Drew Ogletree": "IND",
    "Jake Ferguson": "DAL",
    "Luke Schoonmaker": "DAL",
    "Zach Ertz": "WAS",
    "Ben Sinnott": "WAS",
    "John Bates": "WAS",
    "Chig Okonkwo": "TEN",
    "Chigoziem Okonkwo": "TEN",
    "Josh Whyle": "TEN",
    "Nick Vannett": "TEN",
    "David Njoku": "CLE",
    "Jordan Akins": "CLE",
    "Cade Otton": "TB",
    "Payne Durham": "TB",
    "Hunter Henry": "NE",
    "Austin Hooper": "NE",
    "Pat Freiermuth": "PIT",
    "Darnell Washington": "PIT",
    "Connor Heyward": "PIT",
    "Mark Andrews": "BAL",
    "Isaiah Likely": "BAL",
    "Charlie Kolar": "BAL",
    "Mike Gesicki": "CIN",
    "Drew Sample": "CIN",
    "Tanner Hudson": "CIN",
    "Erick All": "CIN",
    "Dalton Schultz": "HOU",
    "Cade Stover": "HOU",
    "Brevin Jordan": "HOU",
    "Evan Engram": "JAX",
    "Brenton Strange": "JAX",
    "Luke Farrell": "JAX",
    "Greg Dulcich": "DEN",
    "Adam Trautman": "DEN",
    "Nate Adkins": "DEN",
    "Hayden Hurst": "LAC",
    "Will Dissly": "LAC",
    "Stone Smartt": "LAC",
    "Michael Mayer": "LV",
    "Harrison Bryant": "LV",
    "Noah Fant": "SEA",
    "AJ Barner": "SEA",
    "Pharaoh Brown": "SEA",
    "Tip Reiman": "ARI",
    "Elijah Higgins": "ARI",
    "Jonnu Smith": "MIA",
    "Durham Smythe": "MIA",
    "Julian Hill": "MIA",
    "Eric Saubert": "SF",
    "Tommy Tremble": "CAR",
    "Ja'Tavion Sanders": "CAR",
    "Ian Thomas": "CAR",
    "Kyle Pitts": "ATL",
    "Charlie Woerner": "ATL",
    "Tyler Conklin": "NYJ",
    "Jeremy Ruckert": "NYJ",
    "Cole Kmet": "CHI",
    "Gerald Everett": "CHI",
    "T.J. Hockenson": "MIN",
    "Josh Oliver": "MIN",
    "Johnny Mundt": "MIN",
}

# Normalize team aliases (JAX/JAC, WAS/WSH)
TEAM_ALIASES = {
    "JAX": "JAC",
    "WSH": "WAS",
}

# Week 2 Schedule (Home/Away, Game string, whether on Sunday Main Slate)
WEEK_2_GAMES: dict[str, dict[str, Any]] = {
    # 13 Sunday Main Slate games
    "ATL": {"opp": "CAR", "is_home": True, "game": "CAR@ATL", "is_main_slate": True},
    "CAR": {"opp": "ATL", "is_home": False, "game": "CAR@ATL", "is_main_slate": True},
    "CHI": {"opp": "MIN", "is_home": True, "game": "MIN@CHI", "is_main_slate": True},
    "MIN": {"opp": "CHI", "is_home": False, "game": "MIN@CHI", "is_main_slate": True},
    "TEN": {"opp": "PHI", "is_home": True, "game": "PHI@TEN", "is_main_slate": True},
    "PHI": {"opp": "TEN", "is_home": False, "game": "PHI@TEN", "is_main_slate": True},
    "NE": {"opp": "PIT", "is_home": True, "game": "PIT@NE", "is_main_slate": True},
    "PIT": {"opp": "NE", "is_home": False, "game": "PIT@NE", "is_main_slate": True},
    "NYJ": {"opp": "GB", "is_home": True, "game": "GB@NYJ", "is_main_slate": True},
    "GB": {"opp": "NYJ", "is_home": False, "game": "GB@NYJ", "is_main_slate": True},
    "TB": {"opp": "CLE", "is_home": True, "game": "CLE@TB", "is_main_slate": True},
    "CLE": {"opp": "TB", "is_home": False, "game": "CLE@TB", "is_main_slate": True},
    "BAL": {"opp": "NO", "is_home": True, "game": "NO@BAL", "is_main_slate": True},
    "NO": {"opp": "BAL", "is_home": False, "game": "NO@BAL", "is_main_slate": True},
    "HOU": {"opp": "CIN", "is_home": True, "game": "CIN@HOU", "is_main_slate": True},
    "CIN": {"opp": "HOU", "is_home": False, "game": "CIN@HOU", "is_main_slate": True},
    "DEN": {"opp": "JAC", "is_home": True, "game": "JAC@DEN", "is_main_slate": True},
    "JAC": {"opp": "DEN", "is_home": False, "game": "JAC@DEN", "is_main_slate": True},
    "LAC": {"opp": "LV", "is_home": True, "game": "LV@LAC", "is_main_slate": True},
    "LV": {"opp": "LAC", "is_home": False, "game": "LV@LAC", "is_main_slate": True},
    "DAL": {"opp": "WAS", "is_home": True, "game": "WAS@DAL", "is_main_slate": True},
    "WAS": {"opp": "DAL", "is_home": False, "game": "WAS@DAL", "is_main_slate": True},
    "ARI": {"opp": "SEA", "is_home": True, "game": "SEA@ARI", "is_main_slate": True},
    "SEA": {"opp": "ARI", "is_home": False, "game": "SEA@ARI", "is_main_slate": True},
    "SF": {"opp": "MIA", "is_home": True, "game": "MIA@SF", "is_main_slate": True},
    "MIA": {"opp": "SF", "is_home": False, "game": "MIA@SF", "is_main_slate": True},

    # Non-Main Slate games (Excluded from Sunday Main Slate)
    "DET": {"opp": "BUF", "is_home": False, "game": "DET@BUF", "is_main_slate": False},
    "BUF": {"opp": "DET", "is_home": True, "game": "DET@BUF", "is_main_slate": False},
    "KC": {"opp": "IND", "is_home": True, "game": "IND@KC", "is_main_slate": False},
    "IND": {"opp": "KC", "is_home": False, "game": "IND@KC", "is_main_slate": False},
    "LAR": {"opp": "NYG", "is_home": True, "game": "NYG@LAR", "is_main_slate": False},
    "NYG": {"opp": "LAR", "is_home": False, "game": "NYG@LAR", "is_main_slate": False},
}


def normalize_sunday_main_slate_csv(csv_path: str = "data/9-20-26-main-slate-rosters-salaries-fd-week2.csv"):
    """Corrects player team assignments and removes non-main-slate players."""
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print(f"[*] Normalizing Sunday Main Slate CSV: {csv_path}")
    df = pd.read_csv(csv_path)
    initial_len = len(df)
    print(f"    Initial rows: {initial_len}")

    rows_to_keep = []
    dropped_players = []
    corrected_players = []

    for idx, row in df.iterrows():
        name = str(row.get("Nickname", "")).strip()
        pos = str(row.get("Position", "")).strip()
        orig_team = str(row.get("Team", "")).strip()

        # Check canonical mapping
        real_team = CANONICAL_REAL_TEAMS.get(name)
        if not real_team:
            # Check team aliases if present
            real_team = TEAM_ALIASES.get(orig_team, orig_team)
        else:
            real_team = TEAM_ALIASES.get(real_team, real_team)

        # Check if team is in Week 2 schedule
        game_info = WEEK_2_GAMES.get(real_team)
        if not game_info:
            # Unknown or free agent
            rows_to_keep.append(row)
            continue

        # If team played on TNF, SNF, or MNF, drop from Sunday Main Slate
        if not game_info["is_main_slate"]:
            dropped_players.append((name, real_team, pos, game_info["game"]))
            continue

        # If team/opponent/game was wrong, fix it
        if real_team != orig_team or str(row.get("Opponent", "")).strip() != game_info["opp"]:
            corrected_players.append((name, orig_team, real_team, game_info["opp"], game_info["game"]))
            row["Team"] = real_team
            row["Opponent"] = game_info["opp"]
            row["Game"] = game_info["game"]

        rows_to_keep.append(row)

    df_clean = pd.DataFrame(rows_to_keep)
    df_clean.to_csv(csv_path, index=False)

    print(f"    Cleaned rows: {len(df_clean)} (Removed {len(dropped_players)} non-slate players)")
    print(f"    Corrected {len(corrected_players)} players with mismatched teams.")

    if dropped_players:
        print("\n--- SAMPLE DROPPED PLAYERS (Non-Main Slate: TNF / SNF / MNF) ---")
        for p in dropped_players[:12]:
            print(f"    - {p[0]} ({p[1]} {p[2]}) -> Game: {p[3]}")

    if corrected_players:
        print("\n--- SAMPLE CORRECTED PLAYERS (Mapped to Real NFL Team) ---")
        for p in corrected_players[:15]:
            print(f"    - {p[0]}: {p[1]} -> {p[2]} (Opp: {p[3]}, Game: {p[4]})")


def normalize_fantasy_db(db_path: str = "data/fantasy.db"):
    """Updates players table in fantasy.db with real-world pro_team mappings."""
    if not os.path.exists(db_path):
        return

    print(f"\n[*] Normalizing SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated = 0
    for name, real_team in CANONICAL_REAL_TEAMS.items():
        norm_team = TEAM_ALIASES.get(real_team, real_team)
        cur.execute(
            "UPDATE players SET pro_team = ? WHERE full_name = ? AND pro_team != ?",
            (norm_team, name, norm_team)
        )
        if cur.rowcount > 0:
            updated += cur.rowcount

    conn.commit()
    conn.close()
    print(f"    Updated {updated} player records in fantasy.db with real-world NFL teams.")


def normalize_player_crosswalk(crosswalk_path: str = "data/player_crosswalk.json"):
    """Updates player_crosswalk.json with real-world team mappings."""
    if not os.path.exists(crosswalk_path):
        return

    print(f"\n[*] Normalizing player crosswalk: {crosswalk_path}")
    with open(crosswalk_path, "r", encoding="utf-8") as f:
        cw = json.load(f)

    updated = 0
    for p in cw:
        name = p.get("full_name")
        if name in CANONICAL_REAL_TEAMS:
            real_t = CANONICAL_REAL_TEAMS[name]
            # Convert 2-letter / 3-letter Sleeper style if needed
            if p.get("team") != real_t:
                p["team"] = real_t
                updated += 1

    with open(crosswalk_path, "w", encoding="utf-8") as f:
        json.dump(cw, f, indent=2)

    print(f"    Updated {updated} records in player_crosswalk.json.")


if __name__ == "__main__":
    normalize_sunday_main_slate_csv()
    normalize_fantasy_db()
    normalize_player_crosswalk()
    print("\n[SUCCESS] Master NFL Roster Normalization complete!")
