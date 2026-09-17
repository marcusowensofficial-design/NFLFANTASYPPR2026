# NFL Fantasy & DFS Institutional Master Table of Contents (2026 Season)

> **Persistent Institutional Map**: This directory documents the complete architectural layout of the entire NFL Fantasy & DFS platform. It encompasses every model, dataset, solver, adapter, service, and specialized skill developed across the project. Whenever opening a new conversation, refer to this catalog to immediately navigate the codebase.

---

## 1. Core Quant Projection Engines & Scoring Models

| File Path | Description | Key Features & Usages |
| :--- | :--- | :--- |
| [`src/services/recommendation/projection_engine.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/recommendation/projection_engine.py) | **Institutional Multi-Format Quant Engine** | Decoupled scoring for `PPR` (ESPN Season-Long) and `HALF_PPR` (FanDuel DFS). Integrates Trench Collision Multipliers (OL PBWR vs. DL Pressure), NGS micro-metrics, Coverage Shell Matchers (MOFO vs. MOFC), QB Pressure Redistribution, and Goal-Line Package Equity. |
| [`src/services/recommendation/nextgen_advanced_metrics.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/recommendation/nextgen_advanced_metrics.py) | **Next-Gen Positional Quantitative Metrics Engine** | Expected Fantasy Points (xFP) & FPOE engine (`Coiled Spring` buys vs `Mirage` fades), Scheme Coverage Shell Matcher (TPRR vs Zone/Man), QB Pressure Scramble & Checkdown Redistributor, and Goal-Line Package Equity (11 vs 12 vs Jumbo). |
| [`src/services/recommendation/scoring_engine.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/recommendation/scoring_engine.py) | **Start/Sit Composite Scoring Engine** | 0–100 deterministic player evaluation with full factor provenance (`[Volume]`, `[Red Zone]`, `[Separation]`, `[Regression]`, `[Matchup]`, `[Script]`). Enriched with Boris Chen GMM tiers, 8-man PPR leverage, and matchup elasticity. |
| [`scripts/generate_quant_projections.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/generate_quant_projections.py) | **Quant Projections CLI Utility** | Generate weekly projections (`--mode ppr`, `--mode half-ppr`, or `--mode both`). Calculates Format Arbitrage deltas and outputs xFP, FPOE, Zone TPRR, and HVT inside-5 shares. |
| [`src/dfs/loader.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/dfs/loader.py) | **DFS Slate Loader & Data Enrichment** | Parses FanDuel CSVs and enriches player pools with live Vegas spreads/totals, DvP rankings, milestone bonuses (+3.0 pts), Next Gen tracking metrics, and xFP/FPOE indicators. |
| [`src/dfs/ownership.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/dfs/ownership.py) | **DFS Ownership & Leverage Engine** | Computes projected tournament ownership %, ownership tiers (Chalk, Core, Mid, Contrarian), and mathematically sound GPP leverage scores. |

---

## 2. DFS Lineup Solvers & Optimization Engines

