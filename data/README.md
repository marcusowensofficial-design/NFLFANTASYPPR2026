# Data Directory Organization (`data/`)

This directory contains production data assets, organized into dedicated active vs. archived domains:

```
data/
├── [Active Live Datasets]        # Read & Updated by Live API and Web Platform
│   ├── fantasy.db                # Active SQLite Production Database
│   ├── nfl_depth_charts_2026.json # Real-time NFL Depth Charts (32 teams)
│   ├── injuries_live_2026.json   # Live Injury Wires, Practice Status & Decoy Flags
│   ├── player_crosswalk.json     # Multi-Provider Player ID Identity Resolution
│   ├── player_props_live.json    # Live Consensus Prop Lines & Implied Touchdowns
│   ├── nfl_intelligence_master_2026.json # Master Team & Player Intelligence Feed
│   ├── draftedge_dvp_seed.json   # Base DvP Metric Seeds
│   ├── nfl_dvp_proprietary_2026.json # Proprietary S-Curve Defensive DvP Matrix
│   ├── pff_scouting_2026.json    # PFF Trench PBWR/PRWR & CB Shadow Alignments
│   ├── coach_fourth_down_tendencies_2026.json # Coach Aggressiveness & Kicker Multipliers
│   ├── nextgen_micro_metrics_2026.json # Optical Route Separation (ASS) & Shell Matches
│   ├── running_back_micro_metrics_2026.json # RB Route Participation & Inside-5 Shares
│   ├── receiver_micro_metrics_2026.json # WR/TE TPRR, YPRR, First-Read Volume
│   ├── redzone_efficiency_2026.json # 11 vs 12/21 Personnel Red Zone Conversions
│   ├── vegas_movement_2026.json  # Syndicate Steam, Line Velocity & Sharp Money
│   ├── encyclopedia/             # Super Brain Dual-Season (2025/2026) Encyclopedia
│   └── parquets/                 # High-Speed Columnar PyArrow Tables
│
├── slates/                       # Raw FanDuel Contest CSVs (Past & Uploaded)
│   ├── 9-20-26-main-slate-rosters-salaries-fd-week2.csv
│   ├── 10-12-26-bills-vs-rams-singlegameslate.csv
│   ├── KCVSBRONCOSSINGLEGAMESLATE9-14-26.csv
│   └── ...                       # All historical DFS salary CSVs
│
├── historical/                   # Past Actuals, Outcomes & Waiver Archives
│   ├── actuals_week1.json        # Week 1 Realized Box Scores
│   ├── actuals_week2.json        # Week 2 Realized Box Scores
│   ├── actuals_week3.json        # Week 3 Realized Box Scores
│   ├── waiver_expert_consensus_week_*.json # Historical Weekly Waiver Consensus
│   └── Sundaysinglegameslateoutcomes/ # Single Game Showdown Optimal Outlines
│
└── reports/                      # Master Post-Mortems & Quantitative Reports
    ├── WEEK_1_2026_MASTER_POST_MORTEM.md
    ├── WEEK_2_QUANT_BREAKOUT_RADAR.md
    ├── WEEK_3_2026_MASTER_POST_MORTEM.md
    ├── WEEK_4_QUANT_BREAKOUT_RADAR.md
    ├── GAMEDAY_REPORT_2026_09_13.md
    └── SHOWDOWN_SLATE_RESULTS_ARCHIVE.md
```
