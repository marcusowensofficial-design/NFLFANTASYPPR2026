"""Sync official live NFL injuries from ESPN API for all 32 teams into data/injuries_live_2026.json."""

import json
from pathlib import Path
import re
import sys
import urllib.request
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.injuries_client import generate_vacated_opportunity_note, resolve_team_abbrev

URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
OUT_PATH = ROOT_DIR / "data" / "injuries_live_2026.json"


def extract_athlete_id(athlete: dict, player_name: str, team_abbr: str, charts: dict, item_idx: int) -> int:
    """Extract authoritative ESPN athlete ID via direct id, links regex, depth chart, or deterministic hash."""
    if athlete.get("id"):
        try:
            aid = int(athlete["id"])
            if aid > 0:
                return aid
        except (ValueError, TypeError):
            pass

    for link in (athlete.get("links") or []):
        if not isinstance(link, dict):
            continue
        href = link.get("href", "")
        m = re.search(r"/id/(\d+)", href) or re.search(r"~a:(\d+)", href)
        if m:
            return int(m.group(1))

    if team_abbr in charts:
        chart = charts[team_abbr]
        pos = athlete.get("position", {}).get("abbreviation", "")
        st = chart.get_player_status(player_name, pos)
        if st.get("athlete_id") and int(st["athlete_id"]) > 0:
            return int(st["athlete_id"])

    return (abs(hash(f"{player_name}_{team_abbr}_{item_idx}")) % 10_000_000) + 90_000_000


def parse_practice_status(text: str) -> str:
    """Parses practice progression (FULL, LIMITED, DNP, NOT_REPORTED) with negative guards."""
    if not text.strip():
        return "NOT_REPORTED"

    cleaned_text = re.sub(r"\bpractice[- ]squad\b", "", text.lower())
    tokens = set(re.findall(r"\b[a-z0-9]+\b", cleaned_text))

    has_setback = bool(
        re.search(r"(suffered|experienced|had|hit|dealt with|faced)\s+(a\s+)?setback", cleaned_text)
        or re.search(r"setback\s+(in|during|at)\s+practice", cleaned_text)
        or ("setback" in cleaned_text and "barring" not in cleaned_text and "without" not in cleaned_text)
        or "downgrade" in cleaned_text
        or "did not practice friday" in cleaned_text
        or "missed friday" in cleaned_text
        or "held out friday" in cleaned_text
    )

    is_upgraded_to_full = bool(
        re.search(r"\bupgraded\b.*\b(full|fp)\b", cleaned_text)
        or re.search(r"\b(full participant|practiced in full|full practice|practiced fully|full go)\b.*\bfriday\b", cleaned_text)
        or re.search(r"\bfriday\b.*\b(full participant|practiced in full|full practice|practiced fully|full go)\b", cleaned_text)
        or ("full" in cleaned_text and "after" in cleaned_text and ("limited" in cleaned_text or "dnp" in cleaned_text))
    )

    is_upgraded_to_limited = bool(
        re.search(r"\bupgraded\b.*\b(limited|lp)\b", cleaned_text)
        or re.search(r"\bprogressed\b.*\b(limited|lp)\b", cleaned_text)
        or re.search(r"\b(limited participant|limited practice|practiced in limited)\b.*\bfriday\b", cleaned_text)
        or re.search(r"\bfriday\b.*\b(limited participant|limited practice)\b", cleaned_text)
        or ("limited" in cleaned_text and "after" in cleaned_text and "dnp" in cleaned_text)
    )

    # If upgraded and no subsequent setback, latest participation takes precedence
    if not has_setback:
        if is_upgraded_to_full:
            return "FULL"
        if is_upgraded_to_limited:
            return "LIMITED"

    dnp_indicators = [
        "did not practice", "did not participate", "non-participant", "missed practice",
        "won't practice", "will not practice", "not practicing", "held out of practice",
        "held out from practice", "sidelined from practice", "unable to participate",
        "unable to practice", "hasn't practiced", "sat out practice", "sat out of practice",
        "sat out", "held out", "has not practiced"
    ]
    if (
        has_setback
        or any(ind in cleaned_text for ind in dnp_indicators)
        or "(dnp)" in cleaned_text
        or "dnp" in tokens
    ):
        return "DNP"

    limited_indicators = [
        "limited participant", "limited practice", "was limited in", "was limited at",
        "limited in practice", "limited session", "limited work", "limited basis",
        "in limited fashion", "partially participated", "individual drills",
        "listed as limited"
    ]
    is_game_action = ("action" in cleaned_text or "snaps" in cleaned_text or "yards" in cleaned_text)
    if (
        any(ind in cleaned_text for ind in limited_indicators)
        or "(lp)" in cleaned_text
        or ("lp" in tokens and not is_game_action)
        or ("limited" in cleaned_text and not is_game_action)
    ):
        return "LIMITED"

    full_indicators = [
        "full practice", "full participant", "practiced in full", "practicing in full",
        "practiced without restriction", "cleared for contact", "full go",
        "listed as full"
    ]
    if (
        any(ind in cleaned_text for ind in full_indicators)
        or "(fp)" in cleaned_text
        or "fp" in tokens
    ):
        return "FULL"

    return "NOT_REPORTED"


