import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query
import numpy as np
from pydantic import BaseModel, Field

from src.dfs.engine import dfs_engine
from src.dfs.loader import dfs_loader
from src.dfs.optimizer import dfs_optimizer
from src.dfs.analyzer import dfs_analyzer
from src.dfs.showdown_optimizer import FanDuelShowdownOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dfs", tags=["DFS Optimizer"])


def _np_default(o: Any) -> Any:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

SLATES_MAP: dict[str, dict[str, Any]] = {
    "main": {
        "id": "main",
        "name": "Week 2 Main Slate ($60k Classic)",
        "games_count": 13,
        "platform": "FanDuel ($60k Cap)",
        "is_showdown": False,
        "default_csv": str(DATA_DIR / "9-20-26-main-slate-rosters-salaries-fd-week2.csv"),
    },
    "showdown_tnf": {
        "id": "showdown_tnf",
        "name": "Week 2 TNF: Detroit at Buffalo ($60k Showdown)",
        "games_count": 1,
        "platform": "FanDuel Showdown (1.5x MVP + 5 FLEX)",
        "is_showdown": True,
        "default_csv": str(DATA_DIR / "detvsbuffalosinglegameslaterostersnsalaries.csv"),
    },
    "main_week1": {
        "id": "main_week1",
        "name": "Week 1 Main Slate Archive ($60k Classic)",
        "games_count": 13,
        "platform": "FanDuel ($60k Cap)",
        "is_showdown": False,
        "default_csv": str(DATA_DIR / "mainslate9-13-2026.csv") if (DATA_DIR / "mainslate9-13-2026.csv").exists() else str(DATA_DIR / "FanDuel-NFL-2026 MDT-09 MDT-13 MDT-133104-players-list.csv"),
    },
    "early_week1": {
        "id": "early_week1",
        "name": "Week 1 Early-Only Archive (8 Games)",
        "games_count": 8,
        "platform": "FanDuel ($60k Cap)",
        "is_showdown": False,
        "default_csv": str(DATA_DIR / "earlyonlysalariesandrosters.csv") if (DATA_DIR / "earlyonlysalariesandrosters.csv").exists() else str(PROJECT_ROOT / "earlyonlysalariesandrosters.csv"),
    },
}


def _resolve_csv_path(slate_id: str) -> str:
    sid = slate_id.lower().strip()
    if sid == "uploaded":
        uploaded_path = DATA_DIR / "uploaded_fanduel.csv"
        if uploaded_path.exists():
            return str(uploaded_path)
        raise HTTPException(status_code=404, detail="No uploaded FanDuel CSV found. Please upload one first.")

    # Check for TNF showdown variants
    if sid in ("showdown_tnf", "det_buf", "tnf", "showdown"):
        tnf_path = DATA_DIR / "detvsbuffalosinglegameslaterostersnsalaries.csv"
        if tnf_path.exists():
            return str(tnf_path)

    # Week 2 Main Slate checks
    if sid in ("main", "week2", "week2_main", "main_week2"):
        week2_main = DATA_DIR / "9-20-26-main-slate-rosters-salaries-fd-week2.csv"
        if week2_main.exists():
            return str(week2_main)

    # Week 1 Archives checks
    if sid in ("main_week1", "week1", "week1_main"):
        w1_path = DATA_DIR / "mainslate9-13-2026.csv"
        if w1_path.exists():
            return str(w1_path)

    if sid in ("early", "early_week1"):
        root_early = PROJECT_ROOT / "earlyonlysalariesandrosters.csv"
        if root_early.exists():
            return str(root_early)
        data_early = DATA_DIR / "earlyonlysalariesandrosters.csv"
        if data_early.exists():
            return str(data_early)

    slate_info = SLATES_MAP.get(sid)
    if slate_info and os.path.exists(slate_info["default_csv"]):
        return slate_info["default_csv"]

    # Fallback to latest fanduel CSV
    latest = dfs_loader.find_latest_fanduel_csv()
    if latest and os.path.exists(latest):
        return latest

    raise HTTPException(status_code=404, detail=f"No CSV data found for slate '{slate_id}'.")


class DFSUploadSlateRequest(BaseModel):
    filename: str = Field(default="fanduel_salaries.csv", description="Name of the uploaded CSV file")
    csv_text: str = Field(description="Raw CSV contents from FanDuel export")


