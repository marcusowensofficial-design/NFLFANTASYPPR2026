"""Weather adapter package."""

from src.adapters.weather.client import (
    STADIUM_COORDINATES,
    WeatherClient,
    WeatherReport,
    weather_client,
)

__all__ = ["WeatherClient", "WeatherReport", "weather_client", "STADIUM_COORDINATES"]
