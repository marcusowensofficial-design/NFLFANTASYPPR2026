# Project: Apex Fantasy Week 7 Platform Update & Live Injury Sync

## Architecture
- **Data Ingestion & Adapters (`src/adapters/nfl/`)**: Connects to ESPN API for live injury feeds, practice statuses, depth charts, schedules, and Vegas odds with offline local cache fallbacks.
- **Data Store & Cache (`data/`, SQLite `data/fantasy.db`)**: Primary persistence for league state (`LeagueModel.current_week`), players, matchups, injuries (`data/injuries_live_2026.json`), depth charts (`data/nfl_depth_charts_2026.json`), projections (`data/projections_week_7_2026.json`), and DFS slates.
- **Recommendation & Projection Engine (`src/services/recommendation/`)**: Calculates quant projections (Half-PPR / Full-PPR), in-house DvP ratings, start/sit ratings, and vacated beneficiary boosts.
- **FastAPI Backend Services (`web/backend/main.py`, `src/api/`)**: Serves RESTful endpoints (`/api/injuries`, `/api/lineup`, `/api/dfs`, `/api/recommendations`, `/api/waivers`) with automatic effective week resolution.
- **React Frontend Application (`web/frontend/`)**: Vite + React 19 SPA rendering Live Injuries, Lineup Optimizer, Matchups, Waivers, Projections, Defense vs. Position, and DFS Slates.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1.1 | ESPN Ingestion & Athlete ID Fix | Correct athlete ID extraction from links regex in `scripts/sync_live_injuries.py` | M1 | Survey Explorer 1 |
| F1.2 | Practice Status NLP Expansion | Expand regex/keywords for DNP, LP, FP in `injuries_client.py` and `sync_live_injuries.py` | M1 | Survey Explorer 1 |
| F1.3 | Beneficiary & Next-Man-Up Enrichment | Enrich injuries with next-man-up backups and vacated opportunity notes via depth charts | M1 | Survey Explorer 1 |
| F1.4 | Offline Local Disk Fallback | Add disk cache fallback to `data/injuries_live_2026.json` and `data/nfl_depth_charts_2026.json` | M1 | Survey Explorer 1 |
| F1.5 | 32-Team Injury Store Sync | Execute live sync across all 32 teams to produce validated `data/injuries_live_2026.json` | M1 | Survey Explorer 1 |
| F2.1 | SQLite Active Week Advancement | Advance `LeagueModel.current_week` in SQLite `data/fantasy.db` to Week 7 | M2 | Survey Explorer 2 |
| F2.2 | Week 7 Bye Teams Configuration | Set Week 7 bye teams (BUF, JAX, LAC, WSH) in `expert_consensus_service.py` & `WaiversTab.tsx` | M2 | Survey Explorer 2 |
| F2.3 | Schedule & Vegas Lines Update | Update `schedule_client.py` offline fallback for Week 7 and sync `data/vegas_movement_2026.json` | M2 | Survey Explorer 2 |
| F2.4 | In-House DvP Recalculation | Recalculate DvP FPA ratings across Weeks 1–6 into `data/nfl_dvp_proprietary_2026.json` & SQLite | M2 | Survey Explorer 2 |
| F2.5 | Week 7 Player Projections | Generate Week 7 projections in SQLite `PlayerModel` and `data/projections_week_7_2026.json` & `.parquet` | M2 | Survey Explorer 2 |
| F2.6 | Week 7 Waiver Consensus | Generate `data/waiver_expert_consensus_week_7_2026.json` for Week 7 bye casualty radar | M2 | Survey Explorer 2 |
| F2.7 | DFS Week 7 Main Slate Mapping | Map `SLATES_MAP["main"]` to `data/mainslate10-18-26.csv` and add "10-18" date parser in `loader.py` | M2 | Survey Explorer 2 & 3 |
| F3.1 | Frontend Week 7 Fallback Synchronization | Update `|| 6` fallback defaults to `|| 7` across `App.tsx` and all 8 frontend tab components | M3 | Survey Explorer 2 & 3 |
| F3.2 | Frontend Build Cleanliness | Verify `npm run build` succeeds cleanly with 0 TypeScript/bundling errors | M3 | Survey Explorer 3 |
| F3.3 | Backend API Router Verification | Verify `/api/injuries`, `/api/lineup`, `/api/dfs` return 200 with schema compliance | M3 | Survey Explorer 3 |
| F4.1 | E2E Pytest Suite (Tiers 1-2) | Implement `tests/test_week7_e2e_verification.py` for API contract and edge cases | M4 | Survey Explorer 3 |
| F4.2 | Live Server Socket Smoke Test (Tier 3) | Implement `scripts/verify_web_services_live.py` for real HTTP socket validation | M4 | Survey Explorer 3 |
| F4.3 | Full Regression & Acceptance (Tier 4) | Run full 179+ test suite and end-to-end acceptance checks | M4 | Survey Explorer 3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Live Injury & Practice Status Update | Ingest live 2026 NFL injury feeds, practice statuses (DNP/LP/FP), athlete ID fix, next-man-up enrichment, and cache fallbacks | none | DONE |
| M2 | Week 7 Season Transition | Advance SQLite league to Week 7, configure byes (BUF, JAX, LAC, WSH), update schedules, Vegas lines, DvP, projections, waiver consensus, and DFS slates | M1 | DONE |
| M3 | Frontend & API Synchronization | Synchronize frontend default week fallbacks to Week 7, verify `npm run build`, and ensure API endpoints respond with Week 7 data | M2 | DONE |
| M4 | E2E Verification & Hardening | Implement and pass comprehensive Week 7 test suite (`tests/test_week7_e2e_verification.py`), socket smoke test, and full regressions | M3 | DONE |

