"""Defense vs Position (DvP) rating and matchup grade calculator with non-linear scaling and role splits."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class DvPProfile:
    pro_team: str
    qb_rank: int
    rb_rank: int
    wr_rank: int
    te_rank: int
    overall_def_rank: int
    points_allowed_per_game: float
    rb_rec_rank: int = 16  # Rank vs pass-catching RBs (receptions/rec yards conceded)
    wr_slot_rank: int = 16  # Rank vs slot receivers
    dst_allowed_rank: int = 16  # Rank vs opposing D/ST (1 = stingiest offense/fewest fantasy pts allowed, 32 = most generous offense/turnovers & sacks)
    overall_off_rank: int = 16  # Overall offensive ranking (1 = best scoring/EPA offense, 32 = worst offense)


# Baseline 32 NFL Team Defensive & Offensive Profiles (1 = stingiest/toughest, 32 = most generous/softest)
# Calibrated using rolling defensive efficiency, pass/run EPA, fantasy points conceded, offensive sack/turnover rates, and scoring output
DEFAULT_DVP_PROFILES: dict[str, DvPProfile] = {
    "SF": DvPProfile("SF", qb_rank=6, rb_rank=4, wr_rank=7, te_rank=3, overall_def_rank=4, points_allowed_per_game=17.5, rb_rec_rank=18, wr_slot_rank=12, dst_allowed_rank=4, overall_off_rank=3),
    "BAL": DvPProfile("BAL", qb_rank=3, rb_rank=2, wr_rank=5, te_rank=2, overall_def_rank=2, points_allowed_per_game=16.8, rb_rec_rank=20, wr_slot_rank=10, dst_allowed_rank=2, overall_off_rank=2),
    "CLE": DvPProfile("CLE", qb_rank=2, rb_rank=6, wr_rank=2, te_rank=8, overall_def_rank=3, points_allowed_per_game=17.0, rb_rec_rank=17, wr_slot_rank=9, dst_allowed_rank=26, overall_off_rank=26),
    "NYJ": DvPProfile("NYJ", qb_rank=1, rb_rank=12, wr_rank=1, te_rank=5, overall_def_rank=5, points_allowed_per_game=18.2, rb_rec_rank=22, wr_slot_rank=15, dst_allowed_rank=22, overall_off_rank=22),
    "KC": DvPProfile("KC", qb_rank=4, rb_rank=10, wr_rank=4, te_rank=9, overall_def_rank=1, points_allowed_per_game=16.5, rb_rec_rank=14, wr_slot_rank=8, dst_allowed_rank=3, overall_off_rank=4),
    "PIT": DvPProfile("PIT", qb_rank=8, rb_rank=5, wr_rank=10, te_rank=12, overall_def_rank=7, points_allowed_per_game=18.5, rb_rec_rank=16, wr_slot_rank=14, dst_allowed_rank=23, overall_off_rank=24),
    "HOU": DvPProfile("HOU", qb_rank=10, rb_rank=7, wr_rank=9, te_rank=14, overall_def_rank=8, points_allowed_per_game=19.0, rb_rec_rank=15, wr_slot_rank=11, dst_allowed_rank=8, overall_off_rank=9),
    "DET": DvPProfile("DET", qb_rank=22, rb_rank=3, wr_rank=27, te_rank=11, overall_def_rank=12, points_allowed_per_game=20.5, rb_rec_rank=19, wr_slot_rank=24, dst_allowed_rank=1, overall_off_rank=1),
    "CHI": DvPProfile("CHI", qb_rank=11, rb_rank=8, wr_rank=8, te_rank=13, overall_def_rank=10, points_allowed_per_game=19.8, rb_rec_rank=12, wr_slot_rank=13, dst_allowed_rank=17, overall_off_rank=18),
    "BUF": DvPProfile("BUF", qb_rank=9, rb_rank=16, wr_rank=12, te_rank=6, overall_def_rank=9, points_allowed_per_game=19.5, rb_rec_rank=23, wr_slot_rank=16, dst_allowed_rank=5, overall_off_rank=5),
    "DAL": DvPProfile("DAL", qb_rank=5, rb_rank=19, wr_rank=3, te_rank=7, overall_def_rank=6, points_allowed_per_game=18.0, rb_rec_rank=21, wr_slot_rank=6, dst_allowed_rank=10, overall_off_rank=10),
    "MIN": DvPProfile("MIN", qb_rank=14, rb_rank=9, wr_rank=16, te_rank=10, overall_def_rank=11, points_allowed_per_game=20.0, rb_rec_rank=13, wr_slot_rank=19, dst_allowed_rank=19, overall_off_rank=15),
    "GB": DvPProfile("GB", qb_rank=13, rb_rank=18, wr_rank=14, te_rank=15, overall_def_rank=13, points_allowed_per_game=20.8, rb_rec_rank=11, wr_slot_rank=18, dst_allowed_rank=7, overall_off_rank=8),
    "MIA": DvPProfile("MIA", qb_rank=12, rb_rank=15, wr_rank=11, te_rank=18, overall_def_rank=14, points_allowed_per_game=21.0, rb_rec_rank=25, wr_slot_rank=17, dst_allowed_rank=11, overall_off_rank=11),
    "SEA": DvPProfile("SEA", qb_rank=18, rb_rank=21, wr_rank=15, te_rank=17, overall_def_rank=16, points_allowed_per_game=21.5, rb_rec_rank=18, wr_slot_rank=20, dst_allowed_rank=21, overall_off_rank=21),
    "PHI": DvPProfile("PHI", qb_rank=25, rb_rank=11, wr_rank=28, te_rank=19, overall_def_rank=18, points_allowed_per_game=22.5, rb_rec_rank=24, wr_slot_rank=26, dst_allowed_rank=6, overall_off_rank=6),
    "CIN": DvPProfile("CIN", qb_rank=20, rb_rank=23, wr_rank=18, te_rank=26, overall_def_rank=19, points_allowed_per_game=22.8, rb_rec_rank=26, wr_slot_rank=21, dst_allowed_rank=9, overall_off_rank=7),
    "TB": DvPProfile("TB", qb_rank=24, rb_rank=13, wr_rank=23, te_rank=24, overall_def_rank=17, points_allowed_per_game=22.0, rb_rec_rank=27, wr_slot_rank=23, dst_allowed_rank=14, overall_off_rank=13),
    "DEN": DvPProfile("DEN", qb_rank=15, rb_rank=25, wr_rank=13, te_rank=22, overall_def_rank=15, points_allowed_per_game=21.2, rb_rec_rank=28, wr_slot_rank=22, dst_allowed_rank=27, overall_off_rank=27),
    "LAR": DvPProfile("LAR", qb_rank=19, rb_rank=17, wr_rank=20, te_rank=21, overall_def_rank=20, points_allowed_per_game=23.0, rb_rec_rank=16, wr_slot_rank=25, dst_allowed_rank=12, overall_off_rank=12),
    "NO": DvPProfile("NO", qb_rank=7, rb_rank=20, wr_rank=6, te_rank=4, overall_def_rank=21, points_allowed_per_game=23.2, rb_rec_rank=15, wr_slot_rank=7, dst_allowed_rank=25, overall_off_rank=25),
    "IND": DvPProfile("IND", qb_rank=21, rb_rank=26, wr_rank=19, te_rank=20, overall_def_rank=22, points_allowed_per_game=23.5, rb_rec_rank=29, wr_slot_rank=27, dst_allowed_rank=20, overall_off_rank=20),
    "JAX": DvPProfile("JAX", qb_rank=28, rb_rank=14, wr_rank=26, te_rank=25, overall_def_rank=23, points_allowed_per_game=24.0, rb_rec_rank=17, wr_slot_rank=28, dst_allowed_rank=18, overall_off_rank=19),
    "ATL": DvPProfile("ATL", qb_rank=16, rb_rank=22, wr_rank=17, te_rank=16, overall_def_rank=24, points_allowed_per_game=24.2, rb_rec_rank=18, wr_slot_rank=16, dst_allowed_rank=13, overall_off_rank=14),
    "TEN": DvPProfile("TEN", qb_rank=26, rb_rank=24, wr_rank=25, te_rank=23, overall_def_rank=25, points_allowed_per_game=24.5, rb_rec_rank=19, wr_slot_rank=29, dst_allowed_rank=29, overall_off_rank=29),
    "LAC": DvPProfile("LAC", qb_rank=17, rb_rank=27, wr_rank=22, te_rank=27, overall_def_rank=26, points_allowed_per_game=24.8, rb_rec_rank=22, wr_slot_rank=20, dst_allowed_rank=16, overall_off_rank=17),
    "LV": DvPProfile("LV", qb_rank=23, rb_rank=28, wr_rank=21, te_rank=28, overall_def_rank=27, points_allowed_per_game=25.0, rb_rec_rank=24, wr_slot_rank=26, dst_allowed_rank=28, overall_off_rank=28),
    "NE": DvPProfile("NE", qb_rank=27, rb_rank=29, wr_rank=24, te_rank=29, overall_def_rank=28, points_allowed_per_game=25.5, rb_rec_rank=25, wr_slot_rank=30, dst_allowed_rank=30, overall_off_rank=30),
    "NYG": DvPProfile("NYG", qb_rank=29, rb_rank=30, wr_rank=29, te_rank=30, overall_def_rank=29, points_allowed_per_game=26.0, rb_rec_rank=30, wr_slot_rank=31, dst_allowed_rank=31, overall_off_rank=31),
    "ARI": DvPProfile("ARI", qb_rank=30, rb_rank=31, wr_rank=30, te_rank=31, overall_def_rank=30, points_allowed_per_game=26.5, rb_rec_rank=31, wr_slot_rank=32, dst_allowed_rank=15, overall_off_rank=16),
    "WSH": DvPProfile("WSH", qb_rank=32, rb_rank=15, wr_rank=32, te_rank=32, overall_def_rank=31, points_allowed_per_game=27.2, rb_rec_rank=32, wr_slot_rank=28, dst_allowed_rank=24, overall_off_rank=23),
    "CAR": DvPProfile("CAR", qb_rank=31, rb_rank=32, wr_rank=31, te_rank=1, overall_def_rank=32, points_allowed_per_game=28.0, rb_rec_rank=28, wr_slot_rank=29, dst_allowed_rank=32, overall_off_rank=32),
}


class DvPClient:
    """Manages Defense vs Position (DvP) calculations and matchup scoring with role splits."""

    def __init__(self, profiles: dict[str, DvPProfile] | None = None):
        self.profiles = dict(profiles or DEFAULT_DVP_PROFILES)

    def update_team_profile(self, pro_team: str, **kwargs) -> None:
        """Dynamically update a team's defensive or offensive metrics from live 2026 data."""
        team = pro_team.upper().strip()
        if team in self.profiles:
            curr = self.profiles[team]
            for k, v in kwargs.items():
                if hasattr(curr, k):
                    setattr(curr, k, v)

    def get_position_rank(self, opponent_team: str, position: str) -> int:
        """Returns rank 1-32 (1 = toughest vs position, 32 = softest vs position)."""
        opp = opponent_team.upper().strip()
        profile = self.profiles.get(opp)
        if not profile:
            return 16  # Neutral middle rank fallback

        pos = position.upper().strip()
        if pos == "QB":
            return profile.qb_rank
        elif pos in ("RB", "FB"):
            return profile.rb_rank
        elif pos == "WR":
            return profile.wr_rank
        elif pos == "TE":
            return profile.te_rank
        elif pos in ("K", "PK"):
            return profile.overall_def_rank
        elif pos in ("D/ST", "DST"):
            # Against opposing offenses: rank of fantasy points allowed to D/ST (1=stingiest, 32=most generous/vulnerable)
            return profile.dst_allowed_rank
        return 16

    def get_overall_rank(self, opponent_team: str) -> int:
        """Returns overall defensive rank 1-32 (1 = best defense, 32 = worst defense)."""
        opp = opponent_team.upper().strip()
        profile = self.profiles.get(opp)
        return profile.overall_def_rank if profile else 16

    def get_overall_off_rank(self, opponent_team: str) -> int:
        """Returns overall offensive rank 1-32 (1 = best offense, 32 = worst offense)."""
        opp = opponent_team.upper().strip()
        profile = self.profiles.get(opp)
        return profile.overall_off_rank if profile else 16

    def get_matchup_stars(self, rank: int | None) -> int:
        """Converts a 1-32 DvP rank into FantasyPros 1-5 star matchup rating:
        Rank 1-6   -> 1 Star  (Worst / Stifling Matchup)
        Rank 7-12  -> 2 Stars (Tough / Below Average)
        Rank 13-20 -> 3 Stars (Neutral / Middle of the Pack)
        Rank 21-26 -> 4 Stars (Good / Above Average)
        Rank 27-32 -> 5 Stars (Amazing / Softest Matchup)
        """
        if rank is None:
            return 3
        if rank <= 6:
            return 1
        elif rank <= 12:
            return 2
        elif rank <= 20:
            return 3
        elif rank <= 26:
            return 4
        else:
            return 5

    def calculate_matchup_score(self, opponent_team: str, position: str) -> tuple[float, str]:
        """Calculates 0-100 MatchupScore using non-linear calibrated curve centered at 70 (neutral).
        
        Returns:
            tuple[float, str]: (matchup_score, grade: FAVORABLE | NEUTRAL | TOUGH)
        """
        pos = position.upper().strip()
        pos_rank = self.get_position_rank(opponent_team, pos)
        if pos in ("D/ST", "DST"):
            overall_rank = self.get_overall_off_rank(opponent_team)
        else:
            overall_rank = self.get_overall_rank(opponent_team)

        # Non-linear S-curve centering around 70.0:
        # Rank 16.5 is neutral (score = 70.0).
        # Rank 1 (toughest) produces ~36.0 (tough, but not a 3.1 linear zero).
        # Rank 32 (softest) produces ~95.0.
        pos_delta = (pos_rank - 16.5) / 15.5
        overall_delta = (overall_rank - 16.5) / 15.5

        blended_delta = (0.75 * pos_delta) + (0.25 * overall_delta)
        score = round(70.0 + (blended_delta * 26.0), 1)
        score = max(20.0, min(100.0, score))

        if score >= 76.0:
            grade: Literal["FAVORABLE", "NEUTRAL", "TOUGH"] = "FAVORABLE"
        elif score <= 58.0:
            grade = "TOUGH"
        else:
            grade = "NEUTRAL"

        return score, grade

    def calculate_role_matchup_score(
        self,
        opponent_team: str,
        position: str,
        is_receiving_back: bool = False,
        is_slot: bool = False,
        team_spread: float = 0.0,
    ) -> tuple[float, str, str]:
        """Calculates role-specific DvP score taking into account PPR receiving volume and slot alignment.
        
        Returns:
            tuple[float, str, str]: (score, grade, tactical_detail)
        """
        opp = opponent_team.upper().strip()
        profile = self.profiles.get(opp)
        pos = position.upper().strip()

        if not profile:
            score, grade = self.calculate_matchup_score(opp, pos)
            return score, grade, f"Standard neutral baseline vs {opp}"

        if pos in ("RB", "FB") and is_receiving_back:
            rec_rank = profile.rb_rec_rank
            overall_rank = profile.overall_def_rank
            pos_delta = (rec_rank - 16.5) / 15.5
            overall_delta = (overall_rank - 16.5) / 15.5
            blended_delta = (0.80 * pos_delta) + (0.20 * overall_delta)

            score = round(70.0 + (blended_delta * 26.0), 1)
            # Underdog pass funnel bonus
            if team_spread >= 4.0:
                score = min(100.0, score + 4.0)

            if score >= 76.0:
                grade = "FAVORABLE"
                detail = f"PPR Receiving Funnel vs {opp}: Defense yields #{rec_rank} targets/rec to RBs"
            elif score <= 58.0:
                grade = "TOUGH"
                detail = f"Stifling pass-coverage vs RBs: {opp} allows minimal checkdowns (#{rec_rank})"
            else:
                grade = "NEUTRAL"
                detail = f"Moderate checkdown volume expected vs {opp} (DvP rank #{rec_rank})"

            return max(20.0, min(100.0, score)), grade, detail

        if pos == "WR" and is_slot:
            slot_rank = profile.wr_slot_rank
            overall_rank = profile.overall_def_rank
            pos_delta = (slot_rank - 16.5) / 15.5
            overall_delta = (overall_rank - 16.5) / 15.5
            blended_delta = (0.80 * pos_delta) + (0.20 * overall_delta)

            score = round(70.0 + (blended_delta * 26.0), 1)
            if score >= 76.0:
                grade = "FAVORABLE"
                detail = f"Slot Matchup Advantage: {opp} ranks #{slot_rank} vs slot receivers over the middle"
            elif score <= 58.0:
                grade = "TOUGH"
                detail = f"Tough slot/nickel coverage vs {opp} (#{slot_rank} vs slot)"
            else:
                grade = "NEUTRAL"
                detail = f"Neutral slot coverage vs {opp} (#{slot_rank})"

            return max(20.0, min(100.0, score)), grade, detail

        # Default standard matchup
        score, grade = self.calculate_matchup_score(opp, pos)
        pos_rank = self.get_position_rank(opp, pos)
        if pos in ("D/ST", "DST"):
            off_rank = self.get_overall_off_rank(opp)
            detail = f"{grade.title()} streaming matchup vs {opp} (DvP rank #{pos_rank} vs D/ST, Opp Offense #{off_rank})"
        else:
            detail = f"{grade.title()} matchup vs {opp} (DvP rank #{pos_rank} vs {pos})"
        return score, grade, detail

    def detect_defensive_funnel(self, opponent_team: str) -> dict[str, Any]:
        """Detects whether an opponent functions as a Pass Funnel or Run Funnel.

        Returns:
            dict with keys:
                'is_pass_funnel': bool,
                'is_run_funnel': bool,
                'pass_rank': int,
                'rush_rank': int,
                'detail': str | None
        """
        opp = opponent_team.upper().strip()
        profile = self.profiles.get(opp)
        if not profile:
            return {
                "is_pass_funnel": False,
                "is_run_funnel": False,
                "pass_rank": 16,
                "rush_rank": 16,
                "detail": None,
            }

        pass_rank = profile.wr_rank
        rush_rank = profile.rb_rank

        # Pass Funnel: Stout vs Run (rb_rank <= 12), soft vs Pass (wr_rank >= 20 or diff >= 9)
        if rush_rank <= 12 and (pass_rank >= 20 or (pass_rank - rush_rank) >= 9):
            return {
                "is_pass_funnel": True,
                "is_run_funnel": False,
                "pass_rank": pass_rank,
                "rush_rank": rush_rank,
                "detail": f"Pass Funnel Defense: {opp} shuts down the run (#{rush_rank}) while conceding heavy yardage to wideouts (#{pass_rank})",
            }

        # Run Funnel: Stingy secondary (wr_rank <= 12), vulnerable on ground (rb_rank >= 20 or diff >= 9)
        if pass_rank <= 12 and (rush_rank >= 20 or (rush_rank - pass_rank) >= 9):
            return {
                "is_pass_funnel": False,
                "is_run_funnel": True,
                "pass_rank": pass_rank,
                "rush_rank": rush_rank,
                "detail": f"Run Funnel Defense: {opp} locks down outside receivers (#{pass_rank}) but is vulnerable against ground rushes (#{rush_rank})",
            }

        return {
            "is_pass_funnel": False,
            "is_run_funnel": False,
            "pass_rank": pass_rank,
            "rush_rank": rush_rank,
            "detail": None,
        }


dvp_client = DvPClient()

