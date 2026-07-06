from pathlib import Path

from nutriscore.config import Settings, get_settings


def test_defaults_are_sensible():
    settings = Settings()

    assert isinstance(settings.db_path, Path)
    assert settings.off_base_url.startswith("https://")
    assert settings.off_timeout_seconds > 0


def test_default_meal_windows_match_the_plan():
    settings = Settings()

    assert settings.breakfast_window == (5, 11)
    assert settings.lunch_window == (11, 15)
    assert settings.dinner_window == (18, 22)


def test_values_are_overridable_from_the_environment(monkeypatch):
    monkeypatch.setenv("NUTRISCORE_OFF_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("NUTRISCORE_DB_PATH", "/tmp/custom.db")

    settings = Settings()

    assert settings.off_timeout_seconds == 2.5
    assert settings.db_path == Path("/tmp/custom.db")


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