class DFSOptimizeRequest(BaseModel):
    slate_id: str = Field(default="main", description="Slate ID: 'main', 'early', or 'uploaded'")
    mode: str = Field(default="SINGLE_ENTRY_GPP", description="'SINGLE_ENTRY_GPP' or 'CASH'")
    num_lineups: int = Field(default=1, ge=1, le=20, description="Number of unique lineups to generate (1-20)")
    randomness: float = Field(default=0.0, ge=0.0, le=0.5, description="Projection variance factor for portfolio diversification")
    projection_source: str = Field(default="MODEL", description="Projection source: MODEL, CONSENSUS, FANTASYPROS, SLEEPER, ESPN")
    custom_projections: dict[str, float] = Field(default_factory=dict, description="Custom projection overrides (player name or ID to points)")
    stack_qb: str | None = Field(default=None, description="Optional quarterback to stack")
    stack_team: str | None = Field(default=None, description="Team abbreviation for primary stack")
    stack_opp: str | None = Field(default=None, description="Opposing team abbreviation for bring-back")
    lock_players: list[str] = Field(default_factory=list, description="List of player names or IDs to force into roster")
    exclude_players: list[str] = Field(default_factory=list, description="List of player names or IDs to exclude")
    min_salary: int = Field(default=58000, ge=50000, le=60000)
    max_salary: int = Field(default=60000, ge=50000, le=60000)


class DFSExportRequest(BaseModel):
    lineups: list[dict[str, Any]] = Field(description="List of solved lineup dictionaries")


@router.post("/upload-slate")
async def upload_slate(payload: DFSUploadSlateRequest) -> dict[str, Any]:
    """Ingests, parses, and enriches a user-uploaded FanDuel CSV file."""
    if not payload.csv_text or not payload.csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV file content is empty.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target_path = DATA_DIR / "uploaded_fanduel.csv"

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(payload.csv_text)
    except Exception as e:
        logger.error(f"Failed to save uploaded CSV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded CSV: {e}")

    # Verify and enrich via loader
    try:
        enriched_df = await dfs_loader.load_slate(csv_path=str(target_path))
        # Clear engine cached slate so fresh data is loaded
        dfs_engine.clear_cache()
    except Exception as e:
        logger.error(f"Failed to parse and enrich uploaded CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid FanDuel CSV format: {e}")

    teams = sorted(enriched_df["team"].unique().tolist()) if "team" in enriched_df.columns else []
    games = sorted(enriched_df["game"].unique().tolist()) if "game" in enriched_df.columns else []
    salary_min = int(enriched_df["salary"].min()) if "salary" in enriched_df.columns and not enriched_df.empty else 0
    salary_max = int(enriched_df["salary"].max()) if "salary" in enriched_df.columns and not enriched_df.empty else 0

    top_stars = []
    if not enriched_df.empty:
        top_df = enriched_df.sort_values(by="salary", ascending=False).head(5)
        for _, r in top_df.iterrows():
            top_stars.append({
                "name": r.get("name"),
                "position": r.get("position"),
                "team": r.get("team"),
                "salary": int(r.get("salary", 0)),
                "proj": float(r.get("proj", 0.0)),
            })

    is_showdown = (
        len(games) == 1
        or "MVP 1.5x Salary" in enriched_df.columns
        or "MVP" in str(enriched_df.columns)
    )
    platform = "FanDuel Showdown (1.5x MVP + 5 FLEX)" if is_showdown else "FanDuel ($60k Cap)"

    SLATES_MAP["uploaded"] = {
        "id": "uploaded",
        "name": f"Uploaded: {payload.filename}",
        "games_count": len(games),
        "platform": platform,
        "is_showdown": is_showdown,
        "default_csv": str(target_path),
    }

    return {
        "success": True,
        "slate_id": "uploaded",
        "filename": payload.filename,
        "total_players": len(enriched_df),
        "teams": teams,
        "games_count": len(games),
        "is_showdown": is_showdown,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "top_stars": top_stars,
    }


@router.post("/export-lineups")
async def export_lineups(payload: DFSExportRequest) -> dict[str, Any]:
    """Generates FanDuel CSV upload formatted file content from solved lineups."""
    if not payload.lineups:
        raise HTTPException(status_code=400, detail="No lineups provided for export.")

    csv_text = dfs_optimizer.format_fanduel_csv_export(payload.lineups)
    return {
        "filename": "fanduel_lineup_import.csv",
        "csv_content": csv_text,
        "lineup_count": len(payload.lineups),
    }


