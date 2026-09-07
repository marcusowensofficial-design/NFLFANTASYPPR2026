"""Application configuration and settings using Pydantic Settings."""

from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ESPN Configuration
    espn_league_id: int | None = None
    espn_season: int = 2026
    espn_swid: str | None = None
    espn_s2: str | None = None
    espn_team_id: int | None = None

    # FantasyPros Configuration
    fantasypros_api_key: str | None = None
    fantasypros_base_url: str = "https://api.fantasypros.com/public/v2/json"

    # Application Configuration
    database_url: str = "sqlite:///./data/fantasy.db"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    @field_validator("espn_league_id", "espn_team_id", mode="before")
    @classmethod
    def parse_optional_int(cls, v: Any) -> int | None:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return int(v)

    @field_validator("espn_swid", "espn_s2", "fantasypros_api_key", mode="before")
    @classmethod
    def parse_optional_str(cls, v: Any) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return str(v).strip()



settings = Settings()
