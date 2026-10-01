"""Canonical NFL Roster & Team Verification Module.

Enforces real-world NFL franchise assignments for all players, preventing
simulation artifacts, swapped team tags, and erroneous inclusions of players
who already played on Thursday Night or play in non-slate island games.
"""

import json
from pathlib import Path
from typing import Any
import pandas as pd

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
    "Cam Akers": "MIN",
    "Dameon Pierce": "HOU",
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
    "Brandin Cooks": "DAL",
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
    "Nick Vannett": "TEN",
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

# Dynamically synchronize CANONICAL_REAL_TEAMS from authoritative 2026 depth charts
try:
    _depth_chart_path = Path(__file__).resolve().parents[2] / "data" / "nfl_depth_charts_2026.json"
    if _depth_chart_path.exists():
        with open(_depth_chart_path, "r", encoding="utf-8") as _f:
            _dc = json.load(_f).get("teams", {})
            for _tm, _tdata in _dc.items():
                for _unit, _pdict in _tdata.items():
                    if isinstance(_pdict, dict):
                        for _pos, _plist in _pdict.items():
                            if isinstance(_plist, list):
                                for _p in _plist:
                                    if isinstance(_p, dict) and "name" in _p:
                                        CANONICAL_REAL_TEAMS[_p["name"]] = _tm
except Exception:
    pass

CANONICAL_TEAM_ALIASES: dict[str, list[str]] = {
    "WSH": ["WAS"],
    "WAS": ["WSH"],
    "JAX": ["JAC"],
    "JAC": ["JAX"],
    "LV": ["LVR", "OAK"],
    "LVR": ["LV", "OAK"],
    "TB": ["TBB"],
    "TBB": ["TB"],
    "NO": ["NOS"],
    "NOS": ["NO"],
    "SF": ["SFO"],
    "SFO": ["SF"],
    "GB": ["GBP"],
    "GBP": ["GB"],
    "KC": ["KCC"],
    "KCC": ["KC"],
    "NE": ["NEP"],
    "NEP": ["NE"],
    "LAR": ["LA", "STL"],
    "LA": ["LAR", "STL"],
}

TEAM_ALIASES: dict[str, str] = {
    "JAC": "JAX",
    "WAS": "WSH",
    "LVR": "LV",
    "TBB": "TB",
    "NOS": "NO",
    "SFO": "SF",
    "GBP": "GB",
    "KCC": "KC",
    "NEP": "NE",
    "LA": "LAR",
}


def resolve_team_alias(team: str, available_teams: Any) -> str | None:
    """Finds the matching team code within available_teams, checking aliases."""
    if not team:
        return None
    t_clean = str(team).upper().strip()
    if t_clean in available_teams:
        return t_clean
    for alias in CANONICAL_TEAM_ALIASES.get(t_clean, []):
        if alias in available_teams:
            return alias
    return None


def normalize_roster_dataframe(
    df: pd.DataFrame,
    team_vegas_schedule: dict[str, dict[str, Any]] | None = None,
    filter_non_slate: bool = True,
) -> pd.DataFrame:
    """Normalizes player team/opponent/game columns against real NFL teams.

    If team_vegas_schedule is provided, drops players whose real teams are not
    playing in the active slate games (e.g. Thursday TNF, Sunday Night SNF, Monday Night MNF).
    """
    rows_to_keep = []
    for _, row in df.iterrows():
        raw_name = row.get("Nickname")
        if pd.isna(raw_name) or not str(raw_name).strip():
            raw_name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
        name = str(raw_name).strip()
        orig_team = str(row.get("Team", "")).strip().upper()

        real_team = CANONICAL_REAL_TEAMS.get(name, orig_team)

        if team_vegas_schedule:
            # Match real_team or its alias in schedule
            matched_sched_team = resolve_team_alias(real_team, team_vegas_schedule)
            if not matched_sched_team:
                matched_sched_team = resolve_team_alias(orig_team, team_vegas_schedule)

            # If player's real team is not in the active slate schedule, drop
            if filter_non_slate and not matched_sched_team:
                continue

            if matched_sched_team:
                game_ctx = team_vegas_schedule[matched_sched_team]
                row["Team"] = matched_sched_team
                row["Opponent"] = game_ctx.get("opponent", row.get("Opponent"))
                row["Game"] = game_ctx.get("game", row.get("Game"))
            else:
                row["Team"] = real_team
        else:
            row["Team"] = real_team

        rows_to_keep.append(row)

    return pd.DataFrame(rows_to_keep)