@router.get("/slates")
async def get_available_slates() -> list[dict[str, Any]]:
    """Returns available DFS slates with file status, game counts, and modification times."""
    available = []
    for sid, info in SLATES_MAP.items():
        exists = os.path.exists(info["default_csv"])
        last_modified = None
        if exists:
            try:
                mtime = os.path.getmtime(info["default_csv"])
                last_modified = datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %I:%M %p")
            except OSError:
                pass
        available.append({
            "id": info["id"],
            "name": info["name"],
            "games_count": info["games_count"],
            "platform": info["platform"],
            "is_showdown": info.get("is_showdown", False),
            "is_available": exists,
            "last_modified": last_modified,
        })
    return available


@router.get("/slate-data")
async def get_slate_data(
    slate_id: str = Query(default="main"),
    projection_source: str = Query(default="MODEL", description="Projection source: MODEL, CONSENSUS, FANTASYPROS, SLEEPER, ESPN"),
    force_reload: bool = Query(default=False, description="Force re-reading CSV from disk"),
) -> dict[str, Any]:
    """Returns enriched player pool, top game stacks, chalk radar, and tournament leverage targets."""
    csv_path = _resolve_csv_path(slate_id)
    source_str = projection_source if isinstance(projection_source, str) else "MODEL"
    try:
        slate_df = await dfs_engine.get_slate(csv_path=csv_path, projection_source=source_str, force_reload=force_reload)
    except Exception as e:
        logger.error(f"Failed to load slate data for {slate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load slate: {e}")

    last_modified = None
    if csv_path and os.path.exists(csv_path):
        try:
            mtime = os.path.getmtime(csv_path)
            last_modified = datetime.datetime.fromtimestamp(mtime).strftime("%b %d, %I:%M %p")
        except OSError:
            pass

    slate_info = SLATES_MAP.get(slate_id.lower(), {})
    is_showdown = (
        slate_info.get("is_showdown", False)
        or slate_id.lower() in ("showdown_tnf", "det_buf", "tnf", "showdown")
        or (slate_df is not None and "game" in slate_df.columns and len(slate_df["game"].dropna().unique()) == 1)
        or (slate_df is not None and "MVP 1.5x Salary" in slate_df.columns)
    )

    import json

    def _to_clean_records(df: Any) -> list[dict[str, Any]]:
        if df is None or df.empty:
            return []
        return json.loads(df.to_json(orient="records"))

    # Top Game Stacks
    top_stacks = dfs_analyzer.get_top_game_stacks(slate_df, top_n=5)

    # Top Leverage Plays
    top_leverage_df = dfs_analyzer.get_top_leverage_plays(slate_df, top_n=12)
    leverage_plays = _to_clean_records(top_leverage_df[[
        "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "proj_ownership", "leverage_score", "ownership_tier"
    ]]) if not top_leverage_df.empty else []

    # Top Chalk Plays
    top_chalk_df = dfs_analyzer.get_top_ownership_plays(slate_df, top_n=12)
    chalk_plays = _to_clean_records(top_chalk_df[[
        "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "proj_ownership", "ownership_tier"
    ]]) if not top_chalk_df.empty else []

    # Player pool catalog (sorted by salary desc)
    clean_pool = slate_df[
        ~slate_df["injury"].isin(["IR", "O", "OUT"])
        & (slate_df["proj"] >= 1.0)
    ].sort_values(by="salary", ascending=False)

    desired_cols = [
        "player_id", "name", "position", "team", "opponent", "salary", "proj", "ceiling_proj", "floor_proj",
        "team_implied", "opp_soft_rank", "opp_tier", "opp_tier_label", "opp_fd_fpa", "value_ratio", "proj_ownership", "ownership_tier", "leverage_score",
        "xfp", "fpoe", "tprr_vs_zone", "inside_5_carry_share", "scramble_rate_pressured", "p2s_rate", "scheme_note",
        "separation_score", "first_read_pct", "regression_index"
    ]
    available_cols = [col for col in desired_cols if col in clean_pool.columns]
    player_items = _to_clean_records(clean_pool[available_cols])

    raw_resp = {
        "slate_id": slate_id,
        "is_showdown": is_showdown,
        "last_modified": last_modified,
        "projection_source": source_str.upper(),
        "total_players": len(player_items),
        "top_stacks": top_stacks,
        "leverage_plays": leverage_plays,
        "chalk_plays": chalk_plays,
        "players": player_items,
    }

    return json.loads(json.dumps(raw_resp, default=_np_default))


