"""Tests for CLI Adapters."""

from pathlib import Path
import sys
import pytest

from modue_harness.adapters import (
    BaseCLIAdapter,
    GenericCLIAdapter,
    ClaudeCLIAdapter,
    AGYCLIAdapter,
    AiderCLIAdapter,
    create_adapter,
    strip_ansi,
)
from modue_harness.core.types import TaskStatus, TurnContext


def test_strip_ansi():
    """Verify ANSI escape codes are stripped."""
    colored_text = "\x1b[31mRed text\x1b[0m and \x1b[1mBold\x1b[0m"
    assert strip_ansi(colored_text) == "Red text and Bold"


def test_adapter_factory():
    """Verify create_adapter resolves correct classes."""
    claude = create_adapter("claude")
    assert isinstance(claude, ClaudeCLIAdapter)

    agy = create_adapter("agy")
    assert isinstance(agy, AGYCLIAdapter)

    aider = create_adapter("aider")
    assert isinstance(aider, AiderCLIAdapter)

    generic = create_adapter("unknown-custom")
    assert isinstance(generic, GenericCLIAdapter)


def test_generic_adapter_command_building():
    """Verify command list construction."""
    adapter = GenericCLIAdapter(
        name="test",
        command="echo",
        default_args=["-n"],
        prompt_delivery="positional",
    )
    cmd = adapter.build_command("hello world")
    assert cmd == ["echo", "-n", "hello world"]


def test_generic_adapter_execution(tmp_path: Path):
    """Verify actual subprocess execution using python command."""
    # Use current python executable to run a one-liner
    adapter = GenericCLIAdapter(
        name="python-echo",
        command=sys.executable,
        default_args=["-c", "import sys; print('Output: ' + sys.stdin.read().strip())"],
        prompt_delivery="stdin",
    )

    board_dir = tmp_path / "blackboard"
    board_dir.mkdir()
    context = TurnContext(
        step_id="step_1",
        instruction="Ping test",
        blackboard_dir=board_dir,
        workspace_dir=tmp_path,
    )

    result = adapter.execute(context)
    assert result.is_success
    assert result.exit_code == 0
    assert "Output: ### Task Instruction:\n\nPing test" in result.stdout


def test_adapter_command_not_found(tmp_path: Path):
    """Verify handling of missing commands."""
    adapter = GenericCLIAdapter(
        name="missing",
        command="non_existent_command_xyz_123",
    )
    context = TurnContext(
        step_id="step_fail",
        instruction="Fail",
        blackboard_dir=tmp_path,
        workspace_dir=tmp_path,
    )
    result = adapter.execute(context)
    assert not result.is_success
    assert result.exit_code == 127
    assert "Command not found" in (result.error_message or "")


def test_adapter_timeout_handling(tmp_path: Path):
    """Verify timeout expiration handling."""
    adapter = GenericCLIAdapter(
        name="sleeper",
        command=sys.executable,
        default_args=["-c", "import time; time.sleep(2)"],
        prompt_delivery="stdin",
    )
    context = TurnContext(
        step_id="step_timeout",
        instruction="Sleep",
        blackboard_dir=tmp_path,
        workspace_dir=tmp_path,
    )
    result = adapter.execute(context, timeout=0.2)
    assert not result.is_success
    assert result.exit_code == 124
    assert "timed out" in (result.error_message or "")


def test_adapter_stream_execution(tmp_path: Path):
    """Verify streaming execution yields output chunks."""
    adapter = GenericCLIAdapter(
        name="streamer",
        command=sys.executable,
        default_args=["-c", "print('Line1'); print('Line2')"],
        prompt_delivery="stdin",
    )
    context = TurnContext(
        step_id="step_stream",
        instruction="Stream",
        blackboard_dir=tmp_path,
        workspace_dir=tmp_path,
    )

    gen = adapter.execute_stream(context)
    lines = list(gen)
    assert any("Line1" in l for l in lines)
    assert any("Line2" in l for l in lines)
