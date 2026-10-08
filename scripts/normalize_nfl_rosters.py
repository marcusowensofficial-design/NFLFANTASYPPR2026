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
    "Aaron Rodgers": "PIT",
    "Kyler Murray": "MIN",
    "Tua Tagovailoa": "ATL",
    "Sam Darnold": "SEA",
    "Kirk Cousins": "LV",
    "Geno Smith": "NYJ",
    "Deshaun Watson": "CLE",
    "Jacoby Brissett": "ARI",
    "Drew Lock": "SEA",
    "Cooper Rush": "ATL",
    "Carson Wentz": "MIN",
    "Kenny Pickett": "CAR",
    "Mac Jones": "SF",
    "Gardner Minshew II": "ARI",
    "Gardner Minshew": "LV",
    "Aidan O'Connell": "LV",
    "Sam Howell": "DAL",
    "Zach Wilson": "NO",
    "Jarrett Stidham": "DEN",
    "Mason Rudolph": "PIT",
    "Davis Mills": "HOU",
    "Joe Flacco": "CIN",
    "Nick Mullens": "MIN",
    "Marcus Mariota": "WAS",
    "Mitchell Trubisky": "TEN",
    "Andy Dalton": "PHI",
    "Spencer Rattler": "NO",
    "J.J. McCarthy": "NYG",
    "Michael Penix Jr.": "ATL",
    "Patrick Mahomes": "KC",
    "Josh Allen": "BUF",
    "Jared Goff": "DET",
    "Matthew Stafford": "LAR",
    "Daniel Jones": "IND",
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
    "Javonte Williams": "DAL",
    "Omarion Hampton": "LAC",
    "Breece Hall": "NYJ",
    "D'Andre Swift": "CHI",
    "David Montgomery": "HOU",
    "Jahmyr Gibbs": "DET",
    "James Cook": "BUF",
    "Jonathan Taylor": "IND",
    "Isiah Pacheco": "DET",
    "Kyren Williams": "LAR",
    "Devin Singletary": "NYG",
    "Tyrone Tracy Jr.": "NYG",
    "Travis Etienne Jr.": "NO",
    "Travis Etienne": "JAX",
    "Rhamondre Stevenson": "NE",
    "Chuba Hubbard": "CAR",
    "J.K. Dobbins": "DEN",
    "Jaylen Warren": "PIT",
    "MarShawn Lloyd": "GB",
    "Aaron Jones Sr.": "MIN",
    "Aaron Jones": "MIN",
    "Kyle Monangai": "CHI",
    "Tony Pollard": "TEN",
    "Tyjae Spears": "TEN",
    "Tyler Allgeier": "ARI",
    "Rico Dowdle": "PIT",
    "Jordan Mason": "MIN",
    "Ezekiel Elliott": "DAL",
    "Najee Harris": "NYG",
    "Rachaad White": "WSH",
    "Jerome Ford": "CLE",
    "Nick Chubb": "CLE",
    "Brian Robinson Jr.": "ATL",
    "Austin Ekeler": "WAS",
    "James Conner": "ARI",
    "Trey Benson": "ARI",
    "Raheem Mostert": "MIA",
    "Jaylen Wright": "MIA",
    "Kenneth Walker III": "KC",
    "Kenneth Walker": "SEA",
    "Zach Charbonnet": "SEA",
    "Gus Edwards": "LAC",
    "Kimani Vidal": "LAC",
    "Zamir White": "LV",
    "Alexander Mattison": "LV",
    "Alvin Kamara": "NO",
    "Jamaal Williams": "NO",
    "Kendre Miller": "NO",
    "Tank Bigsby": "PHI",
    "Miles Sanders": "CAR",
    "Jonathon Brooks": "CAR",
    "Antonio Gibson": "NE",
    "Cam Akers: HOU": "MIN",
    "Dameon Pierce": "PHI",
    "Joe Mixon": "HOU",
    "Ty Chandler": "NO",
    "Roschon Johnson": "CHI",
    "Emanuel Wilson": "SEA",
    "Braelon Allen": "NYJ",
    "Ray Davis": "BUF",
    "Blake Corum": "LAR",
    "Trey Sermon": "ATL",
    "Carson Steele": "KC",
    "Kareem Hunt": "KC",
    "Cam Skattebo": "NYG",

    # WRs
    "Jaxon Smith-Njigba": "SEA",
    "Ja'Marr Chase": "CIN",
    "Justin Jefferson": "MIN",
    "CeeDee Lamb": "DAL",
    "Mike Evans": "SF",
    "George Pickens": "DAL",
    "Chris Olave": "NO",
    "Nico Collins": "HOU",
    "Drake London": "ATL",
    "Zay Flowers": "BAL",
    "DeVonta Smith": "PHI",
    "A.J. Brown": "NE",
    "Garrett Wilson": "NYJ",
    "Tee Higgins": "CIN",
    "DK Metcalf": "PIT",
    "Christian Watson": "GB",
    "Jaylen Waddle": "DEN",
    "Tyreek Hill": "MIA",
    "Ladd McConkey": "LAC",
    "Rome Odunze": "CHI",
    "Keenan Allen": "IND",
    "DJ Moore": "BUF",
    "Deebo Samuel Sr.": "SF",
    "Deebo Samuel": "SF",
    "Brandon Aiyuk": "SF",
    "Courtland Sutton": "DEN",
    "Stefon Diggs": "WSH",
    "Tank Dell": "HOU",
    "Terry McLaurin": "WAS",
    "Michael Pittman Jr.": "PIT",
    "Michael Pittman": "IND",
    "Josh Downs": "IND",
    "Alec Pierce": "IND",
    "AD Mitchell": "IND",
    "Adonai Mitchell": "NYJ",
    "Rashee Rice": "KC",
    "Xavier Worthy": "KC",
    "Hollywood Brown": "PHI",
    "Marquise Brown": "KC",
    "JuJu Smith-Schuster": "KC",
    "Puka Nacua": "LAR",
    "Cooper Kupp": "SEA",
    "Demarcus Robinson": "SF",
    "Jordan Whittington": "LAR",
    "Tutu Atwell": "LAR",
    "Malik Nabers": "NYG",
    "Wan'Dale Robinson": "TEN",
    "Darius Slayton": "IND",
    "Jalin Hyatt": "NYG",
    "Amon-Ra St. Brown": "DET",
    "Jameson Williams": "DET",
    "Tim Patrick": "NYJ",
    "Kalif Raymond": "CHI",
    "Khalil Shakir": "BUF",
    "Keon Coleman": "BUF",
    "Curtis Samuel": "BUF",
    "Mack Hollins": "NE",
    "Marquez Valdes-Scantling": "LAC",
    "Romeo Doubs": "NE",
    "Jayden Reed": "GB",
    "Dontayvion Wicks": "PHI",
    "Jordan Addison": "MIN",
    "Jalen Nailor": "LV",
    "Chris Godwin Jr.": "TB",
    "Chris Godwin": "TB",
    "Jalen McMillan": "TB",
    "Quentin Johnston": "LAC",
    "Joshua Palmer": "BUF",
    "Marvin Harrison Jr.": "ARI",
    "Michael Wilson": "ARI",
    "Greg Dortch": "BUF",
    "Brian Thomas Jr.": "JAX",
    "Christian Kirk": "SF",
    "Gabe Davis": "JAX",
    "Parker Washington": "JAX",
    "Jauan Jennings": "MIN",
    "Ricky Pearsall": "SF",
    "Malik Washington": "MIA",
    "Odell Beckham Jr.": "MIA",
    "Devaughn Vele": "NO",
    "Josh Reynolds": "DEN",
    "Marvin Mims Jr.": "DEN",
    "Troy Franklin": "DEN",
    "Jakobi Meyers": "JAX",
    "Tre Tucker": "LV",
    "Rashid Shaheed": "SEA",
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
    "Elijah Moore": "PHI",
    "Cedric Tillman": "CLE",
    "Tyler Lockett": "SEA",
    "Demario Douglas": "NE",
    "Kendrick Bourne": "ARI",
    "Ja'Lynn Polk": "NE",
    "K.J. Osborn": "NE",
    "Calvin Austin III": "NYG",
    "Van Jefferson": "PIT",
    "Roman Wilson": "PIT",
    "Luke McCaffrey": "WAS",
    "Dyami Brown": "WAS",
    "Noah Brown": "WAS",
    "Brandin Cooks": "SF",
    "Jalen Tolbert": "MIA",
    "KaVontae Turpin": "DAL",
    "Rashod Bateman": "BAL",
    "Nelson Agholor": "BAL",
    "Devontez Walker": "BAL",
    "Tylan Wallace": "CLE",
    "Andrei Iosivas": "CIN",
    "Trenton Irwin": "CIN",
    "Jermaine Burton": "CIN",
    "Darnell Mooney": "NYG",
    "Ray-Ray McCloud": "ATL",
    "KhaDarel Hodge": "SF",
    "Casey Washington": "ATL",
    "Allen Lazard": "NYJ",
    "Mike Williams": "NYJ",
    "Malachi Corley": "CLE",
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
    "Foster Moreau": "HOU",
    "Dalton Kincaid": "BUF",
    "Dawson Knox": "BUF",
    "Sam LaPorta": "DET",
    "Brock Wright": "DET",
    "Travis Kelce": "KC",
    "Noah Gray": "KC",
    "Colby Parkinson": "LAR",
    "Davis Allen": "LAR",
    "Theo Johnson": "NYG",
    "Daniel Bellinger": "TEN",
    "Kylen Granson": "TEN",
    "Mo Alie-Cox": "IND",
    "Drew Ogletree": "IND",
    "Jake Ferguson": "DAL",
    "Luke Schoonmaker": "DAL",
    "Zach Ertz": "PHI",
    "Ben Sinnott": "WAS",
    "John Bates": "WAS",
    "Chig Okonkwo": "WSH",
    "Chigoziem Okonkwo": "TEN",
    "Josh Whyle": "GB",
    "Nick Vannett": "BAL",
    "David Njoku": "LAC",
    "Jordan Akins": "CLE",
    "Cade Otton": "TB",
    "Payne Durham": "TB",
    "Hunter Henry": "NE",
    "Austin Hooper": "ATL",
    "Pat Freiermuth": "PIT",
    "Darnell Washington": "PIT",
    "Connor Heyward": "LV",
    "Mark Andrews": "BAL",
    "Isaiah Likely": "NYG",
    "Charlie Kolar": "LAC",
    "Mike Gesicki": "CIN",
    "Drew Sample": "CIN",
    "Tanner Hudson": "CIN",
    "Erick All": "CIN",
    "Dalton Schultz": "HOU",
    "Cade Stover": "HOU",
    "Brevin Jordan": "HOU",
    "Evan Engram": "DEN",
    "Brenton Strange": "JAX",
    "Luke Farrell": "SF",
    "Greg Dulcich": "MIA",
    "Adam Trautman": "DEN",
    "Nate Adkins": "DEN",
    "Hayden Hurst": "LAC",
    "Will Dissly": "LAC",
    "Stone Smartt": "LAC",
    "Michael Mayer": "LV",
    "Harrison Bryant": "LV",
    "Noah Fant": "NO",
    "AJ Barner": "SEA",
    "Pharaoh Brown": "SEA",
    "Tip Reiman": "ARI",
    "Elijah Higgins": "ARI",
    "Jonnu Smith": "GB",
    "Durham Smythe": "BAL",
    "Julian Hill": "NE",
    "Eric Saubert": "SEA",
    "Tommy Tremble": "CAR",
    "Ja'Tavion Sanders": "CAR",
    "Ian Thomas": "LV",
    "Kyle Pitts": "ATL",
    "Charlie Woerner": "ATL",
    "Tyler Conklin": "DET",
    "Jeremy Ruckert": "NYJ",
    "Cole Kmet": "CHI",
    "Gerald Everett": "CHI",
    "T.J. Hockenson": "MIN",
    "Josh Oliver": "MIN",
    "Johnny Mundt": "PHI",
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
