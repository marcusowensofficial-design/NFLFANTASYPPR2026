"""Tests for Vegas Sportsbook Player Proposition Markets & Boris Chen GMM Tier Integration."""

import pytest
from src.adapters.betting.props_client import (
    VegasPropsClient,
    american_odds_to_prob,
    prob_to_american_odds,
    vegas_props_client,
)
from src.adapters.borischen.client import (
    BorisChenClient,
    BorisChenTierItem,
    boris_chen_client,
)
from src.db.models import PlayerModel
from src.services.recommendation.scoring_engine import scoring_engine


def test_american_odds_conversion():
    """Verify American moneyline conversion to implied probability and vice versa."""
    # Even money
    assert american_odds_to_prob(100) == 0.50
    assert american_odds_to_prob(-100) == 0.50
    # Heavy favorite
    assert american_odds_to_prob(-200) == pytest.approx(0.667, abs=0.01)
    # Underdog
    assert american_odds_to_prob(150) == 0.40

    # Prob back to odds
    assert prob_to_american_odds(0.50) == -100
    assert prob_to_american_odds(0.60) < 0
    assert prob_to_american_odds(0.40) > 0


@pytest.mark.asyncio
async def test_vegas_props_synthesis_and_implied_ppr():
    """Verify Vegas player props synthesis and market-implied PPR points."""
    client = VegasPropsClient()

    # WR synthesis
    wr_props = await client.get_player_props(
        player_id=101,
        player_name="Justin Jefferson",
        position="WR",
        team="MIN",
        opponent="GB",
        week=1,
        implied_team_total=24.5,
        spread=-2.5,
        over_under=47.5,
        projected_points=18.5,
    )
    assert wr_props.player_name == "Justin Jefferson"
    assert wr_props.position == "WR"
    assert wr_props.receptions_ou is not None
    assert wr_props.receptions_ou >= 5.0
    assert wr_props.rec_yards_ou is not None
    assert wr_props.rec_yards_ou >= 60.0
    assert wr_props.anytime_td_prob > 0.35
    assert wr_props.implied_ppr_points > 12.0
    assert len(wr_props.sharp_notes) > 0
    assert wr_props.vegas_grade in ("VERY_ELITE", "ELITE")
    assert wr_props.vegas_grade_label in ("🔥 VERY ELITE", "✨ ELITE")
    assert wr_props.vegas_takeaway != ""

    # RB synthesis
    rb_props = await client.get_player_props(
        player_id=102,
        player_name="Christian McCaffrey",
        position="RB",
        team="SF",
        opponent="LAR",
        week=1,
        implied_team_total=27.0,
        spread=-6.5,
        over_under=48.0,
        projected_points=21.0,
    )
    assert rb_props.position == "RB"
    assert rb_props.rush_yards_ou is not None
    assert rb_props.rush_yards_ou >= 65.0
    assert rb_props.rush_att_ou is not None
    assert rb_props.anytime_td_prob >= 0.50
    assert rb_props.implied_ppr_points >= 15.0
    assert rb_props.vegas_grade == "VERY_ELITE"
    assert rb_props.vegas_grade_label == "🔥 VERY ELITE"


@pytest.mark.asyncio
async def test_vegas_grade_buckets_across_positions():
    """Verify position-specific Vegas grade calibration across QB, RB, WR, TE, and fades."""
    client = VegasPropsClient()

    # 1. Elite QB
    qb_props = await client.get_player_props(
        player_id=201,
        player_name="Josh Allen",
        position="QB",
        team="BUF",
        opponent="MIA",
        week=1,
        implied_team_total=26.5,
        spread=-4.5,
        over_under=49.5,
        projected_points=23.0,
    )
    assert qb_props.vegas_grade in ("VERY_ELITE", "ELITE")
    assert "Pass Yds O/U" in qb_props.vegas_takeaway or "Pass Yds" in qb_props.vegas_takeaway

    # 2. Elite TE
    te_props = await client.get_player_props(
        player_id=202,
        player_name="Trey McBride",
        position="TE",
        team="ARI",
        opponent="LAR",
        week=1,
        implied_team_total=24.0,
        spread=-1.5,
        over_under=48.5,
        projected_points=14.5,
    )
    assert te_props.vegas_grade in ("VERY_ELITE", "ELITE")
    assert te_props.receptions_ou is not None
    assert te_props.receptions_ou >= 4.5

    # 3. Fade / low-volume RB
    fade_props = await client.get_player_props(
        player_id=203,
        player_name="Backup RB",
        position="RB",
        team="CAR",
        opponent="NO",
        week=1,
        implied_team_total=16.0,
        spread=7.5,
        over_under=39.5,
        projected_points=3.5,
    )
    assert fade_props.vegas_grade in ("FADE", "VERY_BAD")
    assert fade_props.vegas_grade_color in ("amber", "rose")