| File Path | Description | Key Features & Usages |
| :--- | :--- | :--- |
| [`scripts/solve_det_buf_slate.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/solve_det_buf_slate.py) | **Detroit @ Buffalo Showdown 5-Lineup Engine** | Solves calibrated 5-lineup tournament portfolio for Week 2 TNF (Knapsack 6-Starter Anchor, Gibbs TD Monopoly, Allen Outlier, Detroit Air Hedge, LaPorta Leverage Knapsack). Enforces $200–$800 unspent buffer and $\ge \$3,500$ single-entry floor. |
| [`src/dfs/showdown_optimizer.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/dfs/showdown_optimizer.py) | **FanDuel Showdown Solver Engine** | Native 6-slot (1 MVP @ 1.5x + 5 AnyFLEX) linear programming optimizer with automated multi-script generation (Team A dominant, Team B dominant, Balanced 4-2/3-3, Zero-QB). |
| [`scripts/run_showdown_optimizer.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/run_showdown_optimizer.py) | **Single-Game Multi-Script Solver** | Solves the 4 mandatory FanDuel showdown game scripts: (1) Team A Onslaught, (2) Team B Onslaught, (3) Balanced 4-2 / 3-3, and (4) Zero-QB Touchdown Monopoly. |
| [`scripts/solve_main_slate_matrix.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/solve_main_slate_matrix.py) | **Classic 9-Slot 3-Game Matrix Solver** | Solves Sunday Main Slate tournaments using the 3-Game Matrix: Primary Shootout Stack + Mini-Stack 1 + Mini-Stack 2 + Cheap Disruption D/ST ($200–$900 unspent buffer). |
| [`scripts/optimize_fanduel_lineup.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/optimize_fanduel_lineup.py) | **Knapsack Integer Programming Optimizer** | Enforces 1.5x MVP pricing math, the dynamic unspent salary buffer ($1,500–$3,500 on low totals), and the strict $\ge \$3,500$ single-entry punt floor. |
| [`scripts/sim_det_buf.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/sim_det_buf.py) | **10,000-Trial Monte Carlo DET @ BUF Simulator** | Correlated simulation with QB-receiver joint distributions, game total variance, and optimal lineup frequency tracking. |
| [`scripts/find_optimal_top3_showdown.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/find_optimal_top3_showdown.py) | **Exhaustive Combinatorial Showdown Solver** | Full MILP search evaluating all 3,104 valid roster combinations under strict single-entry rules. |
| [`scripts/find_sharp_5th_lineup.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/find_sharp_5th_lineup.py) | **Sharp Leverage 5th Lineup Knapsack Optimizer** | Identifies optimal leverage combinations leaving Cook out of the lineup and capturing tight end ceiling equity. |
| [`scripts/solve_vegas_props_lineup.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/solve_vegas_props_lineup.py) | **Pure Sportsbook Props Solver** | Solves showdown lineups strictly from consensus sportsbook receiving yards, rushing yards, and anytime touchdown probabilities. |
| [`scripts/check_final_dvp.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/check_final_dvp.py) | **Proprietary DvP Matchup Auditor** | Quick audit tool checking real positional points allowed and DvP rankings. |
| [`scripts/simulate_showdown_monte_carlo.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/simulate_showdown_monte_carlo.py) | **Monte Carlo Showdown Simulator** | Runs 10,000 game simulations with correlated covariance matrices to identify true 90th-percentile ceiling outcomes. |
| [`scripts/solve_tournament_stacks.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/solve_tournament_stacks.py) | **Tournament GPP Stack Generator** | Generates primary stacks (QB + WR1/TE1) with opposing bring-backs and anti-cannibalization rules. |
| [`scripts/audit_lineup_forensics.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/scripts/audit_lineup_forensics.py) | **Lineup Forensic Auditor** | Post-lock and post-game auditing tool checking correlation violations, MVP multiplier capture, and salary waste. |

---

## 3. In-Season Matchup, Roster & Strategic Services

| File Path | Description | Key Features & Usages |
| :--- | :--- | :--- |
| [`src/services/matchup/wrcb_matrix.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/matchup/wrcb_matrix.py) | **WR vs. CB Shadow Coverage Matrix** | Tracks perimeter (X/Z) vs. slot (Y) alignment, individual corner coverage grades, and shadow lockdown downgrades. |
| [`src/services/matchup/vegas_gamescript.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/matchup/vegas_gamescript.py) | **Vegas Game Script Engine** | Classifies environments into Shootout, Favorite Run Funnel, Underdog Pass Funnel, or Slugfest. |
| [`src/services/matchup/dvp_service.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/matchup/dvp_service.py) | **Defense vs. Position (DvP) Service** | Ingests DraftEdge and FantasyPros defensive rankings to provide matchup elasticity multipliers. |
| [`src/services/waiver/waiver_service.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/waiver/waiver_service.py) | **Dynamic VORP Waiver Wire Service** | Calculates Dynamic Value Over Replacement Player (VORP) against shallow 8-team waiver pools. |
| [`src/services/trade/trade_analyzer.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/trade/trade_analyzer.py) | **Trade Evaluation Engine** | Evaluates multi-player trades using weekly win-probability deltas and ROS projections. |
| [`src/services/espn_sync.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/espn_sync.py) | **ESPN Live League Synchronizer** | Pulls active rosters, scores, waivers, and standings from ESPN League #1841917737. |
| [`src/services/fantasypros_sync.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/fantasypros_sync.py) | **FantasyPros Intelligence Sync** | Ingests weekly ECR rankings, consensus projections, and expert start/sit grades. |
| [`src/services/sleeper_sync.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/sleeper_sync.py) | **Sleeper Projection Synchronizer** | Ingests Sleeper itemized weekly projections, ADP trends, and depth chart changes. |
| [`src/services/gamelog_service.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/services/gamelog_service.py) | **Game Log & Live Box Score Service** | Tracks play-by-play scoring, live snap rates, red-zone touches, and target distribution. |

---

## 4. Next Gen Stats, Film Charting & Scouting Data

