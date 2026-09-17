"""Pytest configuration and shared fixtures."""

import pytest

from modue_harness.core.config import HarnessConfig


@pytest.fixture
def default_config() -> HarnessConfig:
    """Fixture providing a default HarnessConfig."""
    return HarnessConfig(name="test-harness", version="0.0.0", debug=True)
