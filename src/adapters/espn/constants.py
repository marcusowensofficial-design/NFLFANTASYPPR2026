"""ESPN Fantasy Football constants, slot definitions, and stat mappings."""

from enum import IntEnum, StrEnum

ESPN_FFL_BASE_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
ESPN_PUBLIC_NFL_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

class RosterSlot(IntEnum):
    QB = 0
    TQB = 1
    RB = 2
    RB_WR = 3
    WR = 4
    WR_TE = 5
    TE = 6
    OP = 7  # Superflex (QB/RB/WR/TE)
    DT = 8
    DE = 9
    LB = 10
    DL = 11
    CB = 12
    S = 13
    DB = 14
    DP = 15
    DST = 16
    K = 17
    P = 18
    HC = 19
    BENCH = 20
    IR = 21
    FLEX = 23  # RB/WR/TE

SLOT_NAME_MAP: dict[int, str] = {
    RosterSlot.QB: "QB",
    RosterSlot.TQB: "TQB",
    RosterSlot.RB: "RB",
    RosterSlot.RB_WR: "RB/WR",
    RosterSlot.WR: "WR",
    RosterSlot.WR_TE: "WR/TE",
    RosterSlot.TE: "TE",
    RosterSlot.OP: "SUPERFLEX",
    RosterSlot.DST: "D/ST",
    RosterSlot.K: "K",
    RosterSlot.BENCH: "BE",
    RosterSlot.IR: "IR",
    RosterSlot.FLEX: "FLEX",
}

STARTER_SLOT_IDS: set[int] = {
    RosterSlot.QB,
    RosterSlot.RB,
    RosterSlot.WR,
    RosterSlot.TE,
    RosterSlot.FLEX,
    RosterSlot.OP,
    RosterSlot.DST,
    RosterSlot.K,
}

class StatSource(IntEnum):
    ACTUAL = 0
    PROJECTED = 1

class PlayerAvailabilityStatus(StrEnum):
    FREE_AGENT = "FREEAGENT"
    WAIVERS = "WAIVERS"
    ON_TEAM = "ONTEAM"

NFL_TEAM_MAP: dict[int, str] = {
    0: "FA",
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}

POSITION_ID_MAP: dict[int, str] = {
    1: "QB",
    2: "RB",
    3: "WR",
    4: "TE",
    5: "K",
    16: "D/ST",
}
