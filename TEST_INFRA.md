# E2E Test Infra: Apex Fantasy Week 7 Platform & Live Injury Sync

## Test Philosophy
- Opaque-box, requirement-driven, and end-to-end verified.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial + Real-World Workload Testing.

## Feature Inventory & Test Mapping
| # | Feature | Source | Tier 1 (Contract) | Tier 2 (Boundaries) | Tier 3 (Cross-Module) |
|---|---------|--------|:-----------------:|:-------------------:|:---------------------:|
| 1 | Live Injury Ingestion & Statuses | R1 | ✓ | ✓ | ✓ |
| 2 | Practice Status NLP Parsing (DNP/LP/FP) | R1 | ✓ | ✓ | ✓ |
| 3 | Beneficiary Next-Man-Up & Vacated Opportunity | R1 | ✓ | ✓ | ✓ |
| 4 | Offline Disk Cache Fallback | R1 | ✓ | ✓ | ✓ |
| 5 | SQLite Active Week Advancement (Week 7) | R2 | ✓ | ✓ | ✓ |
| 6 | Week 7 Bye Teams (BUF, JAX, LAC, WSH) | R2 | ✓ | ✓ | ✓ |
| 7 | Schedule & Vegas Lines Sync | R2 | ✓ | ✓ | ✓ |
| 8 | In-House DvP Recalculation | R2 | ✓ | ✓ | ✓ |
| 9 | Week 7 Quant Projections (SQLite & JSON/Parquet) | R2 | ✓ | ✓ | ✓ |
| 10 | DFS Week 7 Main Slate Mapping (`mainslate10-18-26.csv`) | R2 | ✓ | ✓ | ✓ |
| 11 | Frontend Week 7 Fallback Sync & Build | R3 | ✓ | ✓ | ✓ |
| 12 | FastAPI Backend Endpoints (/api/injuries, /api/lineup, /api/dfs) | R3 | ✓ | ✓ | ✓ |

## Test Architecture
- **E2E Pytest Suite**: `tests/test_week7_e2e_verification.py`
  - Command: `python -m pytest tests/test_week7_e2e_verification.py -v`
  - Covers Tiers 1, 2, and 3: API responses, data types, status codes, non-zero athlete IDs, practice statuses, and DFS slate optimizations.
- **Live HTTP Socket Smoke Test**: `scripts/verify_web_services_live.py`
  - Command: `python scripts/verify_web_services_live.py`
  - Starts background FastAPI server on port 8000, queries live HTTP endpoints, verifies status 200, checks response payloads, tests shutdown.
- **Frontend Build Validation**:
  - Command: `cd web/frontend && npm run build`
  - Ensures clean TypeScript transpilation, asset bundling, and zero syntax errors.
- **Full Regression Suite**:
  - Command: `python -m pytest tests/ -q`
  - Ensures all 179+ existing tests pass with 0 regressions.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Full Tuesday Injury Sync & Practice Report Rollout | F1, F2, F3, F4 | High |
| 2 | Week 7 Lineup Generation with Bye Week Handling | F5, F6, F9, F12 | High |
| 3 | Week 7 Sunday Main Slate DFS Lineup Optimization | F10, F12 | Medium |
| 4 | Offline Disaster Recovery Mode (ESPN Down) | F4, F7, F12 | High |
| 5 | Full Web Platform End-to-End User Session (Injuries -> Lineup -> DFS) | All Features | High |

## Coverage Thresholds
- Tier 1: ≥5 checks per feature (HTTP status, schema, non-empty, field presence)
- Tier 2: Boundary & corner cases (empty cache, offline network, bye week players, inactive stars)
- Tier 3: Cross-module interactions (injuries -> lineup projections, schedule -> matchups -> DvP)
- Tier 4: ≥5 end-to-end integration workflows