def test_boris_chen_text_parsing():
    """Verify Boris Chen text parser correctly extracts tiers and player names."""
    client = BorisChenClient()
    sample_text = """
    Tier 1: CeeDee Lamb (1), Justin Jefferson (2), Tyreek Hill (3)
    Tier 2: Amon-Ra St. Brown (4), Ja'Marr Chase (5)
    Tier 3: Nico Collins (6), Garrett Wilson (7)
    """
    tiers = client._parse_boris_chen_text(sample_text, "PPR-WR")
    assert len(tiers) == 7
    assert "ceedee lamb" in tiers
    assert tiers["ceedee lamb"].tier == 1
    assert tiers["ceedee lamb"].rank == 1
    assert "amonra st brown" in tiers
    assert tiers["amonra st brown"].tier == 2


def test_boris_chen_algorithmic_clustering():
    """Verify algorithmic fallback clustering when raw web text is unavailable."""
    client = BorisChenClient()
    players_data = [
        {"name": "Stud A", "rank": 1, "ecr": 1.1, "ecr_std": 0.4},
        {"name": "Stud B", "rank": 2, "ecr": 1.9, "ecr_std": 0.5},
        {"name": "Starter C", "rank": 3, "ecr": 5.8, "ecr_std": 1.2},  # Big gap
        {"name": "Starter D", "rank": 4, "ecr": 6.2, "ecr_std": 1.1},
    ]
    clusters = client.cluster_players_into_tiers(players_data)
    assert len(clusters) == 4
    assert clusters["stud a"].tier == 1
    assert clusters["stud b"].tier == 1
    assert clusters["starter c"].tier == 2
    assert clusters["starter d"].tier == 2


def test_scoring_engine_populates_props_and_tiers():
    """Verify that StartSitScoringEngine populates props and tier fields into StartSitEvaluation."""
    player = PlayerModel(
        id=888,
        full_name="Amon-Ra St. Brown",
        position="WR",
        pro_team="DET",
        projected_points=17.8,
        fp_rank_ecr=4,
        fp_pos_rank="WR4",
        fp_tier=1,
        fp_rank_std=0.8,
    )
    eval_result = scoring_engine.evaluate_player(player, projection_source="MODEL")
    assert eval_result.player_id == 888
    # Props fields
    assert eval_result.props_receptions_ou is not None
    assert eval_result.props_receptions_ou >= 5.0
    assert eval_result.props_implied_ppr_pts is not None
    assert eval_result.props_implied_ppr_pts > 10.0
    assert eval_result.props_anytime_td_prob is not None
    # Boris Chen tier
    assert eval_result.boris_chen_tier == 1
    assert eval_result.boris_chen_tier_label == "Tier 1"

    # Verify reason bullets generated
    all_reasons = eval_result.reasons_positive + eval_result.reasons_negative
    assert any("[Vegas Props]" in r for r in all_reasons)
    assert any("[Boris Chen]" in r for r in all_reasons)


@pytest.mark.asyncio
async def test_api_analysis_props_and_tiers(client):
    """Verify that /api/analysis/player-props and /api/analysis/boris-chen-tiers return 200."""
    res_props = client.get("/api/analysis/player-props?week=1")
    assert res_props.status_code == 200
    props_list = res_props.json()
    assert isinstance(props_list, list)

    res_tiers = client.get("/api/analysis/boris-chen-tiers?week=1")
    assert res_tiers.status_code == 200
    tiers_dict = res_tiers.json()
    assert isinstance(tiers_dict, dict)
    assert "QB" in tiers_dict
    assert "PPR-WR" in tiers_dict
