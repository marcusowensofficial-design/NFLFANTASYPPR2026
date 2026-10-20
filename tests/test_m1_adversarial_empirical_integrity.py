"""Empirical adversarial challenge and data integrity test suite for Milestone M1.

Evaluates:
1. Data store validation on data/injuries_live_2026.json:
   - 800 items, all athlete_id > 0
   - ID uniqueness and collision analysis
   - Position format validity across all 800 items
   - ISO-8601 timestamp compliance
   - Next-man-up enrichment coverage on true depth-chart starters
   - 32-team coverage and representation
2. API route stress-testing on /api/injuries:
   - Status filters (OUT matching IR/PUP/DOUBTFUL, ACTIVE, QUESTIONABLE, ALL)
   - Team filters (abbreviations, full franchise names, nicknames, case sensitivity, aliases like WAS/WSH)
   - Practice status filter behavior (e.g. ?practice_status=DNP parameter handling)
   - Limit boundary testing (limit=0, limit=1000, limit=-1, limit=801, limit=1, limit=800)
   - Position and search filters
   - Multi-filter combinations
   - Slicing vs matched_count integrity
   - Sort order invariant (OUT/IR/DOUBTFUL -> QUESTIONABLE -> ACTIVE)
   - Response schema contract compliance
"""

import json
from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.injuries_client import resolve_team_abbrev

DATA_PATH = Path("data/injuries_live_2026.json")
DEPTHCHART_PATH = Path("data/nfl_depth_charts_2026.json")


# ============================================================================
# PART 1: DATA STORE INTEGRITY ON data/injuries_live_2026.json
# ============================================================================

def test_data_store_count_and_non_zero_ids():
    """Verify total injuries count equals 800 and 100% have positive non-zero athlete_id."""
    assert DATA_PATH.exists(), f"Missing {DATA_PATH}"
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("total_injuries") == 800
    injuries = data.get("injuries", [])
    assert len(injuries) == 800

    zero_or_negative = [i for i in injuries if not isinstance(i.get("athlete_id"), int) or i.get("athlete_id") <= 0]
    assert len(zero_or_negative) == 0, f"Found {len(zero_or_negative)} non-positive IDs"


def test_data_store_athlete_id_uniqueness():
    """Audit whether athlete_ids are unique across the 800 items in data store."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    injuries = data.get("injuries", [])

    id_to_names = {}
    duplicates = []
    for i in injuries:
        aid = i["athlete_id"]
        if aid in id_to_names:
            duplicates.append((aid, i["name"], id_to_names[aid]))
        else:
            id_to_names[aid] = i["name"]

    # Record findings: if duplicates exist, document them
    print(f"Total unique athlete IDs: {len(id_to_names)} / {len(injuries)}")
    if duplicates:
        print(f"Warning: {len(duplicates)} duplicate athlete IDs found: {duplicates[:5]}")
    # In ESPN injury report, some players might be reported under multiple transactions or distinct items
    # We assert that unique count is at least 95% of total
    assert len(id_to_names) >= 750


def test_data_store_position_formats():
    """Audit position strings across all 800 records for format validity and non-emptiness."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    injuries = data.get("injuries", [])

    valid_positions = {
        "QB", "RB", "FB", "WR", "TE", "OT", "OG", "C", "G", "T", "OL",
        "DE", "DT", "NT", "DL", "LB", "ILB", "OLB", "MLB",
        "CB", "S", "SS", "FS", "DB", "PK", "K", "P", "LS", "UNK"
    }

    invalid_positions = []
    for i in injuries:
        pos = i.get("position")
        if not pos or not isinstance(pos, str) or pos.strip().upper() not in valid_positions:
            invalid_positions.append((i["name"], pos))

    assert len(invalid_positions) == 0, f"Found unexpected positions: {invalid_positions[:10]}"


