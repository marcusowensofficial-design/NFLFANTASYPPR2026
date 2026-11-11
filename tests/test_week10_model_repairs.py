"""Regression tests for Week 10 projection, calibration, props, DvP, and backtesting repairs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from src.adapters.betting import props_client as props_mod
from src.adapters.betting.props_client import PlayerPropsData, VegasPropsClient
from src.adapters.nfl.dvp_client import DvPClient, DvPProfile
from src.adapters.nfl.schedule_client import NFLGame
from src.db.models import LeagueModel, PlayerModel, WeeklyProjectionHistoryModel
from src.services.backtesting.evaluator import BacktestingEvaluator
from src.services.recommendation.projection_engine import (
    QuantProjectionEngine,
    quant_projection_engine,
)
from src.services.recommendation.scoring_engine import StartSitScoringEngine


def _make_game(
    game_id: str,
    home: str,
    away: str,
    over_under: float = 45.0,
    spread: float = -2.5,
    home_imp: float = 23.75,
    away_imp: float = 21.25,
    is_dome: bool = True,
) -> NFLGame:
    return NFLGame(
        id=game_id,
        name=f"{away} @ {home}",
        date="2026-11-15T18:00:00Z",
        venue_name="Test Dome",
        is_dome=is_dome,
        home_team=home,
        away_team=away,
        over_under=over_under,
        spread=spread,
        home_implied_total=home_imp,
        away_implied_total=away_imp,
    )


def test_bye_week_zeroing_without_game_context():
    """BYE teams in Week 10 (CHI, DEN, PHI, TB) must zero out even when nfl_game is None."""
    for team in ("CHI", "DEN", "PHI", "TB"):
        p = PlayerModel(
            id=88001,
            full_name="Test Bye Player",
            position="WR",
            pro_team=team,
            projected_points=16.0,
            projected_points_fp=15.5,
            projected_points_espn=15.0,
            fp_pos_rank="WR12",
            fp_rank_ecr=24,
        )
        res_half = quant_projection_engine.calculate_player_projection(
            p,
            nfl_game=None,
            projection_source="ENSEMBLE",
            scoring_format="HALF_PPR",
            week=10,
        )
        assert res_half.projected_points == 0.0
        assert res_half.model_points == 0.0
        assert res_half.ensemble_half_ppr == 0.0
        assert res_half.model_provenance.get("reason") == "BYE week"

        scoring = StartSitScoringEngine()
        ev = scoring.evaluate_player(p, nfl_game=None, week=10)
        assert ev.projected_points == 0.0
        assert ev.start_score == 0.0


def test_backup_qb_gating_prevents_phantom_starter_baseline():
    """Deep backup QBs (ECR > 32, healthy starter, no high market prop) must not inherit ~18pt starter floor."""
    backup_qb = PlayerModel(
        id=88002,
        full_name="Test Backup Quarterback",
        position="QB",
        pro_team="IND",
        fp_pos_rank="QB55",
        fp_rank_ecr=220,
        projected_points_espn=0.0,
        projected_points_fp=0.0,
    )
    game = _make_game("2026_W10_TEN_IND", "IND", "TEN", over_under=44.5, spread=-2.5, home_imp=23.5, away_imp=21.0)
    res = quant_projection_engine.calculate_player_projection(
        backup_qb,
        nfl_game=game,
        projection_source="MODEL",
        scoring_format="HALF_PPR",
        week=10,
    )
    assert res.model_points <= 4.0, f"Backup QB inflated to {res.model_points}"


def test_model_source_independent_of_cached_projected_points_model():
    """Recalculating MODEL must never anchor back to player.projected_points_model."""
    base_kwargs = dict(
        id=88003,
        full_name="Test Independent Receiver",
        position="WR",
        pro_team="DAL",
        projected_points=14.0,
        projected_points_fp=14.5,
        projected_points_espn=14.2,
        projected_points_sleeper=14.8,
        projected_points_sleeper_half=12.4,
        fp_pos_rank="WR18",
        fp_rank_ecr=42,
    )
    game = _make_game("2026_W10_SF_DAL", "DAL", "SF", over_under=48.5, spread=-1.5, home_imp=25.0, away_imp=23.5)
    p_zero = PlayerModel(**base_kwargs, projected_points_model=0.0)
    p_stale = PlayerModel(**base_kwargs, projected_points_model=33.0)

    r_zero = quant_projection_engine.calculate_player_projection(
        p_zero, nfl_game=game, projection_source="MODEL", scoring_format="PPR", week=10
    )
    r_stale = quant_projection_engine.calculate_player_projection(
        p_stale, nfl_game=game, projection_source="MODEL", scoring_format="PPR", week=10
    )
    assert r_zero.model_points == r_stale.model_points


def test_stale_live_props_ignored_and_td_only_no_phantom_yards(tmp_path, monkeypatch):
    """player_props_live.json older than 6 days is invalidated, and TD-only props do not impute starter yards."""
    fake_pkg = tmp_path / "src" / "adapters" / "betting"
    fake_pkg.mkdir(parents=True)
    fake_file = fake_pkg / "props_client.py"
    fake_file.write_text("# test anchor", encoding="utf-8")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    (data_dir / "player_props_live.json").write_text(
        json.dumps(
            {
                "fetched_at": stale_ts,
                "players": {"stale player": {"pass_yds_ou": 280.5}},
            }
        ),
        encoding="utf-8",
    )

    orig_file = props_mod.__file__
    orig_cache = dict(props_mod._live_props_cache)
    try:
        monkeypatch.setattr(props_mod, "__file__", str(fake_file))
        props_mod._live_props_cache = {"mtime": 0, "players": {"residual": {}}}
        props_mod._load_live_props_cache()
        assert props_mod._live_props_cache["players"] == {}
    finally:
        monkeypatch.setattr(props_mod, "__file__", orig_file)
        props_mod._live_props_cache = orig_cache

    client = VegasPropsClient()
    td_only_props = PlayerPropsData(
        player_id=1,
        player_name="TD Only Player",
        position="WR",
        team="DAL",
        opponent="SF",
        anytime_td_prob=0.35,
        source="SPORTSBOOK_CONSENSUS",
    )
    client._calculate_implied_ppr(td_only_props)
    assert td_only_props.implied_ppr_points < 3.0, (
        f"Expected pure TD equity (<3.0), got {td_only_props.implied_ppr_points}"
    )


def test_dvp_alias_and_team_implied_total_direction():
    """WAS/WSH resolve identically, and high team_implied_total raises offense score."""
    client = DvPClient(
        profiles={
            "WSH": DvPProfile(
                pro_team="WSH",
                qb_rank=32,
                rb_rank=15,
                wr_rank=32,
                te_rank=32,
                overall_def_rank=31,
                points_allowed_per_game=27.2,
            )
        },
        auto_hydrate=False,
    )
    assert client._resolve_team("WAS") == "WSH"
    assert client.get_position_rank("WAS", "WR") == client.get_position_rank("WSH", "WR")
    hi_score, _ = client.calculate_matchup_score("WAS", "WR", team_implied_total=27.5)
    lo_score, _ = client.calculate_matchup_score("WAS", "WR", team_implied_total=17.5)
    assert hi_score > lo_score


def test_normalize_team_projections_conserves_excess_targets():
    """Team target totals above 1.05x pass_cap are scaled proportionally across catchers."""
    p1 = PlayerModel(id=1, full_name="WR Alpha", position="WR", pro_team="MIN")
    p2 = PlayerModel(id=2, full_name="WR Beta", position="WR", pro_team="MIN")
    game = _make_game("2026_W10_MIN_GB", "GB", "MIN", over_under=46.0, spread=-2.0, home_imp=24.0, away_imp=22.0)
    r1 = quant_projection_engine.calculate_player_projection(p1, nfl_game=game, scoring_format="HALF_PPR", week=10)
    r2 = quant_projection_engine.calculate_player_projection(p2, nfl_game=game, scoring_format="HALF_PPR", week=10)

    r1.team_pass_att = 32.0
    r2.team_pass_att = 32.0
    r1.itemized_stats.targets = 24.0
    r2.itemized_stats.targets = 20.0
    orig_sum_pts = r1.projected_points + r2.projected_points

    QuantProjectionEngine.normalize_team_projections([(p1, r1), (p2, r2)], scoring_format="HALF_PPR")
    assert r1.itemized_stats.targets + r2.itemized_stats.targets <= 32.0 * 1.03
    assert r1.projected_points + r2.projected_points < orig_sum_pts


def test_backtest_source_leaderboard_aggregation(client, db_session):
    """BacktestingEvaluator aggregates multi-week history and API report exposes source_leaderboard."""
    db_session.add(
        LeagueModel(
            id=1,
            name="Test League",
            season=2026,
            current_week=10,
            user_team_id=1,
            size=8,
        )
    )
    db_session.add_all(
        [
            WeeklyProjectionHistoryModel(
                player_id=10,
                player_name="Player A",
                position="WR",
                pro_team="DET",
                season=2026,
                week=8,
                scoring_format="HALF_PPR",
                model_pts=14.0,
                quant_pts=14.0,
                xgboost_pts=15.0,
                ensemble_pts=14.8,
                sleeper_pts=13.5,
                actual_pts=15.0,
                floor_10th=6.0,
                median_50th=13.0,
                ceiling_85th=22.0,
                ceiling_95th=30.0,
                is_bye=False,
            ),
            WeeklyProjectionHistoryModel(
                player_id=11,
                player_name="Player B",
                position="RB",
                pro_team="BUF",
                season=2026,
                week=9,
                scoring_format="HALF_PPR",
                model_pts=12.0,
                quant_pts=12.0,
                xgboost_pts=10.0,
                ensemble_pts=10.6,
                sleeper_pts=13.0,
                actual_pts=10.0,
                floor_10th=5.0,
                median_50th=9.5,
                ceiling_85th=16.0,
                ceiling_95th=22.0,
                is_bye=False,
            ),
        ]
    )
    db_session.commit()

    weeks, board = BacktestingEvaluator().build_source_leaderboard(
        db_session, season=2026, max_week=9, scoring_format="HALF_PPR"
    )
    assert weeks == [8, 9]
    assert len(board) >= 3
    ens = next(m for m in board if m.source == "ENSEMBLE")
    assert ens.weeks_evaluated == 2
    assert ens.sample_size == 2
    assert ens.mae < 1.0
    assert ens.coverage_10th_pct == 0.0

    resp = client.get("/api/backtest/report?team_id=1")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["evaluated_weeks"] == [8, 9]
    assert len(payload["source_leaderboard"]) >= 3
