"""Weather client querying Open-Meteo API for NFL stadiums."""

import logging
from typing import Any
import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Coordinates for outdoor NFL stadiums (latitude, longitude, is_dome)
STADIUM_COORDINATES: dict[str, tuple[float, float, bool]] = {
    "ARI": (33.5276, -112.2626, True),   # State Farm Stadium (Retractable Roof)
    "ATL": (33.7554, -84.4009, True),    # Mercedes-Benz Stadium (Retractable Roof)
    "BAL": (39.2780, -76.6227, False),   # M&T Bank Stadium
    "BUF": (42.7738, -78.7870, False),   # Highmark Stadium
    "CAR": (35.2258, -80.8528, False),   # Bank of America Stadium
    "CHI": (41.8623, -87.6167, False),   # Soldier Field
    "CIN": (39.0955, -84.5161, False),   # Paycor Stadium
    "CLE": (41.5061, -81.6995, False),   # Cleveland Browns Stadium
    "DAL": (32.7473, -97.0945, True),    # AT&T Stadium (Retractable Roof)
    "DEN": (39.7439, -105.0201, False),  # Empower Field at Mile High
    "DET": (42.3400, -83.0456, True),    # Ford Field (Dome)
    "GB": (44.5013, -88.0622, False),    # Lambeau Field
    "HOU": (29.6847, -95.4107, True),    # NRG Stadium (Retractable Roof)
    "IND": (39.7601, -86.1639, True),    # Lucas Oil Stadium (Retractable Roof)
    "JAX": (30.3239, -81.6373, False),   # EverBank Stadium
    "KC": (39.0489, -94.4839, False),    # GEHA Field at Arrowhead
    "LV": (36.0908, -115.1833, True),    # Allegiant Stadium (Dome)
    "LAC": (33.9535, -118.3392, True),   # SoFi Stadium (Canopy)
    "LAR": (33.9535, -118.3392, True),   # SoFi Stadium (Canopy)
    "MIA": (25.9580, -80.2389, False),   # Hard Rock Stadium
    "MIN": (44.9739, -93.2575, True),    # U.S. Bank Stadium (Dome)
    "NE": (42.0909, -71.2643, False),    # Gillette Stadium
    "NO": (29.9511, -90.0812, True),     # Caesars Superdome (Dome)
    "NYG": (40.8135, -74.0744, False),   # MetLife Stadium
    "NYJ": (40.8135, -74.0744, False),   # MetLife Stadium
    "PHI": (39.9008, -75.1675, False),   # Lincoln Financial Field
    "PIT": (40.4468, -80.0158, False),   # Acrisure Stadium
    "SF": (37.4033, -121.9698, False),   # Levi's Stadium
    "SEA": (47.5952, -122.3316, False),  # Lumen Field
    "TB": (27.9759, -82.5033, False),    # Raymond James Stadium
    "TEN": (36.1665, -86.7713, False),   # Nissan Stadium
    "WSH": (38.9076, -76.8645, False),   # Northwest Stadium
}


class WeatherReport(BaseModel):
    team: str
    is_dome: bool
    temperature_f: float = 72.0
    wind_speed_mph: float = 0.0
    wind_gusts_mph: float = 0.0
    precipitation_in: float = 0.0
    weather_score: float = 100.0  # 0 to 100 (100 = perfect dome or mild weather)
    weather_concern: str | None = None  # None, "MODERATE_WIND", "HIGH_WIND", "RAIN"


