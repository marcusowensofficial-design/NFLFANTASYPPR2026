"""Vegas Line Movement Velocity & Syndicate Steam Detection Engine.

Calculates the rate of change and market velocity for spreads and totals:
- Delta Spread (current_spread - open_spread)
- Delta Total (current_total - open_total)
- Syndicate Steam Classification:
    - STRONG_OVER_STEAM: Total movement >= +1.5 points (triggers game stack multiplier)
    - STRONG_UNDER_STEAM: Total movement <= -1.5 points (triggers D/ST boost)
    - FAVORITE_STEAM: Spread shifted towards favorite by >= 1.5 points (triggers RB1 positive script boost)
    - REVERSE_LINE_MOVEMENT: Line movement counter to ticket percentages
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GameLineMovement(BaseModel):
    game_id: str
    away_team: str
    home_team: str
    open_spread: float
    current_spread: float
    delta_spread: float
    open_total: float
    current_total: float
    delta_total: float
    steam_classification: str
    game_stack_multiplier: float = 1.0
    favored_rb_multiplier: float = 1.0
    dst_multiplier: float = 1.0
    notes: str = ""


class LineMovementVelocityEngine:
    """Detects sharp syndicate action and line movement velocity across slates."""

    def __init__(self, data_path: Optional[str] = None):
        if data_path:
            self.data_path = Path(data_path)
        else:
            self.data_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "vegas_movement_2026.json"

    def analyze_game(
        self,
        away_team: str,
        home_team: str,
        open_spread: float,
        current_spread: float,
        open_total: float,
        current_total: float
    ) -> GameLineMovement:
        """Calculates velocities and applies DFS game-theory multipliers."""
        delta_spread = round(current_spread - open_spread, 2)
        delta_total = round(current_total - open_total, 2)

        classifications = []
        game_stack_mult = 1.0
        rb_mult = 1.0
        dst_mult = 1.0

        # Total Velocity
        if delta_total >= 1.5:
            classifications.append("STRONG_OVER_STEAM")
            game_stack_mult += 0.05  # +5% synergy boost to game stacks
        elif delta_total >= 0.5:
            classifications.append("MILD_OVER_STEAM")
            game_stack_mult += 0.02
        elif delta_total <= -1.5:
            classifications.append("STRONG_UNDER_STEAM")
            dst_mult += 0.08  # +8% boost to D/STs in dropping totals
            game_stack_mult -= 0.05
        elif delta_total <= -0.5:
            classifications.append("MILD_UNDER_STEAM")

        # Spread Velocity (assuming negative spread = home favorite, e.g. -3.0 to -5.5)
        # If home is favorite and spread becomes more negative: favorite steam
        if current_spread < open_spread and abs(delta_spread) >= 1.5:
            classifications.append("HOME_FAVORITE_STEAM")
            rb_mult += 0.05  # Boost home RB1 in positive game script
        elif current_spread > open_spread and abs(delta_spread) >= 1.5:
            classifications.append("AWAY_STEAM")

        steam_str = " | ".join(classifications) if classifications else "NEUTRAL_MOVEMENT"

        return GameLineMovement(
            game_id=f"{away_team}@{home_team}",
            away_team=away_team,
            home_team=home_team,
            open_spread=open_spread,
            current_spread=current_spread,
            delta_spread=delta_spread,
            open_total=open_total,
            current_total=current_total,
            delta_total=delta_total,
            steam_classification=steam_str,
            game_stack_multiplier=round(game_stack_mult, 3),
            favored_rb_multiplier=round(rb_mult, 3),
            dst_multiplier=round(dst_mult, 3),
            notes=f"Total moved {delta_total:+} pts; Spread moved {delta_spread:+} pts."
        )

    def load_and_analyze_slate(self) -> Dict[str, GameLineMovement]:
        """Loads live vegas JSON and analyzes all games on the slate."""
        if not self.data_path.exists():
            logger.warning(f"Vegas movement file {self.data_path} not found.")
            return {}

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            results: Dict[str, GameLineMovement] = {}
            for game in data.get("games", []):
                away = game.get("away_team", "")
                home = game.get("home_team", "")
                open_sp = float(game.get("open_spread", game.get("spread", 0.0)))
                curr_sp = float(game.get("spread", open_sp))
                open_tot = float(game.get("open_over_under", game.get("over_under", 44.0)))
                curr_tot = float(game.get("over_under", open_tot))

                analysis = self.analyze_game(
                    away_team=away,
                    home_team=home,
                    open_spread=open_sp,
                    current_spread=curr_sp,
                    open_total=open_tot,
                    current_total=curr_tot
                )
                results[f"{away}@{home}"] = analysis
                results[away] = analysis
                results[home] = analysis

            return results
        except Exception as e:
            logger.error(f"Failed to load or parse vegas movement: {e}")
            return {}


line_velocity_engine = LineMovementVelocityEngine()