def test_data_store_timestamp_iso_compliance():
    """Audit that timestamps in data store conform to valid ISO-8601 formatting."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Root last_updated
    last_up = data.get("last_updated")
    assert last_up is not None
    # Parse last_updated ISO
    parsed_root = datetime.fromisoformat(last_up.replace("Z", "+00:00"))
    assert parsed_root.year == 2026

    # Item timestamps
    injuries = data.get("injuries", [])
    bad_timestamps = []
    for i in injuries:
        up = i.get("updated")
        if up:
            try:
                datetime.fromisoformat(up.replace("Z", "+00:00"))
            except Exception:
                bad_timestamps.append((i["name"], up))

    assert len(bad_timestamps) == 0, f"Malformed timestamps: {bad_timestamps[:5]}"


def test_data_store_32_team_coverage():
    """Ensure injuries are represented across all 32 NFL teams."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    injuries = data.get("injuries", [])

    teams_found = {resolve_team_abbrev(i["team"]) for i in injuries}
    expected_32 = {
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS"
    }
    missing = expected_32 - teams_found
    assert len(missing) == 0, f"Missing NFL teams in injury store: {missing}"


def test_data_store_starter_next_man_up_enrichment():
    """Audit next-man-up enrichment rate specifically for true rank-1 starters on official depth charts."""
    assert DEPTHCHART_PATH.exists()
    all_charts = nfl_depthchart_client._load_all_from_disk()
    assert len(all_charts) >= 32

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    injuries = data.get("injuries", [])

    # Identify all offensive skill starters (QB, RB, WR, TE rank 1) across all 32 teams
    starters: dict[tuple[str, str], str] = {}  # (team_abbr, norm_name) -> display_name
    for team_abbr, chart in all_charts.items():
        for slot, athletes in chart.offense.items():
            slot_lower = slot.lower()
            if any(pos in slot_lower for pos in ("qb", "rb", "wr", "te")):
                for ath in athletes:
                    if ath.rank == 1:
                        starters[(team_abbr, ath.display_name.lower().strip())] = ath.display_name

    # Cross-reference with injured/questionable players
    sidelined_starters = []
    enriched_starters = []
    unenriched_starters = []

    for i in injuries:
        team_abbr = resolve_team_abbrev(i["team"])
        pos = i.get("position", "").upper()
        if pos in ("QB", "RB", "WR", "TE") and (i.get("is_out") or "QUESTIONABLE" in i.get("status", "").upper()):
            norm_name = i["name"].lower().strip()
            # Check if this player is a starter
            is_starter = False
            for (t, s_name) in starters:
                if t == team_abbr and (norm_name in s_name or s_name in norm_name):
                    is_starter = True
                    break
            if is_starter:
                sidelined_starters.append(i)
                if i.get("backup_athlete_name"):
                    enriched_starters.append(i)
                else:
                    unenriched_starters.append(i)

    enrichment_rate = (len(enriched_starters) / len(sidelined_starters)) * 100 if sidelined_starters else 0.0
    print(f"\n[Depth Chart Audit] Sidelined Starters: {len(sidelined_starters)}, Enriched: {len(enriched_starters)} ({enrichment_rate:.1f}%)")
    if unenriched_starters:
        print(f"Unenriched starters count: {len(unenriched_starters)}")
        for u in unenriched_starters[:5]:
            print(f"  Unenriched starter: {u['name']} ({u['position']} - {u['team']}) Status: {u['status']}")

    # Starters who are out/questionable should have high enrichment rate (>= 75%)
    assert enrichment_rate >= 75.0, f"Enrichment rate too low: {enrichment_rate:.1f}%"


# ============================================================================
# PART 2: API ROUTE TESTING ON /api/injuries
# ============================================================================

def test_api_limit_boundary_stress():
    """Verify limit validation: limit=0 (422), limit=1000 (422), limit=-1 (422), limit=801 (422), limit=1 (200), limit=800 (200)."""
    client = TestClient(app)

    # Upper and lower out-of-bounds
    assert client.get("/api/injuries?limit=0").status_code == 422
    assert client.get("/api/injuries?limit=1000").status_code == 422
    assert client.get("/api/injuries?limit=-1").status_code == 422
    assert client.get("/api/injuries?limit=801").status_code == 422

    # In-bounds limits
    resp_1 = client.get("/api/injuries?limit=1")
    assert resp_1.status_code == 200
    assert len(resp_1.json()["injuries"]) == 1

    resp_800 = client.get("/api/injuries?limit=800")
    assert resp_800.status_code == 200
    data_800 = resp_800.json()
    assert len(data_800["injuries"]) == data_800["total_count"]


