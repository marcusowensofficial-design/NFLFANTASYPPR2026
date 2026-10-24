#!/usr/bin/env python3
"""Live Web Services & E2E Platform Verification Script for Apex Fantasy Analytics.

Validates Requirements R1, R2, and R3 per TEST_INFRA.md and PROJECT.md:
- R1: Live NFL Injuries, Practice Statuses, Beneficiary Next-Man-Up & Offline Cache Fallback.
- R2: Week 7 Season Transition (SQLite, Byes, Schedule, Vegas Lines, DvP, Projections, DFS Slate).
- R3: API Router Endpoints & Schemas (Injuries, DFS Salaries, Lineup Optimizer, DvP Ratings, Waiver Consensus, League Summary).

Usage:
    # In-process TestClient verification (hermetic, fast):
    python scripts/verify_web_services_live.py

    # Against a running uvicorn server (live socket test):
    python scripts/verify_web_services_live.py --server http://127.0.0.1:8000
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any
from unittest.mock import patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import pandas as pd
from starlette.testclient import TestClient

from src.adapters.nfl.depthchart_client import nfl_depthchart_client
from src.adapters.nfl.injuries_client import NFLInjuriesClient, parse_practice_status, resolve_team_abbrev
from src.adapters.nfl.schedule_client import NFLGame, nfl_schedule_client
from src.api.analysis_routes import resolve_effective_week
from src.api.dfs_routes import SLATES_MAP, _resolve_csv_path
from src.db.models import DefenseVsPositionModel, LeagueModel, PlayerModel
from src.db.session import SessionLocal
from src.services.waiver.expert_consensus_service import expert_consensus_service
from web.backend.main import app

DATA_DIR = PROJECT_ROOT / "data"


class VerificationResult:
    def __init__(self, check_id: int, category: str, name: str, expected: str, actual: str, passed: bool, notes: str = ""):
        self.check_id = check_id
        self.category = category
        self.name = name
        self.expected = expected
        self.actual = actual
        self.passed = passed
        self.notes = notes


class WebServicesLiveVerifier:
    def __init__(self, server_url: str | None = None, verbose: bool = False):
        self.server_url = server_url.rstrip("/") if server_url else None
        self.verbose = verbose
        self.test_client = TestClient(app) if not self.server_url else None
        self.results: list[VerificationResult] = []
        self._check_counter = 0

    def _record(self, category: str, name: str, expected: str, actual: str, passed: bool, notes: str = ""):
        self._check_counter += 1
        res = VerificationResult(
            check_id=self._check_counter,
            category=category,
            name=name,
            expected=expected,
            actual=actual,
            passed=passed,
            notes=notes,
        )
        self.results.append(res)
        if self.verbose:
            status_tag = "[PASS]" if passed else "[FAIL]"
            print(f"  {status_tag} {category} :: {name} -> {actual}")

    def _http_get(self, path: str) -> tuple[int, dict[str, Any] | list[Any]]:
        """Performs HTTP GET either via live HTTP or in-process TestClient."""
        if self.server_url:
            url = f"{self.server_url}{path}"
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url)
                return resp.status_code, resp.json()
        else:
            resp = self.test_client.get(path)
            return resp.status_code, resp.json()

    # ==========================================================================
    # Verification Stages
    # ==========================================================================

    def verify_data_stores(self):
        """Verifies local data files and SQLite database state for Week 7."""
        # 1. Injuries JSON
        inj_path = DATA_DIR / "injuries_live_2026.json"
        if not inj_path.exists():
            self._record("Data Store", "Injuries File Exists", "Exists", "Missing", False)
        else:
            with open(inj_path, "r", encoding="utf-8") as f:
                inj_data = json.load(f)
            injuries = inj_data.get("injuries", [])
            total = len(injuries)
            non_zero_ids = sum(1 for i in injuries if i.get("athlete_id", 0) > 0)
            teams = {i.get("team_abbr") or resolve_team_abbrev(i.get("team", "")) for i in injuries}

            self._record("Data Store", "Live Injuries Count", ">= 800", f"{total}", total >= 800)
            self._record("Data Store", "Athlete IDs Non-Zero", f"{total}/{total} (100%)", f"{non_zero_ids}/{total}", non_zero_ids == total)
            self._record("Data Store", "Injuries 32-Team Coverage", ">= 32 teams", f"{len(teams)} teams", len(teams) >= 32)

            # Next-man-up enrichment
            enriched = sum(1 for i in injuries if i.get("backup_athlete_name") and i.get("vacated_opportunity_note"))
            self._record("Data Store", "Next-Man-Up Enrichment", ">= 30 starters", f"{enriched} starters", enriched >= 30)

        # 2. Depth Charts JSON
        dc_path = DATA_DIR / "nfl_depth_charts_2026.json"
        if not dc_path.exists():
            self._record("Data Store", "Depth Charts File Exists", "Exists", "Missing", False)
        else:
            with open(dc_path, "r", encoding="utf-8") as f:
                dc_data = json.load(f)
            teams_dict = dc_data.get("teams", dc_data) if isinstance(dc_data, dict) else {}
            dc_teams = len(teams_dict)
            self._record("Data Store", "Depth Charts Teams", ">= 32 teams", f"{dc_teams} teams", dc_teams >= 32)

        # 3. Vegas Movement JSON
        vegas_path = DATA_DIR / "vegas_movement_2026.json"
        if not vegas_path.exists():
            self._record("Data Store", "Vegas Movement File Exists", "Exists", "Missing", False)
        else:
            with open(vegas_path, "r", encoding="utf-8") as f:
                vegas_data = json.load(f)
            v_week = vegas_data.get("week")
            v_games = len(vegas_data.get("games", []))
            self._record("Data Store", "Vegas Movement Week", "Week 7", f"Week {v_week}", v_week == 7)
            self._record("Data Store", "Vegas Movement Games Count", "14 games", f"{v_games} games", v_games == 14)

        # 4. Projections JSON & Parquet
        proj_json_path = DATA_DIR / "projections_week_7_2026.json"
        proj_parquet_path = DATA_DIR / "projections_week_7_2026.parquet"
        self._record("Data Store", "Projections JSON Exists", "Exists", "Exists" if proj_json_path.exists() else "Missing", proj_json_path.exists())
        self._record("Data Store", "Projections Parquet Exists", "Exists", "Exists" if proj_parquet_path.exists() else "Missing", proj_parquet_path.exists())

        if proj_json_path.exists():
            with open(proj_json_path, "r", encoding="utf-8") as f:
                pj = json.load(f)
            self._record("Data Store", "Projections JSON Records", ">= 300 players", f"{len(pj)} players", len(pj) >= 300)

        if proj_parquet_path.exists():
            df_pq = pd.read_parquet(proj_parquet_path)
            self._record("Data Store", "Projections Parquet Rows", ">= 300 rows", f"{len(df_pq)} rows", len(df_pq) >= 300)

        # 5. SQLite fantasy.db State
        db = SessionLocal()
        try:
            league = db.query(LeagueModel).order_by(LeagueModel.last_synced_at.desc()).first()
            cur_week = league.current_week if league else None
            self._record("Data Store", "SQLite League Active Week", "Week 7", f"Week {cur_week}", cur_week == 7)

            dvp_w7 = db.query(DefenseVsPositionModel).filter(
                DefenseVsPositionModel.season == 2026,
                DefenseVsPositionModel.week == 7,
            ).count()
            self._record("Data Store", "SQLite DvP Week 7 Records", "128 records (32 teams x 4)", f"{dvp_w7} records", dvp_w7 == 128)

            total_players = db.query(PlayerModel).count()
            calibrated_players = db.query(PlayerModel).filter(PlayerModel.projected_points.isnot(None)).count()
            self._record("Data Store", "SQLite Players Calibrated", f"100% ({total_players}/{total_players})", f"{calibrated_players}/{total_players}", total_players >= 390 and calibrated_players == total_players)
        finally:
            db.close()

        # 6. DFS Main Slate CSV Mapping
        csv_path = _resolve_csv_path("main")
        exists = Path(csv_path).exists()
        self._record("Data Store", "DFS Main Slate CSV Exists", "mainslate10-18-26.csv exists", f"{Path(csv_path).name} (exists={exists})", exists and "mainslate10-18-26.csv" in csv_path)

        if exists:
            df_raw = pd.read_csv(csv_path)
            self._record("Data Store", "DFS Main Slate Raw Rows", "512 rows", f"{len(df_raw)} rows", len(df_raw) == 512)

    def verify_offline_fallbacks(self):
        """Validates that network-disconnected adapters fall back seamlessly to disk."""
        # 1. Injuries client offline fallback
        inj_client = NFLInjuriesClient()
        inj_client.clear_cache()
        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Offline simulation")):
            fallback_inj = asyncio.run(inj_client.fetch_injuries(force=True))
        self._record("Offline Fallback", "NFLInjuriesClient Disk Fallback", ">= 800 records", f"{len(fallback_inj)} records", len(fallback_inj) >= 800)

        # 2. Depth chart client offline fallback
        nfl_depthchart_client.clear_cache()
        was_chart = nfl_depthchart_client._load_team_from_disk("WAS")
        wsh_chart = nfl_depthchart_client._load_team_from_disk("WSH")
        has_charts = (was_chart is not None) and (wsh_chart is not None)
        self._record("Offline Fallback", "NFLDepthChartClient WAS/WSH Disk Parity", "Valid TeamDepthChart for both", f"WAS={bool(was_chart)}, WSH={bool(wsh_chart)}", has_charts)

        # 3. Schedule client offline fallback
        fallback_schedule = nfl_schedule_client._get_fallback_schedule(week=7)
        self._record("Offline Fallback", "NFLScheduleClient Week 7 Disk Fallback", "14 games", f"{len(fallback_schedule)} games", len(fallback_schedule) == 14)

    def verify_api_endpoints(self):
        """Validates all REST API endpoints for HTTP 200, schema adherence, and data accuracy."""
        # 1. /api/injuries?team=WAS
        s1, d1 = self._http_get("/api/injuries?team=WAS")
        count_was = len(d1.get("injuries", [])) if s1 == 200 and isinstance(d1, dict) else 0
        self._record("API Endpoints", "GET /api/injuries?team=WAS", "HTTP 200, 25 records", f"HTTP {s1}, {count_was} records", s1 == 200 and count_was == 25)

        # 2. /api/injuries?team=WSH
        s2, d2 = self._http_get("/api/injuries?team=WSH")
        count_wsh = len(d2.get("injuries", [])) if s2 == 200 and isinstance(d2, dict) else 0
        self._record("API Endpoints", "GET /api/injuries?team=WSH", "HTTP 200, 25 records", f"HTTP {s2}, {count_wsh} records", s2 == 200 and count_wsh == 25)

        # 3. /api/injuries?practice_status=DNP
        s3, d3 = self._http_get("/api/injuries?practice_status=DNP")
        dnp_count = d3.get("matched_count", 0) if s3 == 200 and isinstance(d3, dict) else 0
        self._record("API Endpoints", "GET /api/injuries?practice_status=DNP", "HTTP 200, > 0 records", f"HTTP {s3}, {dnp_count} records", s3 == 200 and dnp_count > 0)

        # 4. /api/injuries?status=IR
        s4, d4 = self._http_get("/api/injuries?status=IR")
        ir_count = d4.get("matched_count", 0) if s4 == 200 and isinstance(d4, dict) else 0
        self._record("API Endpoints", "GET /api/injuries?status=IR", "HTTP 200, > 0 records", f"HTTP {s4}, {ir_count} records", s4 == 200 and ir_count > 0)

        # 5. /api/dfs/salaries?slate=main
        s5, d5 = self._http_get("/api/dfs/salaries?slate=main")
        dfs_total = d5.get("total_players", 0) if s5 == 200 and isinstance(d5, dict) else 0
        self._record("API Endpoints", "GET /api/dfs/salaries?slate=main", "HTTP 200, 464 players", f"HTTP {s5}, {dfs_total} players", s5 == 200 and dfs_total == 464)

        # 6. /api/lineup/optimize
        s6, d6 = self._http_get("/api/lineup/optimize")
        starters_count = len(d6.get("starters", [])) if s6 == 200 and isinstance(d6, dict) else 0
        self._record("API Endpoints", "GET /api/lineup/optimize", "HTTP 200, 9 starters", f"HTTP {s6}, {starters_count} starters", s6 == 200 and starters_count == 9)

        # 7. /api/analysis/dvp-ratings
        s7, d7 = self._http_get("/api/analysis/dvp-ratings")
        dvp_count = len(d7) if s7 == 200 and isinstance(d7, list) else 0
        self._record("API Endpoints", "GET /api/analysis/dvp-ratings", "HTTP 200, 128 records", f"HTTP {s7}, {dvp_count} records", s7 == 200 and dvp_count == 128)

        # 8. /api/waiver/consensus-board
        s8, d8 = self._http_get("/api/waiver/consensus-board")
        w_week = d8.get("week") if s8 == 200 and isinstance(d8, dict) else None
        self._record("API Endpoints", "GET /api/waiver/consensus-board", "HTTP 200, week 7", f"HTTP {s8}, week {w_week}", s8 == 200 and w_week == 7)

        # 9. /api/league/summary
        s9, d9 = self._http_get("/api/league/summary")
        l_week = d9.get("current_week") if s9 == 200 and isinstance(d9, dict) else None
        l_teams = len(d9.get("teams", [])) if s9 == 200 and isinstance(d9, dict) else 0
        self._record("API Endpoints", "GET /api/league/summary", "HTTP 200, week 7, 8 teams", f"HTTP {s9}, week {l_week}, {l_teams} teams", s9 == 200 and l_week == 7 and l_teams == 8)

    def print_summary_table(self) -> bool:
        """Prints a human-readable ASCII table of all verification checks."""
        header = f"{'#':<3} | {'Category':<16} | {'Component / Check':<36} | {'Expected':<30} | {'Actual':<30} | {'Status':<6}"
        separator = "-" * len(header)

        print("\n" + "=" * len(header))
        print("  APEX FANTASY PLATFORM: WEEK 7 E2E WEB SERVICES VERIFICATION SUITE")
        if self.server_url:
            print(f"  Target: Remote Server ({self.server_url})")
        else:
            print("  Target: In-Process FastAPI TestClient (Hermetic)")
        print("=" * len(header))
        print(header)
        print(separator)

        all_passed = True
        for r in self.results:
            status_str = "PASS" if r.passed else "FAIL"
            if not r.passed:
                all_passed = False
            print(f"{r.check_id:<3} | {r.category:<16} | {r.name:<36} | {r.expected:<30} | {r.actual:<30} | {status_str:<6}")

        print(separator)
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        print(f"  TOTAL CHECKS: {total} | PASSED: {passed} | FAILED: {failed}")
        print("=" * len(header) + "\n")

        if all_passed:
            print(">>> [SUCCESS] All Week 7 E2E Web Services & Contracts PASSED 100% genuine verification.\n")
        else:
            print(">>> [FAILURE] One or more verification checks failed. Inspect table above.\n")

        return all_passed


def main():
    parser = argparse.ArgumentParser(description="Verify Week 7 Web Services and Endpoints Live")
    parser.add_argument("--server", type=str, default=None, help="Base URL of running server (e.g. http://127.0.0.1:8000)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress logs")
    args = parser.parse_args()

    verifier = WebServicesLiveVerifier(server_url=args.server, verbose=args.verbose)
    verifier.verify_data_stores()
    verifier.verify_offline_fallbacks()
    verifier.verify_api_endpoints()

    passed = verifier.print_summary_table()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
