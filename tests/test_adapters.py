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
    CodexCLIAdapter,
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

    codex = create_adapter("codex")
    assert isinstance(codex, CodexCLIAdapter)

    chatgpt = create_adapter("chatgpt")
    assert isinstance(chatgpt, CodexCLIAdapter)

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


def test_resolve_agy_binary_windows(monkeypatch, tmp_path: Path):
    """Verify resolve_agy_binary discovers Windows %LOCALAPPDATA%\\agy\\bin\\agy.exe."""
    from modue_harness.adapters.agy import resolve_agy_binary
    fake_localappdata = tmp_path / "AppData" / "Local"
    fake_bin = fake_localappdata / "agy" / "bin"
    fake_bin.mkdir(parents=True)
    fake_exe = fake_bin / "agy.exe"
    fake_exe.touch()

    monkeypatch.setenv("LOCALAPPDATA", str(fake_localappdata))
    monkeypatch.setattr("shutil.which", lambda x: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake_home")

    resolved = resolve_agy_binary("agy")
    assert resolved == str(fake_exe)


def test_codex_adapter_command_building():
    """Verify CodexCLIAdapter command line construction and dynamic updates."""
    codex = CodexCLIAdapter(
        name="codex-worker",
        command="codex",
        model="gpt-5.6-terra",
        effort="high",
        sandbox="workspace-write",
    )
    cmd = codex.build_command("Analyze and implement feature")
    assert "codex" in cmd[0]
    assert "exec" in cmd
    assert "--sandbox" in cmd
    assert "workspace-write" in cmd
    assert "-m" in cmd
    assert "gpt-5.6-terra" in cmd
    assert cmd[-1] == "Analyze and implement feature"

    # Test dynamic model update
    codex.set_model("gpt-5.6-luna")
    cmd2 = codex.build_command("Build test app")
    assert "gpt-5.6-luna" in cmd2
    assert "gpt-5.6-terra" not in cmd2


def test_resolve_codex_binary(monkeypatch, tmp_path: Path):
    """Verify resolve_codex_binary finds binary in custom paths."""
    from modue_harness.adapters.codex import resolve_codex_binary

    fake_local = tmp_path / ".local" / "bin"
    fake_local.mkdir(parents=True)
    fake_codex = fake_local / "codex"
    fake_codex.touch()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("shutil.which", lambda x: None)

    resolved = resolve_codex_binary("codex")
    assert resolved == str(fake_codex)


def test_agy_get_available_models(monkeypatch):
    """Verify get_available_agy_models parses models correctly from subprocess."""
    from modue_harness.adapters.agy import get_available_agy_models, get_agy_model_ids
    import subprocess

    fake_stdout = (
        "gemini-3.8-flash-high\tGemini 3.8 Flash (High)\n"
        "gemini-3.1-pro-high\tGemini 3.1 Pro (High)\n"
        "claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)\n"
    )

    class FakeCompletedProcess:
        returncode = 0
        stdout = fake_stdout
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeCompletedProcess())

    models = get_available_agy_models(force_refresh=True)
    assert len(models) == 3
    assert models[0]["id"] == "gemini-3.8-flash-high"
    assert models[0]["name"] == "Gemini 3.8 Flash (High)"
    assert models[1]["id"] == "gemini-3.1-pro-high"

    ids = get_agy_model_ids(force_refresh=False)
    assert ids == ["gemini-3.8-flash-high", "gemini-3.1-pro-high", "claude-sonnet-4-6"]


def test_ui_controller_get_adapter_models():
    """Verify UIController.get_adapter_models returns valid models for adapters."""
    from modue_harness.ui.controller import UIController

    ctrl = UIController(project_name="test_proj")

    agy_models = ctrl.get_adapter_models("agy")
    assert len(agy_models) > 0
    assert any("gemini" in m["id"] for m in agy_models)

    codex_models = ctrl.get_adapter_models("codex")
    assert len(codex_models) >= 3
    assert codex_models[0]["id"] == "gpt-5.6-terra"

    claude_models = ctrl.get_adapter_models("claude")
    assert len(claude_models) >= 3
    assert claude_models[0]["id"] == "sonnet"


def test_claude_get_available_models(monkeypatch):
    """Verify get_available_claude_models fallback and API query."""
    from modue_harness.adapters.claude import get_available_claude_models, get_claude_model_ids

    # Without API key, should return default fallback models
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    models = get_available_claude_models(force_refresh=True)
    assert len(models) >= 3
    assert any(m["id"] == "sonnet" for m in models)

    ids = get_claude_model_ids()
    assert "sonnet" in ids


def test_codex_get_available_models(monkeypatch, tmp_path):
    """Verify get_available_codex_models local config parsing and defaults."""
    from modue_harness.adapters.codex import get_available_codex_models, get_codex_model_ids

    # Without custom config, should return default models
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    models = get_available_codex_models(force_refresh=True)
    assert len(models) >= 3
    assert any(m["id"] == "gpt-5.6-terra" for m in models)

    # With local config.toml
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    cfg_file = codex_home / "config.toml"
    cfg_file.write_text('model = "custom-codex-v1"\nmodel_reasoning_effort = "high"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    models_with_cfg = get_available_codex_models(force_refresh=True)
    assert models_with_cfg[0]["id"] == "custom-codex-v1"
    ids = get_codex_model_ids()
    assert "custom-codex-v1" in ids





def test_create_adapter_drops_optional_kwargs_the_adapter_cannot_take():
    """A permission key meant for one adapter must not break another."""
    from modue_harness.adapters import create_adapter

    # GenericCLIAdapter takes no permission_mode; it should be ignored, not raise.
    adapter = create_adapter("generic", name="tool", command="echo", permission_mode="plan")
    assert adapter.command == "echo"
    assert "--permission-mode" not in adapter.default_args


def test_create_adapter_still_raises_on_unknown_keys():
    """Typos outside the optional set stay visible."""
    import pytest

    from modue_harness.adapters import create_adapter

    with pytest.raises(TypeError):
        create_adapter("generic", name="tool", command="echo", nonexistent_option=1)