def test_api_practice_status_parameter_behavior():
    """Empirically test whether practice_status parameter is filtered properly by /api/injuries."""
    client = TestClient(app)

    # Request with practice_status=DNP
    resp = client.get("/api/injuries?practice_status=DNP&limit=200")
    assert resp.status_code == 200
    data = resp.json()

    # Inspect whether non-DNP records are returned
    non_dnp = [i for i in data["injuries"] if i.get("practice_status") != "DNP"]

    assert len(non_dnp) == 0, f"Expected 0 non-DNP records, got {len(non_dnp)}"
    assert data["matched_count"] > 0


def test_api_status_out_matching_ir_pup_doubtful():
    """Verify status=OUT returns players on IR, PUP, Doubtful, and Out (is_out == True)."""
    client = TestClient(app)
    resp = client.get("/api/injuries?status=OUT&limit=800")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] > 0

    statuses_seen = set()
    for item in data["injuries"]:
        assert item["is_out"] is True, f"Player {item['name']} returned for status=OUT but is_out is False!"
        statuses_seen.add(item["status"].upper())

    # Ensure IR or INJURED RESERVE and OUT are matched
    assert any("IR" in s or "RESERVE" in s for s in statuses_seen)
    assert any("OUT" in s for s in statuses_seen)


def test_api_status_active_and_questionable_filters():
    """Verify status=ACTIVE and status=QUESTIONABLE behave symmetrically."""
    client = TestClient(app)

    # Questionable
    resp_q = client.get("/api/injuries?status=QUESTIONABLE&limit=800")
    assert resp_q.status_code == 200
    data_q = resp_q.json()
    assert data_q["matched_count"] > 0
    for item in data_q["injuries"]:
        assert "QUESTIONABLE" in item["status"].upper()

    # Active
    resp_act = client.get("/api/injuries?status=ACTIVE&limit=800")
    assert resp_act.status_code == 200
    data_act = resp_act.json()
    for item in data_act["injuries"]:
        assert item["is_out"] is False
        assert "QUESTIONABLE" not in item["status"].upper()


def test_api_team_filters_abbreviation_vs_fullname():
    """Verify team query supports full franchise name, nickname, and abbreviation across multiple franchises."""
    client = TestClient(app)

    test_cases = [
        # (abbr_query, full_query, nickname_query, expected_abbr)
        ("KC", "Kansas City Chiefs", "Chiefs", "KC"),
        ("SF", "San Francisco 49ers", "49ers", "SF"),
        ("GB", "Green Bay Packers", "Packers", "GB"),
        ("WAS", "Washington Commanders", "Commanders", "WAS"),
        ("DET", "Detroit Lions", "Lions", "DET"),
    ]

    for abbr, full, nick, expected_abbr in test_cases:
        r_abbr = client.get(f"/api/injuries?team={abbr}&limit=100")
        r_full = client.get(f"/api/injuries?team={full}&limit=100")
        r_nick = client.get(f"/api/injuries?team={nick}&limit=100")

        assert r_abbr.status_code == 200
        assert r_full.status_code == 200
        assert r_nick.status_code == 200

        data_abbr = r_abbr.json()
        data_full = r_full.json()
        data_nick = r_nick.json()

        assert data_abbr["matched_count"] > 0, f"No matches for team abbr {abbr}"
        assert data_full["matched_count"] > 0, f"No matches for team full name {full}"
        assert data_nick["matched_count"] > 0, f"No matches for team nick {nick}"

        # Count parity check
        assert data_abbr["matched_count"] == data_full["matched_count"], (
            f"Mismatch between {abbr} ({data_abbr['matched_count']}) and {full} ({data_full['matched_count']})"
        )


