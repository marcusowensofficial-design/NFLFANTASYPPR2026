# Apex Fantasy Web Platform Architecture (`web/`)

This directory is the dedicated home for all **Website Functions**, containing both the interactive Frontend UI and the Backend API services.

```
web/
├── frontend/                     # React 18 + Vite + TypeScript Web Application
│   ├── src/
│   │   ├── components/
│   │   │   ├── tabs/             # All 12 Interactive Dashboard Tabs:
│   │   │   │   ├── LeagueTab.tsx         # ESPN Roster, Standings, Matchup Scoreboard
│   │   │   │   ├── LineupTab.tsx         # Chronological Lineup Optimizer & Close Calls
│   │   │   │   ├── CompareTab.tsx        # Start/Sit Head-to-Head Matrix with Why Cards
│   │   │   │   ├── WaiversTab.tsx        # 4-Source Expert Consensus Board & Drop Scanner
│   │   │   │   ├── DfsTab.tsx            # Single Game Showdown & Main Slate Optimizer
│   │   │   │   ├── DfsRosterBoard.tsx    # Live Interactive Roster Builder (MVP + AnyFLEX)
│   │   │   │   ├── IntelTab.tsx          # Next-Gen Micro-Metrics, Coverage Shells & Trenches
│   │   │   │   ├── DvpTab.tsx            # Defense vs Position Matchup Elasticity
│   │   │   │   ├── VegasTab.tsx          # Real-time Syndicate Steam, Props & Spreads
│   │   │   │   ├── InjuriesTab.tsx       # Live Practice Reports, Inactive Wire & Decoys
│   │   │   │   ├── TradesTab.tsx         # 2-for-1 Depth Consolidation Analyzer
│   │   │   │   └── SettingsTab.tsx       # League Credentials & Strategy Tuning
│   │   │   ├── shared/           # Design System (Tooltips, Pills, Logos, Cards)
│   │   │   └── modals/           # Command Palette, Game Log Modal, Lineup Push
│   │   ├── types.ts              # TypeScript Data Contracts
│   │   ├── App.tsx               # Root App Layout & Tab Navigation
│   │   └── index.css             # Tailwind / Modern Dark-Mode Theme
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
│
└── backend/                      # Production FastAPI Application Services
    ├── main.py                   # FastAPI Application Entrypoint
    ├── routes.py                 # Registry of all 10 Website API Routers
    └── README.md                 # Detailed Endpoint Specification
```

## Running the Web Application

- **Full Stack Launcher**: Run `start.bat` (or `./start.ps1`) from the repository root.
- **Frontend Only**: `cd web/frontend && npm run dev` (Runs on http://localhost:5173).
- **Backend Only**: `python -m uvicorn web.backend.main:app --reload --port 8000` (Runs on http://127.0.0.1:8000).
- **Interactive API Docs**: http://127.0.0.1:8000/docs
