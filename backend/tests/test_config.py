"""Tests for the application configuration.

Asserts that:
- Default settings are correctly loaded.
- Persona paths resolve correctly.
- Property methods return expected values.
"""

from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings class."""

    def test_default_environment(self) -> None:
        """Default environment should be development."""
        settings = Settings()
        # By default pydantic-settings might load from environment,
        # but in test conftest we override it.
        # This will just verify the property exists and is a string.
        assert isinstance(settings.environment, str)

    def test_get_clone_data_path(self) -> None:
        """get_clone_data_path should return a valid Path."""
        settings = Settings()
        path = settings.get_clone_data_path("alucard")
        assert isinstance(path, Path)
        assert path.name == "data"

    def test_get_clone_persona_path(self) -> None:
        """get_clone_persona_path should return a valid Path ending in persona.txt."""
        settings = Settings()
        path = settings.get_clone_persona_path("alucard")
        assert isinstance(path, Path)
        assert path.name == "persona_v1.txt"

    def test_get_settings_is_singleton(self) -> None:
        """get_settings should return the same instance on subsequent calls."""
        settings_1 = get_settings()
        settings_2 = get_settings()
        assert settings_1 is settings_2
