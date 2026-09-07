# 🏈 Apex Fantasy Analytics: ESPN Fantasy Football 2026 Assistant

A **local-first personal fantasy-football analytics assistant and lineup optimizer** designed for 8-team PPR ESPN Fantasy Football leagues during the 2026 NFL season. Inspired by the functional utility of FantasyPros My Playbook, but built entirely on ESPN league data, verified public NFL sources, an explainable deterministic Start/Sit scoring engine, and an automated roster slot optimizer.

---

## 📌 Project Overview & Guiding Principles

- **Local-First & Private:** All league data, API caches, and credentials remain on your local machine in SQLite and `.env`.
- **Zero Proprietary Scraping:** Does not scrape, copy, or bypass any paywalled or subscription services (e.g., FantasyPros, PFF).
- **Explainable Analytics:** Start/Sit recommendations derive from a transparent composite formula with weighted, documented factors and factual provenance—never fabricated by an LLM.
- **Dynamic Configuration:** Reads actual roster slots, lineup rules, and scoring settings directly from ESPN rather than hardcoding assumptions.
- **Strict Security:** **Never** requests or stores ESPN usernames or passwords. Private leagues authenticate via read-only browser session cookies (`SWID` and `espn_s2`).

---

## 🏗️ Architecture & Data Provider Stack

```
[ESPN Fantasy v3 API] ---------> [ESPN Adapter Layer] ---------\
[ESPN Public NFL API] ---------> [NFL Schedule/Odds/Injuries] ---> [Canonical Store / SQLite Cache]
[DynastyProcess / nflverse] ---> [Player ID Crosswalk] --------/         |
[Open-Meteo Weather API] ------> [Weather Provider] -----------/          |
                                                                          v
                                                           [Start/Sit Scoring Engine]
                                                           [Lineup Optimizer (ILP)]
                                                           [Waiver Wire Scanner]
                                                                          |
                                                                          v
                                                              [FastAPI REST Backend]
                                                                          |
                                                                          v
                                                              [React 19 Dashboard UI]
```

### Verified Data Sources for 2026

| Provider | Type | Cost / License | Data Provided | 2026 Role |
| :--- | :--- | :--- | :--- | :--- |
| **ESPN Fantasy v3 API** | Unofficial REST | Free | League metadata, roster settings, PPR scoring, team rosters, current week, ESPN player projections (`statSourceId=1`), waiver/free agent pool | **Core League Source** |
| **ESPN Public NFL API** | Public REST | Free | 2026 NFL schedule, live game clocks, stadium indoor/outdoor flags, DraftKings odds (spread & over/under for implied totals), official injuries & practice notes | **Live Matchup & Odds Layer** |
| **DynastyProcess ID Crosswalk** | Open Source (GitHub) | Free (MIT) | Cross-indexes ESPN Player ID, GSIS/nflverse ID, Sleeper ID, Yahoo ID, and normalized merge names (`merge_name`) | **Canonical Player Identity** |
| **nflverse / nflreadpy** | Open Source Data | Free | Historical & weekly advanced usage metrics: snap shares, target shares, air yards, carries, and red-zone opportunities | **Usage & Trend Component** |
| **Open-Meteo API** | Public REST | Free (CC-BY 4.0) | Stadium-specific temperature, wind speed, wind gusts, and precipitation probability | **Game-Day Weather Edge** |

---

## 🚀 Quickstart & How to Run

### Windows 1-Click Launchers (Easiest)
- Double-click [`start.bat`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/start.bat) to automatically start both the FastAPI backend and React frontend, and open the dashboard in your default browser.
- Double-click [`test_espn.bat`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/test_espn.bat) to test your ESPN connection or run the mock diagnostic test.

---

### Manual CLI Commands

### Step 1: Clone or Navigate to Directory
```bash
cd c:\Users\marco\OneDrive\Desktop\fantasydfs
```

### Step 2: Configure Environment Variables
Copy the example configuration file:
```bash
cp .env.example .env
```
Edit `.env` in any text editor and fill in your ESPN League ID:
```ini
ESPN_LEAGUE_ID=YOUR_ESPN_LEAGUE_ID
ESPN_SEASON=2026
```
*(If your league is private, also configure `ESPN_SWID` and `ESPN_S2` as explained below).*

### Step 3: Run the ESPN Connection Test (CLI)
You can immediately test your league connection or run the built-in mock test:

```bash
# Test with your configured .env league:
.venv\Scripts\python scripts\test_espn_connection.py

# Or test with the 2026 8-team PPR sample fixture:
.venv\Scripts\python scripts\test_espn_connection.py --mock
```

### Step 4: Run Automated Tests
```bash
.venv\Scripts\pytest
```