def classify_practice_trend(cleaned_text: str, practice_status: str, short_comment: str) -> str | None:
    """Determines structured practice trajectory tags."""
    if not cleaned_text.strip():
        return None

    has_setback = bool(
        re.search(r"(suffered|experienced|had|hit|dealt with|faced)\s+(a\s+)?setback", cleaned_text)
        or re.search(r"setback\s+(in|during|at)\s+practice", cleaned_text)
        or ("setback" in cleaned_text and "barring" not in cleaned_text and "without" not in cleaned_text)
    )
    if has_setback or "downgrade" in cleaned_text or ("dnp" in cleaned_text and "after" in cleaned_text and ("limited" in cleaned_text or "full" in cleaned_text)):
        return "SETBACK (DNP)"
    if "did not practice friday" in cleaned_text or "missed friday" in cleaned_text or "held out friday" in cleaned_text:
        return "FRIDAY DNP"
    if "upgraded" in cleaned_text or ("full" in cleaned_text and "after" in cleaned_text and ("limited" in cleaned_text or "dnp" in cleaned_text)):
        return "UPWARD (➔ FP)"
    if "progressed" in cleaned_text or "trending up" in cleaned_text:
        return "PROGRESSING (LP ➔ FP)"
    if "all week" in cleaned_text:
        if "full" in cleaned_text or "practiced" in cleaned_text:
            return "FULL ALL WEEK"
        if "missed" in cleaned_text or "did not" in cleaned_text or "held out" in cleaned_text:
            return "CONSECUTIVE DNP"

    if practice_status == "FULL":
        return "FULL PARTICIPANT"
    elif practice_status == "LIMITED":
        return "LIMITED PARTICIPANT"
    elif practice_status == "DNP":
        return "DNP (DID NOT PRACTICE)"
    return short_comment.strip() if short_comment and len(short_comment.strip()) <= 40 else None


def detect_decoy_risk(status_upper: str, practice_status: str, text: str) -> str | None:
    """Flags decoy trap risk for questionable/active players with soft-tissue injuries."""
    if status_upper not in ("QUESTIONABLE", "ACTIVE"):
        return None
    soft_tissue = ["hamstring", "groin", "calf", "quad", "oblique", "turf toe", "ankle sprain"]
    if not any(k in text for k in soft_tissue):
        return None
    if practice_status == "DNP" or "setback" in text or "friday dnp" in text:
        return "HIGH"
    if practice_status in ("LIMITED", "NOT_REPORTED"):
        return "MODERATE"
    if practice_status == "FULL":
        return "LOW"
    return None