## Interface Contracts
### `scripts/sync_live_injuries.py` ↔ `data/injuries_live_2026.json`
- Ingests from ESPN API (`ESPN_INJURIES_URL`).
- Outputs JSON dict mapping `team_abbr` -> List of injury items.
- Item Schema:
  - `athlete_id`: int > 0 (extracted via `/id/(\d+)` regex from athlete links)
  - `name`: str
  - `position`: str
  - `status`: str (e.g. "Questionable", "Out", "Injured Reserve", "Doubtful")
  - `short_comment`: str
  - `long_comment`: str
  - `practice_status`: str ("DNP", "LIMITED", "FULL", "NOT_REPORTED")
  - `practice_trend`: str
  - `backup_athlete_name`: Optional[str]
  - `vacated_opportunity_note`: Optional[str]
  - `updated`: ISO UTC timestamp string

### `src/adapters/nfl/injuries_client.py` ↔ Consumers (`injury_routes.py`, `projection_engine.py`)
- `fetch_injuries() -> Dict[str, List[InjuryReport]]`:
  - Attempts live ESPN fetch.
  - On failure or empty, falls back to `data/injuries_live_2026.json`.
  - Enriches with `nfl_depthchart_client` for next-man-up beneficiaries.

### SQLite `leagues` ↔ Backend Services & APIs
- `LeagueModel.current_week`: int = 7.
- `resolve_effective_week(db, week)` returns 7 when `week is None`.

### `src/api/dfs_routes.py` & `src/dfs/loader.py` ↔ Frontend `DFSTab.tsx`
- `SLATES_MAP["main"]`: points to `data/mainslate10-18-26.csv` (Week 7 Sunday Main Slate).
- `loader.py` parses `"10-18"` date strings to October 18, 2026.
- Endpoint `/api/dfs/salaries?slate=main` returns HTTP 200 with Week 7 players.

## Code Layout
- `scripts/sync_live_injuries.py`: Live injury ingestion script.
- `src/adapters/nfl/injuries_client.py`: NFL injury adapter with regex parsing and disk fallback.
- `src/adapters/nfl/depthchart_client.py`: Depth chart adapter with disk fallback.
- `src/adapters/nfl/schedule_client.py`: NFL schedule adapter with Week 7 offline fallback.
- `src/services/recommendation/expert_consensus_service.py`: Bye teams configuration.
- `src/services/recommendation/projection_engine.py`: Quant projection engine.
- `src/services/recommendation/bulk_projection_service.py`: Bulk calibration for SQLite.
- `src/services/recommendation/dvp_calculator.py`: In-house DvP calculation.
- `src/api/dfs_routes.py`: DFS API endpoints and slate mappings.
- `src/dfs/loader.py`: DFS CSV ingestion and enrichment.
- `web/backend/main.py`: FastAPI application entrypoint.
- `web/frontend/src/`: React frontend components and tabs.
- `tests/test_week7_e2e_verification.py`: Dedicated Week 7 E2E test suite.
- `scripts/verify_web_services_live.py`: Real socket HTTP verification script.