class WeatherClient:
    """Client fetching real-time weather from Open-Meteo for outdoor NFL stadiums."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._cache: dict[tuple[str, str | None], WeatherReport] = {}

    async def get_stadium_weather(self, home_team: str, game_time_iso: str | None = None) -> WeatherReport:
        """Fetch game-time weather for a game hosted by home_team.
        
        If game_time_iso is provided, queries hourly forecast at kickoff time.
        """
        cache_key = (home_team.upper(), game_time_iso[:13] if game_time_iso else None)
        if cache_key in self._cache:
            return self._cache[cache_key]

        coords = STADIUM_COORDINATES.get(home_team.upper(), (39.0, -98.0, False))
        lat, lon, is_dome = coords

        if is_dome:
            report = WeatherReport(
                team=home_team,
                is_dome=True,
                temperature_f=72.0,
                wind_speed_mph=0.0,
                weather_score=100.0,
                weather_concern=None,
            )
            self._cache[cache_key] = report
            return report

        # Query Open-Meteo for outdoor venues with both current and hourly forecast
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
            "hourly": "temperature_2m,precipitation,wind_speed_10m,wind_gusts_10m",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                res_data = response.json()

            current_data = res_data.get("current", {})
            temp_f = float(current_data.get("temperature_2m", 70.0))
            precip = float(current_data.get("precipitation", 0.0))
            wind = float(current_data.get("wind_speed_10m", 5.0))
            gusts = float(current_data.get("wind_gusts_10m", 8.0))

            # If game_time_iso provided, attempt to locate the exact kickoff hour in hourly forecast
            if game_time_iso:
                hourly_data = res_data.get("hourly", {})
                time_list = hourly_data.get("time", [])
                target_prefix = game_time_iso.replace("Z", "")[:13]  # YYYY-MM-DDTHH
                matched_idx = next(
                    (i for i, t in enumerate(time_list) if t.startswith(target_prefix)),
                    None,
                )
                if matched_idx is not None:
                    h_temp = hourly_data.get("temperature_2m", [])
                    h_precip = hourly_data.get("precipitation", [])
                    h_wind = hourly_data.get("wind_speed_10m", [])
                    h_gusts = hourly_data.get("wind_gusts_10m", [])
                    if matched_idx < len(h_temp):
                        temp_f = float(h_temp[matched_idx])
                    if matched_idx < len(h_precip):
                        precip = float(h_precip[matched_idx])
                    if matched_idx < len(h_wind):
                        wind = float(h_wind[matched_idx])
                    if matched_idx < len(h_gusts):
                        gusts = float(h_gusts[matched_idx])

            # Compute weather score (0 to 100)
            score = 100.0
            concern = None

            if wind >= 20.0:
                score -= 30.0
                concern = "HIGH_WIND (>20 mph)"
            elif wind >= 15.0:
                score -= 15.0
                concern = "MODERATE_WIND (15-20 mph)"

            if precip > 0.15:
                score -= 20.0
                concern = f"HEAVY_RAIN ({precip:.2f} in)" if not concern else f"{concern}, RAIN"
            elif precip > 0.05:
                score -= 10.0

            if temp_f < 25.0:
                score -= 15.0

            report = WeatherReport(
                team=home_team,
                is_dome=False,
                temperature_f=round(temp_f, 1),
                wind_speed_mph=round(wind, 1),
                wind_gusts_mph=round(gusts, 1),
                precipitation_in=round(precip, 2),
                weather_score=max(0.0, min(100.0, score)),
                weather_concern=concern,
            )
            self._cache[cache_key] = report
            return report

        except Exception as e:
            logger.debug(f"Open-Meteo weather fetch failed for {home_team}: {e}")
            fallback = WeatherReport(team=home_team, is_dome=False, weather_score=90.0)
            self._cache[cache_key] = fallback
            return fallback



    def get_weather_impact_for_position(self, position: str, report: WeatherReport) -> tuple[float, str | None]:
        """Calculates position-specific weather sensitivity score and narrative note."""
        if report.is_dome:
            return 100.0, None

        pos = position.upper().strip()
        wind = report.wind_speed_mph
        precip = report.precipitation_in
        temp = report.temperature_f

        base_score = 100.0
        notes: list[str] = []

        if pos in ("K", "PK"):
            # Kickers are most vulnerable to wind and rain
            if wind >= 20.0:
                base_score -= 35.0
                notes.append(f"High wind ({wind} mph) severely impairs FG range & trajectory")
            elif wind >= 15.0:
                base_score -= 18.0
                notes.append(f"Crosswinds ({wind} mph) threaten FG accuracy")
            if precip >= 0.10:
                base_score -= 15.0
                notes.append("Wet field limits footing and ball striking")

        elif pos in ("QB", "WR"):
            # Downfield passing timing and deep balls disrupted
            if wind >= 20.0:
                base_score -= 25.0
                notes.append(f"High wind ({wind} mph) suppresses deep passing efficiency")
            elif wind >= 15.0:
                base_score -= 8.0
                notes.append(f"Breezy conditions ({wind} mph) moderately test vertical routes")
            if precip >= 0.15:
                base_score -= 15.0
                notes.append("Heavy rain challenges ball grip & downfield timing")
            elif precip >= 0.05:
                base_score -= 8.0

        elif pos in ("RB", "FB"):
            # Ground games and short dump-offs thrive in moderate wind
            if 15.0 <= wind < 22.0:
                base_score = min(100.0, base_score + 2.0)
                notes.append(f"Favorable game script: wind ({wind} mph) boosts ground volume & dump-offs")
            elif wind >= 22.0:
                base_score -= 6.0  # Minor drive stall penalty
            if precip >= 0.15:
                base_score -= 5.0  # Slippery ball security risk

        elif pos == "TE":
            # TEs work the intermediate middle and benefit from checkdowns
            if 15.0 <= wind < 20.0:
                base_score = min(100.0, base_score + 2.0)
                notes.append(f"Underneath volume boost: checkdowns favored in {wind} mph wind")
            elif wind >= 20.0:
                base_score -= 10.0
            if precip >= 0.15:
                base_score -= 8.0

        elif pos in ("D/ST", "DST"):
            # Adverse weather heavily benefits defense/special teams
            if wind >= 18.0:
                base_score = min(100.0, base_score + 10.0)
                notes.append(f"Defensive edge: {wind} mph wind forces errant throws & punts")
            if precip >= 0.10:
                base_score = min(100.0, base_score + 6.0)
                notes.append("Wet conditions amplify fumble and turnover potential")

        if temp < 25.0:
            base_score -= 10.0
            notes.append(f"Freezing temperature ({temp}°F)")

        final_score = max(0.0, min(100.0, base_score))
        return final_score, "; ".join(notes) if notes else None


weather_client = WeatherClient()