### Step 5: Start the Backend (FastAPI)
```bash
.venv\Scripts\uvicorn src.main:app --reload --port 8000
```
- API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- League Status: [http://127.0.0.1:8000/api/espn/status](http://127.0.0.1:8000/api/espn/status)

### Step 6: Start the Frontend Dashboard (React + Vite)
In a second terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open your browser to: [http://localhost:5173](http://localhost:5173)

---

## 🔑 How to Configure Private ESPN Leagues (SWID & espn_s2)

If your ESPN league is private, ESPN returns `401 Unauthorized` unless you supply active session cookies.

> [!IMPORTANT]
> **Security Guardrail**: Never provide your ESPN username or password. This application only requires read-only session cookies stored strictly in your local `.env`.

### Step-by-Step Cookie Extraction:
1. Open **Google Chrome**, **Microsoft Edge**, or **Firefox**.
2. Go to [https://fantasy.espn.com](https://fantasy.espn.com) and log in to your account.
3. Open your fantasy football league page.
4. Press `F12` (or right-click anywhere and select **Inspect**) to open Developer Tools.
5. In Developer Tools:
   - **Chrome / Edge:** Click the **Application** tab at the top.
   - **Firefox:** Click the **Storage** tab at the top.
6. In the left sidebar, expand **Cookies** and select `https://fantasy.espn.com` (or `https://espn.com`).
7. Search or look for the following two cookies:
   - **`SWID`**: Looks like `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}` (include the curly braces).
   - **`espn_s2`**: A long token of alphanumeric characters (~200+ characters).
8. Copy and paste them into your local `.env` file:
   ```ini
   ESPN_SWID={12345678-ABCD-EF01-2345-6789ABCDEF01}
   ESPN_S2=AEC...[your_long_token]...XYZ
   ```
9. Save `.env` and re-run `.venv\Scripts\python scripts\test_espn_connection.py`.

---

## 📊 What Data ESPN Successfully Provides

When connected, the ESPN Fantasy v3 API provides:
- **League Metadata:** Official league name, season, current matchup period/week, total teams.
- **Roster Settings:** Specific roster slots (e.g. 1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, 1 D/ST, 1 K, 7 Bench, 2 IR) mapped to ESPN slot IDs.
- **Scoring Settings:** Points per reception (Full PPR = 1.0), passing/rushing/receiving yardage rates, touchdown values, turnovers.
- **Teams & Owners:** All team nicknames, locations, owners, division assignments, and win-loss records.
- **Active Rosters:** Current starters, bench players, IR players, and lineup lock status.
- **Player Projections:** Weekly projected fantasy points calculated using your league's exact scoring rules (`statSourceId = 1`).
- **Free Agents & Waivers:** Full pool of unowned players with waiver priority and acquisition statuses.

---

## 📁 Repository Directory Structure

```
fantasydfs/
├── data/                               # Local SQLite databases (fantasy.db, player_crosswalk.db)
├── scripts/                            # Diagnostic, mock test & sync automation scripts
│   ├── test_espn_connection.py         # Diagnostic ESPN credential & league connectivity tester
│   └── test_fantasypros_integration.py # FantasyPros consensus data validator
├── src/                                # FastAPI Python Backend Engine
│   ├── main.py                         # Application entrypoint & CORS middleware
│   ├── adapters/                       # External API Integration Layer
│   │   ├── espn/                       # ESPN Fantasy v3 client, auth & slot translation
│   │   ├── fantasypros/                # FantasyPros consensus ECR & projection client
│   │   ├── nfl/                        # NFL schedule, game clock, Vegas lines & injury wire
│   │   └── weather/                    # Open-Meteo stadium forecast provider
│   ├── api/                            # REST API Endpoint Routers
│   │   ├── backtest_routes.py          # Model weight tuning & historical validation
│   │   ├── fantasypros_routes.py       # Consensus ECR rankings & streaming recommendations
│   │   ├── injury_routes.py            # Live NFL injury wire & practice tracker
│   │   ├── league_routes.py            # Standings, matchups, rosters & ESPN sync
│   │   ├── lineup_routes.py            # Optimal lineup solver, push to ESPN & inactives sweeper
│   │   ├── recommendation_routes.py    # Start/Sit comparator & persistent slider settings
│   │   └── waiver_routes.py            # Waiver upgrades & bench architecture audit
│   ├── core/                           # System Constants & Settings
│   │   ├── config.py                   # Pydantic environment configuration
│   │   └── constants.py                # ESPN slot IDs, scoring constants & default weights
│   ├── db/                             # Database Models & ORM
│   │   ├── models.py                   # SQLAlchemy schema (League, Player, UserSettings, etc.)
│   │   └── session.py                  # Database engine session factory
│   └── services/                       # Business Logic & Algorithms
│       ├── espn_sync.py                # Bidirectional ESPN league state synchronizer
│       ├── fantasypros_sync.py         # Multi-expert consensus sync pipeline
│       ├── backtesting/                # Historical backtest analysis & parameter tuning
│       ├── optimizer/                  # PuLP Integer Linear Programming (ILP) lineup solver
│       ├── recommendation/             # Explainable Start/Sit scoring engine & comparator
│       ├── trade/                      # 2-for-1 consolidation trade recommendation engine
│       └── waiver/                     # Waiver wire efficiency & deadweight bench analyzer
├── frontend/                           # React 19 + Vite Frontend Dashboard
│   ├── src/
│   │   ├── App.tsx                     # Modular orchestrator (~430 lines, reduced from 5,290 lines!)
│   │   ├── types.ts                    # Strongly-typed TypeScript interfaces
│   │   ├── main.tsx                    # React application entrypoint
│   │   ├── index.css                   # Custom dark-mode glassmorphism design system
│   │   └── components/
│   │       ├── modals/
│   │       │   └── PreFlightPushModal.tsx   # 1-Click ESPN push review & diff confirmation
│   │       ├── shared/
│   │       │   ├── InstitutionalStatCard.tsx# Itemized NFL box-score stats drawer
│   │       │   ├── InjuryStatusPill.tsx     # Interactive injury badge with doctor/practice notes
│   │       │   ├── MatchupRatingKey.tsx     # Collapsible star rating legend
│   │       │   ├── MatchupStarRating.tsx    # 1-to-5 star defensive matchup indicator
│   │       │   └── WhyHelpers.tsx           # Provenance driver badges & formula helpers
│   │       └── tabs/
│   │           ├── LineupTab.tsx            # Tab 1: Optimal Lineup & interactive swap sandbox
│   │           ├── CompareTab.tsx           # Tab 2: Head-to-Head Start/Sit Comparator (2-4 players)
│   │           ├── WaiversTab.tsx           # Tab 3: Waiver Upgrades & Bench Architecture Audit
│   │           ├── TradesTab.tsx            # Tab 4: 2-for-1 Consolidation Trade Analyzer
│   │           ├── InjuriesTab.tsx          # Tab 5: Live NFL Injury Wire & practice reports
│   │           ├── LeagueTab.tsx            # Tab 6: Official League Standings & Roster Explorer
│   │           ├── SettingsTab.tsx          # Tab 7: SQLite-Persisted Weights & Backtest Tuning
│   │           └── FantasyProsTab.tsx       # Tab 8: FantasyPros Consensus ECR & Streamers
├── tests/                              # Pytest Automated Test Suite (106 tests, 100% pass)
│   ├── test_8man_ppr_expert_enhancements.py
│   ├── test_8team_advanced_features.py
│   ├── test_8team_features.py
│   ├── test_all_features_e2e.py
│   ├── test_analytics_and_optimizer.py
│   ├── test_api.py
│   ├── test_db_and_sync.py
│   ├── test_dst_dvp_matchups.py
│   ├── test_elite_8team_upgrades.py
│   ├── test_enhanced_features.py
│   ├── test_espn_client.py
│   ├── test_fantasypros_integration.py
│   ├── test_matchups_and_accuracy.py
│   ├── test_roster_ordering.py
│   ├── test_start_sit_factor_scores.py
│   └── test_why_triggers.py
├── .gitignore                          # Safeguarded against DB locks and secrets
├── start.bat                           # 1-Click Windows launcher (Backend + Frontend)
└── pyproject.toml                      # Project metadata, dependencies & pytest config
```

---

## 🗺️ Project Roadmap & Implementation Status

- [x] **Phase 1: Architecture, Scaffolding & ESPN Connection Test** *(Completed)*
- [x] **Phase 2: ESPN League Dashboard & SQLite Database** *(Completed)*
  - SQLAlchemy models for League, Team, Player, RosterEntry, Matchup, and UserSettings.
  - Automated sync and snapshot caching with last-updated timestamps.
  - Full league overview UI: Standings, team rosters, and weekly matchups.
- [x] **Phase 3: External NFL Data & Player Identity Resolver** *(Completed)*
  - Ingestion of DynastyProcess ID mapping crosswalk into SQLite.
  - ESPN public NFL schedule, game times, dome flags, and DraftKings spreads/totals.
  - Official NFL injury reports, practice participation notes, and game-day inactive alerts.
- [x] **Phase 4: Explainable Start/Sit Scoring Engine** *(Completed)*
  - Transparent formula: Projection + Matchup + Opportunity + Trend + Game Environment + Weather + Availability.
  - Recalibrated composite scoring and interactive formula inspection drawers.
  - Positive and negative factor bullets with factual provenance.
- [x] **Phase 5: Lineup Optimizer & 1-Click Push to ESPN** *(Completed)*
  - Integer Linear Programming (ILP) solver matching ESPN roster slots.
  - Anti-Thursday early kickoff FLEX guardrails and correlation stacking synergy.
  - Pre-flight diff preview modal and real-time roster push directly to ESPN.
- [x] **Phase 6: Waiver-Wire Upgrade Analyzer** *(Completed)*
  - Evaluates unowned players vs current rostered players with live VORP calculation.
  - 8-Man Roster Architecture & Bench Audit (Grades A-D) with deadweight drop identification.
- [x] **Phase 7: Head-to-Head Comparison Tool & Modular Frontend** *(Completed)*
  - 2-4 player comparison workbench with factor breakdown bars and transparent calibration formulas.
  - Decomposed 5,290-line monolith `App.tsx` into 8 modular tabs and reusable components under `frontend/src/components/`.
- [x] **Phase 8: Backtesting & Model-Weight Optimization** *(Completed)*
  - Historical validation against prior weeks with Nelder-Mead automated weight optimization.
  - Persistent slider settings stored in SQLite (`UserSettingsModel`).
