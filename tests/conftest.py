"""Pytest configuration and shared fixtures."""

import pytest

from modue_harness.core.config import HarnessConfig


@pytest.fixture
def default_config() -> HarnessConfig:
    """Fixture providing a default HarnessConfig."""
    return HarnessConfig(name="test-harness", version="0.0.0", debug=True)


@pytest.fixture(autouse=True)
def isolated_agy_settings(tmp_path_factory, monkeypatch):
    """Never let tests touch the real ~/.gemini/antigravity-cli/settings.json (agy auto-guard)."""
    from modue_harness.adapters import agy_guard

    path = tmp_path_factory.mktemp("agy_settings") / "settings.json"
    monkeypatch.setattr(agy_guard, "AGY_SETTINGS_PATH", path)
    return path