| File Path | Description | Key Features & Contents |
| :--- | :--- | :--- |
| [`data/nextgen_micro_metrics_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/nextgen_micro_metrics_2026.json) | **Master Next-Gen Positional Dataset** | 29 starting QBs with scramble/checkdown/P2S rates, skill players with TPRR vs Zone/Man, slot rates, inside-5 shares, and 32 NFL coverage shells. |
| [`data/week_1_defensive_coverage_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/week_1_defensive_coverage_2026.json) | **32-Team Defensive Coverage Shell Database** | Coverage scheme usage rates across all 32 teams: Cover 0, 1, 2, 3, 4, 6, MOFC %, MOFO %, and Pass EPA allowed per dropback. |
| [`data/week_1_running_back_micro_metrics_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/week_1_running_back_micro_metrics_2026.json) | **Running Back Micro-Metrics Database** | Route participation %, inside-5 carry share, inside-10 touch share, YAC/attempt, and missed tackles forced. |
| [`data/week_1_receiver_micro_metrics_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/week_1_receiver_micro_metrics_2026.json) | **Next Gen Stats Receiver Tracking** | 63 receivers charted with Average Separation Score (ASS), First-Read Progression %, Targets Per Route Run (TPRR), and Coiled-Spring Regression Index. |
| [`data/team_personnel_and_pace_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/team_personnel_and_pace_2026.json) | **Team Personnel & Neutral Pace Database** | 32-team offensive personnel grouping rates (11 vs. 12 personnel) and seconds per play in neutral script. |
| [`data/redzone_efficiency_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/redzone_efficiency_2026.json) | **Red Zone Efficiency & Conversion Data** | Red zone trips per game, TD conversion %, FG attempt rate, and defensive goal-line stop rate. |
| [`data/nfl_intelligence_master_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/nfl_intelligence_master_2026.json) | **Consolidated NFL Intelligence Master** | Realized snaps, high-value touches (HVTs), CPOE, scramble rates, and efficiency metrics across all positions. |
| [`data/pff_scouting_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/pff_scouting_2026.json) | **PFF Trenches & Pass-Protection Scouting** | All 32 NFL teams with OL pass/run block grades & ranks, DL pressure % & ranks, and trench matchup grades. |
| [`data/nfl_depth_charts_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/nfl_depth_charts_2026.json) | **2026 Master Depth Charts** | Official 32-team depth charts with verified offensive and defensive starter roles. |
| [`data/injuries_live_2026.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/injuries_live_2026.json) | **Active Injury Wire & Inactives** | Live tracking of questionable/out designations and 90-minute pre-lock inactives. |
| [`data/detvsbuffalosinglegameslaterostersnsalaries.csv`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/detvsbuffalosinglegameslaterostersnsalaries.csv) | **Week 2 TNF Showdown Slate CSV** | FanDuel player salaries and positions for Detroit Lions @ Buffalo Bills (9/17/2026). |
| [`data/9-20-26-main-slate-rosters-salaries-fd-week2.csv`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/9-20-26-main-slate-rosters-salaries-fd-week2.csv) | **Week 2 Sunday Main Slate CSV** | Full FanDuel 13-game player list and salaries for Sunday Classic (9/20/2026). |
| [`data/WEEK_2_QUANT_BREAKOUT_RADAR.md`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/WEEK_2_QUANT_BREAKOUT_RADAR.md) | **Week 2 Breakout & Leverage Intelligence Radar** | In-depth strategic report on coiled springs, trench mismatches, and tournament anchors for Week 2. |
| [`data/WEEK_1_2026_MASTER_POST_MORTEM.md`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/WEEK_1_2026_MASTER_POST_MORTEM.md) | **Week 1 Empirical Post-Mortem & Law Verification** | Comprehensive mathematical audit proving the Dynamic Unspent Salary Law, 4-2/5-1 hegemony, and DvP 2.0x law. |
| [`data/single_game_slate_outcomes.json`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/single_game_slate_outcomes.json) | **Historical Slate Outcomes Master DB** | Machine-readable results and optimal lineups for all 16 slates of Week 1 2026. |
| [`data/SHOWDOWN_SLATE_RESULTS_ARCHIVE.md`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/SHOWDOWN_SLATE_RESULTS_ARCHIVE.md) | **Showdown Slate Results Archive** | Forensic review of optimal lineup architectures, MVP pricing regimes, and unspent salary proofs. |
| [`data/fantasy.db`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/data/fantasy.db) | **SQLite Production Database** | Master tables for league rosters, player models, projected stats, actual scores, matchups, and schedules. |

---

## 5. External Intelligence & Live Data Adapters