@router.post("/optimize")
async def optimize_dfs_lineup(payload: DFSOptimizeRequest) -> dict[str, Any]:
    """Solves globally optimal FanDuel lineup(s) under linear constraints and performs live forensic audit.
    Dynamically routes to 6-slot Showdown solver (1 MVP + 5 FLEX) or 9-slot Classic solver based on slate type."""
    csv_path = _resolve_csv_path(payload.slate_id)
    try:
        if payload.custom_projections:
            slate_df = await dfs_loader.load_slate(
                csv_path=csv_path,
                custom_projections=payload.custom_projections,
                projection_source=payload.projection_source,
            )
        else:
            slate_df = await dfs_engine.get_slate(
                csv_path=csv_path,
                projection_source=payload.projection_source,
            )
    except Exception as e:
        logger.error(f"Failed to load slate for optimizer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load slate: {e}")

    slate_info = SLATES_MAP.get(payload.slate_id.lower(), {})
    is_showdown = (
        slate_info.get("is_showdown", False)
        or payload.slate_id.lower() in ("showdown_tnf", "det_buf", "tnf", "showdown")
        or (slate_df is not None and "game" in slate_df.columns and len(slate_df["game"].dropna().unique()) == 1)
        or (slate_df is not None and "MVP 1.5x Salary" in slate_df.columns)
    )

    # -------------------------------------------------------------
    # 1. SHOWDOWN / SINGLE GAME SOLVER (1 MVP @ 1.5x + 5 AnyFLEX)
    # -------------------------------------------------------------
    if is_showdown:
        solver = FanDuelShowdownOptimizer(
            salary_cap=60000,
            max_salary=payload.max_salary or 59800,
            min_salary=payload.min_salary or 57000,
        )

        lock_mvp = None
        regular_locks = []
        for lp in (payload.lock_players or []):
            if "mvp" in lp.lower() or "(1.5x)" in lp.lower():
                lock_mvp = lp.split(" (")[0].replace("MVP:", "").strip()
            else:
                regular_locks.append(lp)

        mode_str = "GPP" if "GPP" in (payload.mode or "GPP").upper() else "CASH"

        if payload.num_lineups > 1:
            all_scripts = solver.generate_all_scripts(
                df_slate=slate_df,
                mode=mode_str,
                lock_mvp=lock_mvp,
                lock_players=regular_locks if regular_locks else None,
                exclude_players=payload.exclude_players if payload.exclude_players else None,
            )
            valid_lineups = [l for l in all_scripts.values() if l is not None]
            if not valid_lineups:
                # Fallback to pure solve
                sol = solver.solve(
                    df_slate=slate_df,
                    mode=mode_str,
                    lock_mvp=lock_mvp,
                    lock_players=regular_locks if regular_locks else None,
                    exclude_players=payload.exclude_players if payload.exclude_players else None,
                )
                if sol:
                    valid_lineups = [sol]

            if not valid_lineups:
                raise HTTPException(
                    status_code=400,
                    detail="Unable to find feasible 6-slot FanDuel Showdown lineup under current constraints.",
                )

            primary_lineup = valid_lineups[0]
            audit = await dfs_engine.audit_roster(primary_lineup["roster"])
            for l in valid_lineups:
                l["slate_id"] = payload.slate_id
                l["is_showdown"] = True
                l["audit"] = audit
                l["total_proj"] = l.get("total_projected_pts", 0.0)
                l["total_ceiling"] = l.get("total_ceiling_pts", 0.0)

            exposure = dfs_optimizer.calculate_portfolio_exposure(valid_lineups[: payload.num_lineups])
            resp = dict(primary_lineup)
            resp["lineups"] = valid_lineups[: payload.num_lineups]
            resp["exposure"] = exposure
            resp["is_showdown"] = True
            resp["projection_source"] = (payload.projection_source or "MODEL").upper()
            return json.loads(json.dumps(resp, default=_np_default))

        sol = solver.solve(
            df_slate=slate_df,
            mode=mode_str,
            lock_mvp=lock_mvp,
            lock_players=regular_locks if regular_locks else None,
            exclude_players=payload.exclude_players if payload.exclude_players else None,
        )
        if not sol:
            raise HTTPException(
                status_code=400,
                detail="Unable to find feasible 6-slot FanDuel Showdown lineup under current constraints. Try relaxing salary bounds or removing player locks.",
            )

        audit = await dfs_engine.audit_roster(sol["roster"])
        sol["audit"] = audit
        sol["slate_id"] = payload.slate_id
        sol["is_showdown"] = True
        sol["total_proj"] = sol.get("total_projected_pts", 0.0)
        sol["total_ceiling"] = sol.get("total_ceiling_pts", 0.0)
        sol["projection_source"] = (payload.projection_source or "MODEL").upper()
        sol_copy = dict(sol)
        sol["lineups"] = [sol_copy]
        sol["exposure"] = dfs_optimizer.calculate_portfolio_exposure([sol_copy])
        return json.loads(json.dumps(sol, default=_np_default))

    # -------------------------------------------------------------
    # 2. CLASSIC MAIN / EARLY SLATE SOLVER (9 SLOTS)
    # -------------------------------------------------------------
    # If single-entry tournament without explicit stack, identify natural top game stack
    stack_qb = payload.stack_qb
    stack_team = payload.stack_team
    stack_opp = payload.stack_opp

    if payload.mode == "SINGLE_ENTRY_GPP" and not stack_qb:
        stacks = dfs_analyzer.get_top_game_stacks(slate_df, top_n=1)
        if stacks:
            top_s = stacks[0]
            stack_qb = top_s["qb"].split(" (")[0]
            qb_row = slate_df[slate_df["name"] == stack_qb]
            if not qb_row.empty:
                stack_team = qb_row.iloc[0]["team"]
                stack_opp = qb_row.iloc[0]["opponent"]

    if payload.num_lineups > 1:
        lineups = dfs_optimizer.optimize_multi(
            df_slate=slate_df,
            num_lineups=payload.num_lineups,
            randomness=payload.randomness,
            mode=payload.mode,
            stack_qb=stack_qb,
            stack_team=stack_team,
            stack_opp=stack_opp,
            lock_players=payload.lock_players if payload.lock_players else None,
            exclude_players=payload.exclude_players if payload.exclude_players else None,
            min_salary=payload.min_salary,
            max_salary=payload.max_salary,
        )
        if not lineups:
            raise HTTPException(
                status_code=400,
                detail="Unable to find feasible DFS lineup under current constraints. Try removing locks or relaxing salary bounds.",
            )
        primary_lineup = lineups[0]
        audit = await dfs_engine.audit_roster(primary_lineup["roster"])
        for l in lineups:
            l["slate_id"] = payload.slate_id
            l["is_showdown"] = False
            l["audit"] = audit
            l["active_stack"] = {
                "qb": stack_qb,
                "team": stack_team,
                "opponent": stack_opp,
            } if stack_qb else None

        exposure = dfs_optimizer.calculate_portfolio_exposure(lineups)
        resp = dict(primary_lineup)
        resp["lineups"] = lineups
        resp["exposure"] = exposure
        resp["is_showdown"] = False
        resp["projection_source"] = (payload.projection_source or "MODEL").upper()
        return json.loads(json.dumps(resp, default=_np_default))

    lineup = dfs_optimizer.optimize(
        df_slate=slate_df,
        mode=payload.mode,
        stack_qb=stack_qb,
        stack_team=stack_team,
        stack_opp=stack_opp,
        lock_players=payload.lock_players if payload.lock_players else None,
        exclude_players=payload.exclude_players if payload.exclude_players else None,
        min_salary=payload.min_salary,
        max_salary=payload.max_salary,
    )

    if not lineup:
        raise HTTPException(
            status_code=400,
            detail="Unable to find feasible DFS lineup under current constraints. Try removing locks or relaxing salary bounds.",
        )

    # Perform forensic live audit (weather + injuries)
    audit = await dfs_engine.audit_roster(lineup["roster"])
    lineup["audit"] = audit
    lineup["slate_id"] = payload.slate_id
    lineup["projection_source"] = (payload.projection_source or "MODEL").upper()
    lineup["active_stack"] = {
        "qb": stack_qb,
        "team": stack_team,
        "opponent": stack_opp,
    } if stack_qb else None
    lineup_copy = dict(lineup)
    lineup["lineups"] = [lineup_copy]
    lineup["exposure"] = dfs_optimizer.calculate_portfolio_exposure([lineup_copy])

    return json.loads(json.dumps(lineup, default=_np_default))