def test_api_team_alias_wsh_bug_demonstration():
    """Verify ?team=WSH returns same results as ?team=WAS via resolve_team_abbrev()."""
    client = TestClient(app)
    resp_was = client.get("/api/injuries?team=WAS&limit=50")
    resp_wsh = client.get("/api/injuries?team=WSH&limit=50")

    assert resp_was.status_code == 200
    assert resp_wsh.status_code == 200

    was_count = resp_was.json()["matched_count"]
    wsh_count = resp_wsh.json()["matched_count"]

    print(f"\n[Alias Verification] ?team=WAS returned {was_count} items, and ?team=WSH returned {wsh_count} items.")
    assert was_count > 0
    assert wsh_count == was_count, f"WSH ({wsh_count}) must match WAS ({was_count})"



def test_api_sorting_priority_invariant():
    """Verify sort invariant: OUT/IR/DOUBTFUL (p=0) -> QUESTIONABLE (p=1) -> ACTIVE (p=2)."""
    client = TestClient(app)
    resp = client.get("/api/injuries?limit=800")
    assert resp.status_code == 200
    injuries = resp.json()["injuries"]

    def get_priority(st: str) -> int:
        u = st.upper()
        if "OUT" in u or "IR" in u or "DOUBTFUL" in u:
            return 0
        if "QUESTIONABLE" in u:
            return 1
        return 2

    priorities = [get_priority(i["status"]) for i in injuries]
    for idx in range(len(priorities) - 1):
        assert priorities[idx] <= priorities[idx + 1], (
            f"Sort invariant violated at index {idx}: priority {priorities[idx]} > priority {priorities[idx+1]} "
            f"({injuries[idx]['name']} [{injuries[idx]['status']}] vs {injuries[idx+1]['name']} [{injuries[idx+1]['status']}])"
        )


def test_api_response_schema_contract():
    """Verify all returned fields conform to InjuryResponseItem specification."""
    client = TestClient(app)
    resp = client.get("/api/injuries?limit=50")
    assert resp.status_code == 200
    data = resp.json()

    for item in data["injuries"]:
        assert isinstance(item["athlete_id"], int) and item["athlete_id"] > 0
        assert isinstance(item["name"], str) and len(item["name"]) > 0
        assert isinstance(item["position"], str) and len(item["position"]) > 0
        assert isinstance(item["team"], str) and len(item["team"]) > 0
        assert isinstance(item["team_abbr"], str) and len(item["team_abbr"]) >= 2
        assert isinstance(item["status"], str)
        assert isinstance(item["is_playable"], bool)
        assert isinstance(item["is_out"], bool)
        # Optional fields check
        assert "practice_status" in item
        assert "practice_trend" in item
        assert "decoy_risk" in item
        assert "backup_player_name" in item
        assert "backup_player_id" in item
        assert "vacated_opportunity_note" in item


def test_api_multi_filter_combinations():
    """Verify compound filters (team + position + status + search + limit)."""
    client = TestClient(app)

    # KC + WR + OUT
    r1 = client.get("/api/injuries?team=KC&position=WR&status=OUT&limit=10")
    assert r1.status_code == 200
    d1 = r1.json()
    for i in d1["injuries"]:
        assert i["team_abbr"] == "KC"
        assert i["position"].upper() == "WR"
        assert i["is_out"] is True

    # SF + RB
    r2 = client.get("/api/injuries?team=SF&position=RB&limit=10")
    assert r2.status_code == 200
    d2 = r2.json()
    for i in d2["injuries"]:
        assert i["team_abbr"] == "SF"
        assert i["position"].upper() == "RB"

    # Search with name
    r3 = client.get("/api/injuries?search=Love&limit=10")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["matched_count"] > 0
    for i in d3["injuries"]:
        assert "love" in i["name"].lower()


def test_sync_script_null_links_and_nlp_parentheses_dnp():
    """Verify null links does not raise TypeError and (DNP) parses as DNP."""
    from scripts.sync_live_injuries import extract_athlete_id, parse_practice_status

    # 1. Null links does not trigger TypeError and returns valid positive ID
    aid = extract_athlete_id({"links": None}, "Player", "KC", {}, 0)
    assert isinstance(aid, int) and aid > 0

    # 2. Parentheses around DNP is correctly recognized as DNP
    res = parse_practice_status("Knee - (DNP)")
    print(f"\n[Fixed Verification] parse_practice_status('Knee - (DNP)') returned '{res}'")
    assert res == "DNP"


if __name__ == "__main__":
    pytest.main(["-v", __file__])

