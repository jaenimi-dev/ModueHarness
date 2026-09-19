"""Tests for core BaseHarness and HarnessConfig."""

from pathlib import Path
from typing import Any
import pytest
from modue_harness.core.config import HarnessConfig
from modue_harness.core.harness import BaseHarness


class DummyHarness(BaseHarness):
    """Test concrete harness implementation."""

    def setup(self) -> None:
        super().setup()
        self.setup_called = True

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return {"status": "ok", "args": args, "kwargs": kwargs}

    def teardown(self) -> None:
        super().teardown()
        self.teardown_called = True


def test_harness_config_defaults():
    """Verify default configurations."""
    config = HarnessConfig()
    assert config.name == "default-harness"
    assert config.version == "0.5.0"
    assert config.debug is False
    assert config.options == {}


def test_load_dotenv(tmp_path: Path, monkeypatch):
    """Verify loading key-value pairs from .env into environment."""
    from modue_harness.core.config import load_dotenv
    import os

    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY_ALPHA=hello_world\nTEST_KEY_BETA='quoted_val'\n# Comment line\n", encoding="utf-8")

    monkeypatch.delenv("TEST_KEY_ALPHA", raising=False)
    monkeypatch.delenv("TEST_KEY_BETA", raising=False)

    load_dotenv(env_file)
    assert os.environ.get("TEST_KEY_ALPHA") == "hello_world"
    assert os.environ.get("TEST_KEY_BETA") == "quoted_val"


def test_harness_lifecycle():
    """Verify harness lifecycle execution (setup, run, teardown)."""
    harness = DummyHarness()
    assert not harness.is_initialized

    harness.setup()
    assert harness.is_initialized
    assert harness.setup_called

    result = harness.run("sample_payload", key="value")
    assert result["status"] == "ok"
    assert result["args"] == ("sample_payload",)
    assert result["kwargs"] == {"key": "value"}

    harness.teardown()
    assert not harness.is_initialized
    assert harness.teardown_called


def test_harness_context_manager():
    """Verify harness context manager behavior."""
    with DummyHarness() as harness:
        assert harness.is_initialized
        res = harness.run()
        assert res["status"] == "ok"

    assert not harness.is_initialized
