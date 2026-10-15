# DFS & Quantitative Research Lab (`research/`)

This directory houses all **offline research, past slate solvers, historical simulations, backtesters, and exploratory audits**.

```
research/
├── slates/                       # Game-Specific & Historical Slate Solvers
│   ├── solve_det_buf_slate.py            # Detroit @ Buffalo Single-Game Island Slate
│   ├── solve_nyg_lar_slate.py            # NY Giants @ LA Rams Single-Game Slate
│   ├── solve_tb_dal_slate.py             # Tampa Bay @ Dallas Single-Game Slate
│   ├── solve_week3_optimal.py            # Week 3 Main Slate Optimal Knapsack Solver
│   ├── solve_week4_main_slate.py         # Week 4 Main Slate 3-Game Matrix Solver
│   ├── run_150_mme_tournament_engine.py  # 150-Max GPP Integer Programming Engine
│   └── ...                               # Other dedicated game-day slate scripts
│
├── backtests/                    # Historical Backtesting & Simulation Engines
│   ├── backtest_all_historical_weeks.py  # Multi-Week Accuracy & VORP Evaluator
│   ├── backtest_rams_49ers_sim.py        # Rams vs 49ers Retrospective Simulator
│   ├── sim_det_buf.py                    # 10,000-Trial DET @ BUF Monte Carlo Simulation
│   ├── simulate_showdown_monte_carlo.py  # Universal Single-Game Monte Carlo Simulator
│   └── syndicate_time_series_backtester.py # Vegas Steam & Line Velocity Backtester
│
├── audits/                       # Ad-Hoc Player, Defensive & Box Score Audits
│   ├── audit_2026_rosters.py             # Active NFL Roster Integrity Check
│   ├── audit_dvp_accuracy.py             # DvP S-Curve & Star Rating Forensic Verification
│   ├── audit_game_for_betting.py         # Live Vegas Odds & Player Props Validator
│   ├── audit_lineup_forensics.py         # Actual Contest Winning Lineup Reconstruction
│   ├── comprehensive_rb_analysis.py      # RB Route Participation & HVT Inside-5 Study
│   └── check_*.py                        # 19 Target, Injury & Slate Inspection Scripts
│
├── scratch/                      # Archived Game-Day Scratchpad Scripts (280+ files)
└── tests/                        # Ad-Hoc Verification Scripts (test_*.py)
```

## Moving Scripts between Research and Production
- Reusable, scheduled sync jobs and production algorithms belong in `scripts/` or `src/`.
- Ad-hoc investigations for specific game slates or historical reviews belong in `research/`.
