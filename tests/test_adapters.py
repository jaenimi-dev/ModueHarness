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

    antigravity = create_adapter("antigravity")
    assert isinstance(antigravity, AGYCLIAdapter)

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


def test_claude_adapter_model_and_effort():
    """Verify Claude adapter configures and updates model and reasoning effort."""
    claude = ClaudeCLIAdapter(model="claude-3-7-sonnet-latest", effort="high")
    cmd = claude.build_command("Hello")
    assert "--model" in cmd
    assert "claude-3-7-sonnet-latest" in cmd
    assert "--effort" in cmd
    assert "high" in cmd
    assert "-p" in cmd

    # Test dynamic model update
    claude.set_model("opus")
    cmd2 = claude.build_command("Hello")
    assert "opus" in cmd2
    assert "claude-3-7-sonnet-latest" not in cmd2

    # Test dynamic effort update
    claude.set_effort("max")
    cmd3 = claude.build_command("Hello")
    assert "max" in cmd3
    assert "high" not in cmd3

    # Test clearing effort
    claude.set_effort(None)
    cmd4 = claude.build_command("Hello")
    assert "--effort" not in cmd4


def test_format_command_display_full():
    """Verify format_command_display preserves full command without truncation by default."""
    claude = ClaudeCLIAdapter()
    long_prompt = "### System / Role Directive:\nYou are an architect.\n\n### Task Instruction:\nBuild full web app with tests and docs."
    cmd = claude.build_command(long_prompt)

    full_display = claude.format_command_display(cmd)
    assert "..." not in full_display
    assert "### System / Role Directive:" in full_display
    assert "You are an architect." in full_display
    assert "Build full web app with tests and docs." in full_display

    # Explicit truncation if max_prompt_len is specified
    truncated = claude.format_command_display(cmd, max_prompt_len=20)
    assert "..." in truncated


def test_agy_adapter_features():
    """Verify AGY (Antigravity) adapter configuration, auto-permissions, model, and effort."""
    agy = AGYCLIAdapter(model="gemini-3.8-flash-high", effort="high")
    cmd = agy.build_command("Build test app")

    assert "--dangerously-skip-permissions" in cmd
    assert "-p" in cmd
    assert "--model" in cmd
    assert "gemini-3.8-flash-high" in cmd
    assert "--effort" in cmd
    assert "high" in cmd

    # Test dynamic model update
    agy.set_model("gemini-3.1-pro-high")
    cmd2 = agy.build_command("Build test app")
    assert "gemini-3.1-pro-high" in cmd2
    assert "gemini-3.8-flash-high" not in cmd2

    # Test dynamic effort update
    agy.set_effort("low")
    cmd3 = agy.build_command("Build test app")
    assert "low" in cmd3
    assert "high" not in cmd3

    # Test clearing effort
    agy.set_effort(None)
    cmd4 = agy.build_command("Build test app")
    assert "--effort" not in cmd4


