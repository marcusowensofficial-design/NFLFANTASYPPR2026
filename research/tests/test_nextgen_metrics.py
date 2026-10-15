"""Comprehensive Unit and Integration Test Suite for Positional Next-Gen Metrics.

Tests:
1. Expected Fantasy Points (xFP) and FPOE calculation accuracy.
2. Defensive Coverage Shell matching (MOFO vs MOFC, Blitz 0).
3. QB Pressure Redistribution (scramble rate % and checkdown rate %).
4. Goal-Line Package Distribution and TD equity.
5. End-to-end integration into QuantProjectionEngine and DFSSlateLoader.
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.recommendation.nextgen_advanced_metrics import (
    ExpectedFantasyPointsCalculator,
    CoverageShellMatcher,
    QBPressureRedistributor,
    GoalLinePackageEquity,
    XFPCalculationResult,
)
from src.services.recommendation.projection_engine import (
    quant_projection_engine,
    get_player_nextgen_metrics,
    get_team_coverage_metrics,
    get_team_coaching_forensics,
)
from src.dfs.loader import dfs_loader
from src.db.models import PlayerModel


class TestNextGenAdvancedMetrics(unittest.TestCase):

    def test_xfp_calculator_wr(self):
        """Verify xFP calculation for wide receivers with deep vs intermediate targets."""
        res = ExpectedFantasyPointsCalculator.calculate_player_xfp(
            targets=10.0,
            adot=12.5,
            endzone_targets=1.0,
            realized_ppr=18.5,
            realized_half_ppr=13.5,
            pos="WR",
        )
        self.assertIsInstance(res, XFPCalculationResult)
        self.assertGreater(res.xfp_ppr, 14.0)
        self.assertGreater(res.xfp_half_ppr, 10.0)
        self.assertEqual(round(res.realized_half_ppr - res.xfp_half_ppr, 2), res.fpoe_half_ppr)

    def test_xfp_calculator_rb(self):
        """Verify xFP calculation for running backs separating carries by distance to goal line."""
        res = ExpectedFantasyPointsCalculator.calculate_player_xfp(
            targets=5.0,
            adot=1.2,
            endzone_targets=0.0,
            carries_inside_5=2.0,
            carries_6_to_10=3.0,
            carries_between_20s=12.0,
            realized_ppr=20.5,
            realized_half_ppr=18.0,
            pos="RB",
        )
        self.assertGreater(res.xfp_half_ppr, 14.0)
        self.assertIn(res.opportunity_tier, ("HIGH_VOLUME_STARTER", "ELITE_BELLCOW_ALPHA"))

    def test_coverage_shell_matcher_mofo(self):
        """Verify slot WR / TE receives boost against MOFO (two-high) defense like Buffalo."""
        mult, note = CoverageShellMatcher.calculate_scheme_multiplier(
            pos="WR",
            slot_rate_pct=52.0,
            tprr_vs_zone=0.30,
            tprr_vs_man=0.24,
            opp_mofo_pct=61.8,
            opp_mofc_pct=38.1,
            opp_blitz_rate_pct=10.0,
        )
        self.assertGreater(mult, 1.05)
        self.assertIn("MOFO", note)

    def test_coverage_shell_matcher_boundary_cap(self):
        """Verify boundary WR is penalized/capped against heavy MOFO two-high safety brackets."""
        mult, note = CoverageShellMatcher.calculate_scheme_multiplier(
            pos="WR",
            slot_rate_pct=15.0,
            tprr_vs_zone=0.16,
            tprr_vs_man=0.25,
            opp_mofo_pct=61.8,
            opp_mofc_pct=38.1,
            opp_blitz_rate_pct=10.0,
        )
        self.assertLess(mult, 1.0)
        self.assertIn("Two-high MOFO shell", note)

    def test_qb_pressure_redistribution(self):
        """Verify dual-threat QB gets rushing attempt surge when facing heavy pass rush."""
        redist = QBPressureRedistributor.calculate_redistribution(
            is_dual_threat=True,
            scramble_rate_pressured=18.5,
            checkdown_rate_pressured=11.2,
            p2s_rate=12.5,
            opp_pressure_pct=36.5,
        )
        self.assertGreaterEqual(redist["qb_rush_att_boost"], 2.0)

    def test_goal_line_package_equity(self):
        """Verify 12-personnel and Jumbo boost RB monopoly and grant TE2 end-zone equity."""
        equity = GoalLinePackageEquity.calculate_td_equity(
            inside_5_carry_share=0.65,
            gl_11_personnel_pct=40.0,
            gl_12_personnel_pct=35.0,
            gl_jumbo_pct=25.0,
            expected_team_tds=3.2,
        )
        self.assertGreater(equity["rb_rush_td_expectancy"], 1.0)
        self.assertGreater(equity["te2_endzone_td_expectancy"], 0.20)

    def test_projection_engine_nextgen_integration(self):
        """Verify projection engine returns xfp, fpoe, and coverage notes on live player."""
        dummy_player = PlayerModel(
            id=1001,
            full_name="Amon-Ra St. Brown",
            position="WR",
            pro_team="DET",
            projected_points=16.0,
        )
        res = quant_projection_engine.calculate_player_projection(
            dummy_player,
            scoring_format="HALF_PPR",
            projection_source="MODEL",
        )
        self.assertGreater(res.projected_points, 10.0)
        self.assertGreater(res.xfp, 8.0)
        self.assertIsNotNone(res.fpoe)
        self.assertGreater(res.tprr_vs_zone, 0.20)

    def test_dfs_loader_enrichment(self):
        """Verify DFS loader enriches slate DataFrame with all Next-Gen fields."""
        csv_path = "data/detvsbuffalosinglegameslaterostersnsalaries.csv"
        if not os.path.exists(csv_path):
            self.skipTest(f"{csv_path} not found")

        df = asyncio.run(dfs_loader.load_slate(csv_path))
        expected_cols = [
            "xfp",
            "fpoe",
            "tprr_vs_zone",
            "inside_5_carry_share",
            "scramble_rate_pressured",
            "p2s_rate",
            "scheme_note",
        ]
        for col in expected_cols:
            self.assertIn(col, df.columns, f"Expected column {col} missing from enriched DataFrame")

        # Check Josh Allen has scramble rate
        josh = df[df["name"].str.contains("Josh Allen", case=False, na=False)]
        if not josh.empty:
            self.assertGreater(float(josh.iloc[0]["scramble_rate_pressured"]), 15.0)

        # Check Gibbs has inside-5 share
        gibbs = df[df["name"].str.contains("Jahmyr Gibbs", case=False, na=False)]
        if not gibbs.empty:
            self.assertGreater(float(gibbs.iloc[0]["inside_5_carry_share"]), 0.50)


if __name__ == "__main__":
    unittest.main()