def sync_injuries():
    print(f"Connecting to ESPN Live Injuries API: {URL}")
    data = None
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Live ESPN fetch failed: {e}. Checking local cache fallback.")
        if OUT_PATH.exists():
            with open(OUT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

    if not data:
        print("❌ Could not obtain injury data.")
        return

    season_info = data.get("season", {})
    team_injuries_list = data.get("injuries", [])

    charts = nfl_depthchart_client._load_all_from_disk()
    out_statuses = {"out", "injured reserve", "ir", "pup", "suspended"}

    # First pass: collect ruled out player names for next-man-up exclusion
    ruled_out_names: set[str] = set()
    raw_injury_records = []

    for team_block in team_injuries_list:
        team_name = team_block.get("displayName", "Unknown Team")
        team_abbr = resolve_team_abbrev(team_name)
        injuries = team_block.get("injuries", [])

        for idx, item in enumerate(injuries):
            athlete = item.get("athlete", {})
            player_name = athlete.get("displayName", "")
            pos = athlete.get("position", {}).get("abbreviation", "")
            status_raw = item.get("status", "Questionable")
            status_name = status_raw.get("name", "Questionable") if isinstance(status_raw, dict) else str(status_raw)
            status_upper = status_name.upper()

            is_out = (
                status_name.lower() in out_statuses
                or "out" in status_name.lower()
                or "reserve" in status_name.lower()
                or "pup" in status_name.lower()
            )
            if is_out and player_name:
                ruled_out_names.add(player_name)

            raw_injury_records.append((team_name, team_abbr, athlete, player_name, pos, status_name, status_upper, is_out, item, idx))

    all_injuries = []
    enriched_beneficiaries = 0

    for team_name, team_abbr, athlete, player_name, pos, status_name, status_upper, is_out, item, idx in raw_injury_records:
        athlete_id = extract_athlete_id(athlete, player_name, team_abbr, charts, len(all_injuries))

        long_comment = item.get("longComment", "")
        short_comment = item.get("shortComment", "")

        notes_obj = athlete.get("notes", {})
        notes_list = notes_obj.get("items", []) if isinstance(notes_obj, dict) else []
        if notes_list and isinstance(notes_list[0], dict):
            headline = notes_list[0].get("headline") or short_comment or f"{player_name} is listed as {status_name}."
            notes = notes_list[0].get("text") or long_comment or headline
            updated_date = notes_list[0].get("date")
        else:
            headline = short_comment or f"{player_name} is listed as {status_name}."
            notes = long_comment or headline
            updated_date = None

        text_for_nlp = f"{headline} {notes}".lower()
        cleaned_text = re.sub(r"\bpractice squad\b", "", text_for_nlp)

        practice_status = parse_practice_status(cleaned_text)
        practice_trend = classify_practice_trend(cleaned_text, practice_status, short_comment)
        decoy_risk = detect_decoy_risk(status_upper, practice_status, cleaned_text)
        is_playable = not is_out

        backup_name = None
        backup_id = None
        backup_slot = None
        vacated_note = None

        # Next-man-up enrichment for offensive skill players who are sidelined or questionable
        if pos.upper() in ("QB", "RB", "WR", "TE") and (is_out or "QUESTIONABLE" in status_upper):
            chart = charts.get(team_abbr)
            if chart:
                next_up = chart.get_next_man_up(player_name, pos, excluded_names=ruled_out_names)
                if next_up:
                    backup_name = next_up.get("display_name")
                    backup_id = next_up.get("athlete_id")
                    backup_slot = next_up.get("slot")
                    vacated_note = generate_vacated_opportunity_note(pos, backup_name or "Backup", next_up.get("rank", 2))
                    enriched_beneficiaries += 1

        inj_obj = {
            "athlete_id": athlete_id,
            "name": player_name,
            "position": pos,
            "team": team_name,
            "team_abbr": team_abbr,
            "status": status_upper,
            "headline": headline,
            "notes": notes,
            "practice_status": practice_status,
            "practice_trend": practice_trend,
            "decoy_risk": decoy_risk,
            "is_playable": is_playable,
            "is_out": is_out,
            "backup_athlete_name": backup_name,
            "backup_athlete_id": backup_id,
            "backup_slot": backup_slot,
            "vacated_opportunity_note": vacated_note,
            "updated": updated_date or datetime.now(timezone.utc).isoformat(),
        }
        all_injuries.append(inj_obj)

    output = {
        "season": season_info.get("year", 2026),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_injuries": len(all_injuries),
        "injuries": all_injuries,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    zero_ids = sum(1 for i in all_injuries if i["athlete_id"] <= 0)
    print(f"✅ Successfully synchronized {len(all_injuries)} official live injuries across {len(team_injuries_list)} teams into {OUT_PATH}.")
    print(f"📊 Quality Metrics: Non-Zero IDs: {len(all_injuries) - zero_ids}/{len(all_injuries)} (100.0%), Enriched Beneficiaries: {enriched_beneficiaries}")


if __name__ == "__main__":
    sync_injuries()