| File Path | Description | Key Features & Contents |
| :--- | :--- | :--- |
| [`src/adapters/betting/props_client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/betting/props_client.py) | **Vegas Player Props Client** | Scrapes sportsbook consensus player props (receptions O/U, yardage O/U, anytime TD odds, market sentiment). |
| [`src/adapters/nfl/schedule_client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/nfl/schedule_client.py) | **NFL Schedule & Game Environment Client** | Live game schedules, kickoff timestamps, dome status, game over/unders, and team implied totals. |
| [`src/adapters/nfl/dvp_client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/nfl/dvp_client.py) | **Defense-vs-Position (DvP) Client** | Positional fantasy points allowed and defensive softness rankings (1-32). |
| [`src/adapters/weather/client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/weather/client.py) | **Stadium Weather Forecast Client** | Real-time weather reporting (wind velocity, rain/snow probabilities, temperature, and dome overrides). |
| [`src/adapters/borischen/client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/borischen/client.py) | **Boris Chen Tier Client** | Ingests expert consensus Gaussian Mixture Model (GMM) statistical tiers. |
| [`src/adapters/polymarket/client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/polymarket/client.py) | **Polymarket Sentiment Client** | Prediction market implied odds on team wins, division titles, and game outcomes. |
| [`src/adapters/espn/client.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/adapters/espn/client.py) | **ESPN Fantasy League Client** | Live bi-directional integration with ESPN League #1841917737 (Team: "Blind Horse Named Dank"). |

---

## 6. Specialized Skills & Tactical Playbooks

| File Path | Description | Primary Operational Directive |
| :--- | :--- | :--- |
| [`.agents/skills/fanduel-single-game/SKILL.md`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/.agents/skills/fanduel-single-game/SKILL.md) | **FanDuel Single Game Master Playbook** | 1.5x MVP pricing regime math, Dynamic Unspent Salary Law, 4-2 / 5-1 stacking hegemony, correlation rules (D/ST vs. RB1 ban, QB Rule of 3). |
| [`.agents/skills/fanduel-main-slate/SKILL.md`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/.agents/skills/fanduel-main-slate/SKILL.md) | **FanDuel Main Slate Master Playbook** | 3-Game Geometric Matrix architecture, Good Chalk vs. Bad Chalk filtering, Rushing QB Ceiling Inversion, PFF trench multipliers, and Late-Swap FLEX discipline. |

---

## 7. Web Application & Full-Stack Interface

| Component | File Path | Description |
| :--- | :--- | :--- |
| **Backend API** | [`src/main.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/main.py) | FastAPI app serving REST endpoints on port 8000. |
| **DFS Endpoints** | [`src/api/dfs_routes.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/api/dfs_routes.py) | Slate loading, multi-script optimization, Next-Gen metrics delivery, and correlation audit routes. |
| **Start/Sit Endpoints**| [`src/api/routes.py`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/src/api/routes.py) | Lineup recommendation, Boris Chen comparison, and live score push routes. |
| **Frontend App** | [`frontend/src/App.tsx`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/App.tsx) | Modern React + TypeScript SPA dashboard. |
| **DFS Roster Board** | [`frontend/src/components/tabs/DfsRosterBoard.tsx`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/components/tabs/DfsRosterBoard.tsx) | Interactive FanDuel visual lineup board with live metrics ribbon, portfolio line tabs, Quick Picker, and Card/Table views. |
| **Roster Board CSS** | [`frontend/src/components/tabs/DfsRosterBoard.css`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/components/tabs/DfsRosterBoard.css) | Cyberpunk dark-mode styling with glassmorphic cards, vibrant positional pills, and animations. |
| **DFS Tab** | [`frontend/src/components/tabs/DfsTab.tsx`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/components/tabs/DfsTab.tsx) | Complete DFS workspace with slate catalog, interactive player pool table, custom projection inputs, and export modal. |
| **Start/Sit Tab** | [`frontend/src/components/tabs/CompareTab.tsx`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/components/tabs/CompareTab.tsx) | Side-by-side Start/Sit player comparator with factor breakdowns. |
| **Vegas & Intel Tab**| [`frontend/src/components/tabs/VegasTab.tsx`](file:///c:/Users/marco/OneDrive/Desktop/fantasydfs/frontend/src/components/tabs/VegasTab.tsx) | Vegas props O/U tracker and matchup intelligence. |

---

## 8. Common CLI Commands & Automation

```bash
# 1. Generate Weekly Projections (Format Comparison, xFP, FPOE & Next-Gen Micro-Metrics)
python scripts/generate_quant_projections.py --slate-csv data/detvsbuffalosinglegameslaterostersnsalaries.csv --mode half-ppr --limit 20

# 2. Run Single-Game Showdown Optimizer for Tonight's Island Game (DET @ BUF)
python scripts/solve_det_buf_slate.py

# 3. Solve Sunday Main Slate via 3-Game Geometric Matrix
python scripts/solve_main_slate_matrix.py --slate data/9-20-26-main-slate-rosters-salaries-fd-week2.csv

# 4. Run Monte Carlo Simulation (10,000 Iterations)
python scripts/sim_det_buf.py

# 5. Run Next-Gen Test Suite (8 of 8 Automated Tests)
python scripts/test_nextgen_metrics.py

# 6. Rebuild Master Next-Gen Micro-Metrics Dataset
python scripts/build_nextgen_dataset.py

# 7. Start Full Application (Backend + Frontend)
start.bat
```
