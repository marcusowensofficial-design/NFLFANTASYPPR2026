# 🏈 Apex Fantasy Analytics: ESPN & Sleeper Fantasy Football 2026 Assistant

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/react-19.2+-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vite](https://img.shields.io/badge/vite-8.2+-646cff.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/tests-123%20passed-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A **local-first personal fantasy football analytics platform, institutional DFS quant engine, and automated lineup optimizer** designed for 8-team PPR leagues during the 2026 NFL season. Inspired by the functional utility of FantasyPros My Playbook and PFF Greenline, but built entirely on verified live data, explainable deterministic Start/Sit scoring, Integer Linear Programming (ILP) roster optimization, WR/CB shadow coverage analysis, Vegas game script environments, and 1-click roster execution back to ESPN.

---

## 📌 Project Overview & Core Philosophy

- **Local-First & Private:** All league data, API caches, and credentials remain on your local machine in SQLite (`data/fantasy.db`) and `.env`. Also includes containerized cloud-deployment support (Docker / Render).
- **Zero Proprietary Scraping:** Operates via legitimate public endpoints, official partner APIs, and open-source data crosswalks—no paywalled screen scraping or credential sniffing.
- **Explainable Quant Analytics:** Start/Sit recommendations derive from a transparent composite formula with weighted, documented factors and factual mathematical provenance—never hallucinated by an LLM.
- **Multi-Source Projection Parity:** Freely toggle or blend between **Quant Model**, **FantasyPros Consensus ECR**, **Sleeper / RotoWire**, and native **ESPN** weekly projections.
- **Vegas Player Props & Boris Chen Tiers:** Integrates consensus sportsbook player prop totals (receptions, yards, TD odds) and Gaussian Mixture Model (GMM) expert tier clusters.
- **Dual-Tier Educational Intelligence:** Hover tooltips across the entire interface provide clear "💡 What It Means" explanations for beginners alongside "🎯 Winning Edge" tactical advice for seasoned players.
- **Dynamic League Configuration:** Automatically reads actual roster slots, bench depth, lineup rules, and scoring settings directly from ESPN rather than hardcoding assumptions.
- **Strict Security:** **Never** requests or stores ESPN usernames or passwords. Private leagues authenticate via read-only browser session cookies (`SWID` and `espn_s2`).

---

## 🏗️ Architecture & Data Provider Stack

```
[ESPN Fantasy v3 API] ---------> [ESPN Adapter Layer] ------------\
[Sleeper API] -----------------> [Sleeper Adapter Layer] ----------\
[FantasyPros Consensus API] ---> [FantasyPros Adapter Layer] -----\ \
[Boris Chen GMM Tiers] --------> [Boris Chen Tier Adapter] --------\ \
[Sportsbook Props / Vegas] ----> [Vegas Props Engine] -------------\ \
[ESPN Public NFL API] ---------> [NFL Schedule, Vegas & Injuries] -> [Canonical Store / SQLite Cache]
[DynastyProcess / nflverse] ---> [Player ID Crosswalk] -----------/ /          |
[NFL Depth Charts & PFF-Style] -> [WR/CB Matchup Matrix] ---------/           |
[Open-Meteo Weather API] ------> [Stadium Weather Provider] -----/             |
                                                                               v
                                                                [Institutional Quant DFS Engine]
                                                                [Start/Sit Scoring Composite]
                                                                [PuLP Integer Linear Optimizer]
                                                                [Waiver Wire & Trade Analyzers]
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
| **ESPN Fantasy v3 API** | Unofficial REST | Free | League metadata, roster settings, PPR scoring, team rosters, current week, ESPN player projections (`statSourceId=1`), waiver pool | **Core League Source & Lineup Execution** |
| **Sleeper API** | Public REST | Free | Sleeper / RotoWire weekly player projections, player metadata, depth positions | **Alternative Projection Source** |
| **FantasyPros Public API** | REST API | Free / Keyed | Consensus Expert Consensus Rankings (ECR), projected points, positional tiers, streaming recommendations | **Consensus Multi-Expert Layer** |
| **Consensus Sportsbook Props** | Public REST / Odds Engine | Free | Player prop totals: Receptions O/U, Receiving/Rushing/Passing Yards O/U, Anytime TD odds, and implied PPR points with fallback synthesis | **Market-Implied PPR Floor & TD Edge** |
| **Boris Chen Tiers** | Public Feed / GMM Clustering | Free | Gaussian Mixture Model (GMM) tier clustering based on expert consensus with tier cliff drop-off alerts | **Objective Visual Tier Stratification** |
| **ESPN Public NFL API** | Public REST | Free | 2026 NFL schedule, live game clocks, stadium indoor/outdoor flags, DraftKings odds (spread & over/under for implied team totals), official injuries & practice notes | **Live Matchup, Vegas Odds & Injury Wire** |
| **DynastyProcess ID Crosswalk** | Open Source (GitHub) | Free (MIT) | Cross-indexes ESPN Player ID, GSIS/nflverse ID, Sleeper ID, Yahoo ID, and normalized merge names (`merge_name`) | **Canonical Multi-Platform ID Crosswalk** |
| **nflverse / nflreadpy** | Open Source Data | Free | Historical & weekly advanced usage metrics: snap shares, target shares, air yards, carries, and red-zone opportunities | **Usage & Opportunity Component** |
| **NFL Depth Charts & Matchups** | Public REST / Engine | Free | Team depth charts, receiver alignment percentages (LWR, RWR, Slot), cornerback shadow tracking, defensive personnel | **WR/CB Matchup & Shadow Matrix** |
| **Open-Meteo API** | Public REST | Free (CC-BY 4.0) | Stadium-specific temperature, wind speed, wind gusts, and precipitation probability | **Game-Day Weather Edge** |

---

## 🖥️ Modular 9-Tab Dashboard Features

The React 19 frontend is organized into 9 specialized tabs, providing institutional-grade fantasy management:

### 1. 📋 Lineup Tab (`LineupTab.tsx`)
- **Integer Linear Programming (ILP) Solver:** Solves the mathematically optimal starting roster using PuLP, honoring exact ESPN roster slots (QB, RB, WR, TE, FLEX, D/ST, K).
- **Anti-Thursday Early Kickoff Guardrail:** Automatically prevents early-kickoff (e.g. Thursday night) players from being placed in the FLEX spot, preserving weekend roster flexibility.
- **Inactives Sweeper Alert:** High-visibility banner alerting you to any rostered starter ruled OUT or placed on IR before game time.
- **Boris Chen GMM Tier Badges & Drop-Off Cliffs:** Live positional tier badges (e.g. `Tier 1 (Stud)`, `Tier 2 (Strong)`) with visual warning indicators on drop-off cliffs so you never bench a higher tier tier-breaker.
- **Consensus Vegas Player Props Pills:** Displays sportsbook-implied reception over/unders, yardage totals, anytime TD odds, and implied PPR floor points right on the roster card.
- **Interactive What-If Sandbox:** Drag-and-drop or click to swap any starter with bench players; recalculates optimal projections and deltas in real-time.
- **Pre-Flight Push Modal:** 1-Click synchronization pushes your confirmed optimal lineup directly to ESPN, featuring an itemized change diff before sending.
- **Dual-Tier Tooltips & Box-Score Drawer:** Drill into any player card or hover over DvP, ITT, or VORP to see beginner friendly explanations alongside sharp expert context.

### 2. ⚖️ Start/Sit Comparator (`CompareTab.tsx`)
- **Multi-Player Head-to-Head (2–4 Players):** Side-by-side comparison across any position or flex candidates.
- **🎲 Dedicated Vegas Sharp Lines Comparison:** Side-by-side sportsbook player props breakdown (Receptions O/U, Receiving/Rushing Yds, Anytime TD Odds, Market Implied PPR Points).
- **Boris Chen Tier Grouping & Range Analysis:** Compares expert consensus tiering and historical standard-deviation ranges to identify high-variance ceiling plays vs stable floors.
- **Factor Score Breakdown:** Visualizes normalized sub-scores (0–100) for **Projection**, **Matchup**, **Opportunity**, **Trend**, **Game Environment**, **Health/Availability**, and **Weather**.
- **Transparent Formula Provenance:** Displays exact positive and negative drivers explaining *why* a player is rated higher, derived purely from verifiable statistics.

### 3. 🎯 Matchup Intel Tab (`IntelTab.tsx`)
- **PFF-Style WR vs CB Matrix:** Route alignments (LWR, RWR, Slot %), primary cornerback coverage matchups, shadow corner alerts, and advantage ratings.
- **Vegas Game Script Environments:** Shootout tiers (*High-Scoring Shootout*, *Ground & Pound Clock Bleed*, *Defensive Trench War*, *One-Sided Blowout*), implied team totals, pace index, and projected pass/run distribution.
- **5-Star Defensive Matchup Ratings:** Visual 1-to-5 star defense-vs-position (DvP) grades with interactive tier badges and percentile rankings.
- **H2H Positional Tale of the Tape:** Slot-by-slot matchup comparison against your scheduled weekly league opponent, highlighting key leverage points and point deltas.
- **Interactive Beginner/Expert Hover Glossary:** Instant tooltips clarifying DvP, Shadow CB, ITT, Vegas O/U, and pace metrics for both beginner fantasy players and DFS pros.

### 4. 🔄 Waivers Tab (`WaiversTab.tsx`)
- **Value Over Replacement Player (VORP):** Live VORP calculations against current waiver-wire free agents calibrated for 8-team leagues.
- **8-Team Bench Architecture Audit:** Grades bench construction (Grades A through D) based on high-upside handcuff stashes vs low-ceiling roster cloggers.
- **Deadweight Drop Identifiers:** Highlights expendable bench players with negative net VORP.

### 5. 🤝 Trades Tab (`TradesTab.tsx`)
- **2-for-1 Consolidation Engine:** Designed specifically for shallow 8-man leagues where depth is cheap and elite tier-1 studs win championships.
- **Win-Win Partner Matching:** Analyzes opponents' rosters to find teams suffering from positional deficits who would benefit from trading a stud for two high-end starters.

### 6. 🏥 Injuries Tab (`InjuriesTab.tsx`)
- **Live NFL Practice Participation Wire:** Tracks Wednesday, Thursday, and Friday practice statuses (DNP, LP, FP) with practice progression trends.
- **Official Game Status:** Questionable, Doubtful, Out, and IR tracking with official team medical notes.

### 7. 🏆 League Tab (`LeagueTab.tsx`)
- **Official ESPN Standings & Matchups:** Live league standings, team records, points for/against, weekly matchup scores, and full opponent roster browser.

### 8. 📊 FantasyPros Tab (`FantasyProsTab.tsx`)
- **Expert Consensus Rankings (ECR):** Multi-expert consensus rankings, rank vs ADP deltas, positional tiers, and streaming target recommendations for DEF, K, and TE.

### 9. ⚙️ Settings Tab (`SettingsTab.tsx`)
- **SQLite-Persisted Model Weights:** Customize the weight of Projections, Matchups, Volume/Opportunity, Vegas Environment, Health, and Weather. Settings persist across app restarts via `UserSettingsModel`.
- **Automated Backtesting & Weight Tuning:** Uses the Nelder-Mead simplex algorithm to backtest and tune model weights against historical weeks to minimize prediction error.
- **Multi-Source Projection Switcher:** Select default projection source (**Quant Model**, **Multi-Source Consensus**, **FantasyPros**, **Sleeper**, or **ESPN**).

---

## 🚀 Quickstart & How to Run

### Windows 1-Click Launchers (Easiest)
- Double-click [`start.bat`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/start.bat) to automatically start both the FastAPI backend and React frontend, and launch the dashboard in your default browser.
- Double-click [`test_espn.bat`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/test_espn.bat) to run an immediate diagnostic test of your ESPN league credentials.

---

### Manual CLI Setup

#### Step 1: Clone or Navigate to Directory
```bash
cd c:\Users\marco\OneDrive\Desktop\fantasydfs
```

#### Step 2: Configure Environment Variables
Copy the example configuration file:
```bash
cp .env.example .env
```
Edit `.env` in any text editor and fill in your ESPN League ID:
```ini
ESPN_LEAGUE_ID=YOUR_ESPN_LEAGUE_ID
ESPN_SEASON=2026
```
*(If your league is private, configure `ESPN_SWID` and `ESPN_S2` as explained below).*

#### Step 3: Run the ESPN Connection Test (CLI)
Test your connection using the configured league or the built-in mock fixture:
```bash
# Test with your configured .env league:
.venv\Scripts\python scripts\test_espn_connection.py

# Or test with the 2026 8-team PPR sample fixture:
.venv\Scripts\python scripts\test_espn_connection.py --mock
```

#### Step 4: Run Automated Tests
```bash
.venv\Scripts\pytest
```
*Current test suite: **123 tests passed** across 19 test files (100% pass rate).*

#### Step 5: Start the Backend (FastAPI)
```bash
.venv\Scripts\uvicorn src.main:app --reload --port 8000
```
- API Interactive Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- League Status: [http://127.0.0.1:8000/api/espn/status](http://127.0.0.1:8000/api/espn/status)

#### Step 6: Start the Frontend Dashboard (React + Vite)
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser to: [http://localhost:5173](http://localhost:5173)

---

## 🐳 Containerization & Cloud Deployment

Apex Fantasy Analytics includes production-ready configuration for **Docker**, **Render**, and **Railway**:

### Docker Build & Run (Single Container for Full Stack)
The repository includes a multi-stage [`Dockerfile`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/Dockerfile) that builds the React 19 frontend into static assets and serves them directly via FastAPI:

```bash
# Build the production Docker container
docker build -t apex-fantasy-analytics:latest .

# Run container locally on port 8000
docker run -p 8000:8000 --env-file .env apex-fantasy-analytics:latest
```
Access the application at [http://localhost:8000](http://localhost:8000).

### Deploy to Render
The project includes a ready-to-deploy [`render.yaml`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/render.yaml) blueprint:
1. Connect your GitHub repository to [Render.com](https://render.com).
2. Create a **New Blueprint Instance** and select this repository.
3. Configure your secret environment variables (`ESPN_LEAGUE_ID`, `ESPN_SWID`, `ESPN_S2`) in the Render Dashboard.
4. Render automatically builds the multi-stage Docker image and serves the complete dashboard and API on a single web service.

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
7. Find the following two cookie values:
   - **`SWID`**: Looks like `{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}` (include the curly braces).
   - **`espn_s2`**: A long string of alphanumeric characters (~200+ characters).
8. Copy and paste them into your `.env` file:
   ```ini
   ESPN_SWID={12345678-ABCD-EF01-2345-6789ABCDEF01}
   ESPN_S2=AEC...[your_long_token]...XYZ
   ```
9. Save `.env` and verify via `.venv\Scripts\python scripts\test_espn_connection.py`.

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
│   ├── inspect_roster.py               # Quick CLI roster inspector
│   ├── migrate_db.py                   # SQLite schema migration utility
│   ├── run_backend.bat                 # Direct backend starter
│   ├── run_frontend.bat                # Direct frontend starter
│   ├── test_espn_connection.py         # Diagnostic ESPN credential & league connectivity tester
│   ├── test_lineup_push.py             # CLI lineup push validation test
│   └── verify_projections_and_swaps.py # Projection accuracy and swap validator
├── src/                                # FastAPI Python Backend Engine
│   ├── main.py                         # Application entrypoint, CORS, routers & SPA serving
│   ├── adapters/                       # External API Integration Layer
│   │   ├── betting/                    # Consensus sportsbook player props provider
│   │   │   └── props_client.py         # Receptions O/U, yards O/U, TD odds & implied PPR floor
│   │   ├── borischen/                  # Boris Chen GMM tier clustering integration
│   │   │   └── client.py               # Gaussian Mixture Model tiers & drop-off boundaries
│   │   ├── espn/                       # ESPN Fantasy v3 client, auth & slot translation
│   │   ├── fantasypros/                # FantasyPros consensus ECR & projection client
│   │   ├── nfl/                        # NFL schedule, depth charts, Vegas lines & injuries
│   │   │   ├── depthchart_client.py    # Team depth charts & receiver alignment tracking
│   │   │   ├── dvp_client.py           # Defense vs Position (DvP) calculations
│   │   │   ├── injury_client.py        # NFL practice tracker & injury wire
│   │   │   └── schedule_client.py      # NFL schedule, game clock & Vegas odds
│   │   ├── sleeper/                    # Sleeper API client & projections provider
│   │   │   └── client.py               # Sleeper / RotoWire weekly projections client
│   │   └── weather/                    # Open-Meteo stadium forecast provider
│   ├── api/                            # REST API Endpoint Routers
│   │   ├── analysis_routes.py          # WR/CB Matrix, Vegas Game Scripts, Props & Boris Chen Tiers
│   │   ├── backtest_routes.py          # Model weight tuning & historical validation
│   │   ├── fantasypros_routes.py       # Consensus ECR rankings & streaming recommendations
│   │   ├── injury_routes.py            # Live NFL injury wire & practice tracker
│   │   ├── league_routes.py            # Standings, matchups, rosters & ESPN sync
│   │   ├── lineup_routes.py            # Optimal lineup solver, push to ESPN & inactives sweeper
│   │   ├── recommendation_routes.py    # Start/Sit comparator & persistent slider settings
│   │   ├── sleeper_routes.py           # Sleeper projections sync endpoint
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
│       ├── sleeper_sync.py             # Sleeper / RotoWire projections synchronizer
│       ├── backtesting/                # Historical backtest analysis & parameter tuning
│       ├── matchup/                    # Matchup Intelligence Engine
│       │   ├── vegas_gamescript.py     # Vegas implied totals, pace & pass/run game scripts
│       │   └── wrcb_matrix.py          # WR vs CB route alignments & shadow coverage analysis
│       ├── optimizer/                  # PuLP Integer Linear Programming (ILP) lineup solver
│       ├── recommendation/             # Explainable Start/Sit scoring & DFS projection engine
│       │   ├── projection_engine.py    # Institutional quant projections & Bayesian ensembling
│       │   └── scoring_engine.py       # Multi-factor normalized scoring composite
│       ├── trade/                      # 2-for-1 consolidation trade recommendation engine
│       └── waiver/                     # Waiver wire efficiency & deadweight bench analyzer
├── frontend/                           # React 19 + Vite Frontend Dashboard
│   ├── src/
│   │   ├── App.tsx                     # Orchestrator coordinating all 9 tabs & global sync
│   │   ├── types.ts                    # Strongly-typed TypeScript interfaces
│   │   ├── main.tsx                    # React application entrypoint
│   │   ├── index.css                   # Custom dark-mode glassmorphism design system
│   │   └── components/
│   │       ├── modals/
│   │       │   └── PreFlightPushModal.tsx   # 1-Click ESPN push review & diff confirmation
│   │       ├── shared/
│   │       │   ├── InstitutionalStatCard.tsx# Itemized NFL box-score stats drawer
│   │       │   ├── InjuryStatusPill.tsx     # Interactive injury badge with practice progression
│   │       │   ├── MatchupRatingKey.tsx     # Collapsible star rating legend
│   │       │   ├── MatchupStarRating.tsx    # 1-to-5 star defensive matchup indicator
│   │       │   ├── Tooltip.tsx              # Dual-tier (Beginner/Expert) hover glossary & tips
│   │       │   └── WhyHelpers.tsx           # Provenance driver badges & formula helpers
│   │       └── tabs/
│   │           ├── LineupTab.tsx            # Tab 1: Optimal Lineup & interactive swap sandbox
│   │           ├── CompareTab.tsx           # Tab 2: Head-to-Head Start/Sit Comparator (2-4 players)
│   │           ├── IntelTab.tsx             # Tab 3: WR/CB Matchups, Vegas Game Script & Tale of the Tape
│   │           ├── WaiversTab.tsx           # Tab 4: Waiver Upgrades & Bench Architecture Audit
│   │           ├── TradesTab.tsx            # Tab 5: 2-for-1 Consolidation Trade Analyzer
│   │           ├── InjuriesTab.tsx          # Tab 6: Live NFL Injury Wire & practice reports
│   │           ├── LeagueTab.tsx            # Tab 7: Official League Standings & Roster Explorer
│   │           ├── FantasyProsTab.tsx       # Tab 8: FantasyPros Consensus ECR & Streamers
│   │           └── SettingsTab.tsx          # Tab 9: SQLite-Persisted Weights & Backtest Tuning
├── tests/                              # Pytest Automated Test Suite (123 tests, 100% pass)
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
│   ├── test_props_and_tiers.py
│   ├── test_roster_ordering.py
│   ├── test_sleeper_projections.py
│   ├── test_start_sit_factor_scores.py
│   ├── test_why_triggers.py
│   └── test_wrcb_and_vegas_intel.py
├── Dockerfile                          # Multi-stage container definition (Node 20 + Python 3.11)
├── render.yaml                         # 1-Click Render Cloud deployment blueprint
├── Procfile                            # Web server process runner
├── start.bat                           # 1-Click Windows launcher (Backend + Frontend)
├── start.ps1                           # PowerShell dual-service startup script
├── test_espn.bat                       # 1-Click ESPN connection diagnostic test
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
  - Positive and negative factor bullets with factual mathematical provenance.
- [x] **Phase 5: Lineup Optimizer & 1-Click Push to ESPN** *(Completed)*
  - Integer Linear Programming (ILP) solver matching ESPN roster slots.
  - Anti-Thursday early kickoff FLEX guardrails and correlation stacking synergy.
  - Pre-flight diff preview modal and real-time roster push directly to ESPN.
- [x] **Phase 6: Waiver-Wire Upgrade Analyzer** *(Completed)*
  - Evaluates unowned players vs current rostered players with live VORP calculation.
  - 8-Man Roster Architecture & Bench Audit (Grades A-D) with deadweight drop identification.
- [x] **Phase 7: Head-to-Head Comparison Tool & Modular Frontend** *(Completed)*
  - 2-4 player comparison workbench with factor breakdown bars and transparent calibration formulas.
  - Modularized frontend into 9 focused tabs and reusable components under `frontend/src/components/`.
- [x] **Phase 8: Backtesting & Model-Weight Optimization** *(Completed)*
  - Historical validation against prior weeks with Nelder-Mead automated weight optimization.
  - Persistent slider settings stored in SQLite (`UserSettingsModel`).
- [x] **Phase 9: Matchup Intelligence & Multi-Source Projection Parity** *(Completed)*
  - PFF-style WR vs CB Coverage Matrix with route alignment percentages and shadow alerts.
  - Vegas Game Script environments with implied team totals, pace index, and pass/run projections.
  - 5-Star Defensive Matchup Ratings (DvP) across all positions.
  - Positional Head-to-Head Tale of the Tape matching weekly opponents slot-by-slot.
  - Sleeper / RotoWire projections integration with multi-source switcher.
- [x] **Phase 10: Containerization & Cloud Deployment Architecture** *(Completed)*
  - Multi-stage Dockerfile combining Node.js 20 frontend build with Python 3.11 FastAPI backend.
  - Render blueprint (`render.yaml`) and SPA static asset routing directly via FastAPI.
- [x] **Phase 11: Vegas Player Props, Boris Chen GMM Tiers & Educational Tooltips** *(Completed)*
  - Consensus sportsbook player prop lines (Receptions O/U, Yardage O/U, Anytime TD odds, Implied PPR floor points).
  - Boris Chen Gaussian Mixture Model (GMM) tier clustering with tier drop-off cliff detection.
  - Interactive dual-tier tooltip system with instant beginner glossary & expert tactical edge across all tabs.
  - Comprehensive unit test coverage with 123 tests passing (100% pass rate).

