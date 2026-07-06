"""Application settings.

Configuration is read from environment variables (prefixed ``NUTRISCORE_``) or
an optional ``.env`` file, falling back to the defaults below. Meal-time windows
are ``(start_hour, end_hour)`` pairs on a 24-hour clock; anything outside them is
treated as a snack by the meal-type inference (domain layer).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NUTRISCORE_", env_file=".env")

    # Event store
    db_path: Path = Path("nutriscore.db")

    # OpenFoodFacts client
    off_base_url: str = "https://world.openfoodfacts.org"
    off_timeout_seconds: float = 5.0

    # Meal-type inference windows: (start_hour, end_hour), 24-hour clock.
    breakfast_window: tuple[int, int] = (5, 11)
    lunch_window: tuple[int, int] = (11, 15)
    dinner_window: tuple[int, int] = (18, 22)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loaded once and cached."""
    return Settings()
