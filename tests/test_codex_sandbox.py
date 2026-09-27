"""Tests for the Codex adapter's sandbox handling (blackboard --add-dir, boolean sandbox rejection)."""

import json
import sys
from pathlib import Path

import pytest

from modue_harness.adapters import CodexCLIAdapter, create_adapter
from modue_harness.core.types import TurnContext

FAKE_CODEX = "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"


def _fake_codex(tmp_path: Path, **kwargs) -> CodexCLIAdapter:
    script = tmp_path / "fake_codex.py"
    script.write_text(FAKE_CODEX, encoding="utf-8")
    adapter = CodexCLIAdapter(command=sys.executable, **kwargs)
    adapter.default_args = [str(script)] + adapter.default_args
    return adapter


def _ctx(tmp_path: Path) -> TurnContext:
    ws, board = tmp_path / "ws", tmp_path / "board"
    ws.mkdir(exist_ok=True)
    board.mkdir(exist_ok=True)
    return TurnContext(step_id="s", instruction="x", blackboard_dir=board, workspace_dir=ws)


def _argv(adapter: CodexCLIAdapter, ctx: TurnContext) -> list:
    result = adapter.execute(ctx)
    assert result.is_success, result.error_message
    return json.loads(result.stdout)


def test_workspace_write_adds_blackboard_dir(tmp_path: Path):
    ctx = _ctx(tmp_path)
    argv = _argv(_fake_codex(tmp_path), ctx)

    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("--add-dir") + 1] == str(ctx.blackboard_dir)


def test_blackboard_dir_added_in_stream_mode(tmp_path: Path):
    ctx = _ctx(tmp_path)
    gen = _fake_codex(tmp_path).execute_stream(ctx)
    lines = []
    try:
        while True:
            lines.append(next(gen))
    except StopIteration:
        pass
    assert "--add-dir" in json.loads("".join(lines))


@pytest.mark.parametrize("mode", ["read-only", "danger-full-access"])
def test_other_sandbox_modes_do_not_add_dir(tmp_path: Path, mode: str):
    argv = _argv(_fake_codex(tmp_path, sandbox=mode), _ctx(tmp_path))
    assert "--add-dir" not in argv


def test_user_add_dir_is_respected(tmp_path: Path):
    adapter = _fake_codex(tmp_path)
    adapter.default_args += ["--add-dir", "/custom"]
    argv = _argv(adapter, _ctx(tmp_path))
    assert argv.count("--add-dir") == 1


@pytest.mark.parametrize("value", [True, False])
def test_boolean_sandbox_is_rejected(value: bool):
    with pytest.raises(ValueError, match="mode string"):
        create_adapter("codex", sandbox=value)


def test_sandbox_mode_string_from_agents_yaml(tmp_path: Path):
    from modue_harness.engine.interactive import load_or_detect_agents

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agents.yaml").write_text(
        "agents:\n  dev:\n    adapter: codex\n    sandbox: read-only\n", encoding="utf-8"
    )
    agents = load_or_detect_agents(cwd=tmp_path)
    assert agents["dev"].sandbox == "read-only"


# ------------------------------------------------------- save / reload roundtrip
def test_adapter_type_of_covers_all_registered_types():
    from modue_harness.adapters import GenericCLIAdapter, adapter_type_of

    assert adapter_type_of(create_adapter("codex")) == "codex"
    assert adapter_type_of(create_adapter("chatgpt")) == "codex"
    assert adapter_type_of(create_adapter("claude")) == "claude"
    assert adapter_type_of(create_adapter("antigravity")) == "agy"
    assert adapter_type_of(GenericCLIAdapter(name="g", command="echo")) == "generic"


@pytest.mark.parametrize("sandbox", ["workspace-write", "read-only"])
def test_codex_agent_survives_save_and_reload(tmp_path: Path, sandbox: str):
    """Regression: save_agents_config wrote Codex agents back as `adapter: generic`."""
    import yaml

    from modue_harness.engine.interactive import InteractiveSession, load_or_detect_agents

    session = InteractiveSession.__new__(InteractiveSession)
    session.agents = {"dev": create_adapter("codex", name="dev", model="gpt-5.5", sandbox=sandbox)}
    session.conductor_name = "dev"
    session.agents_file = None
    target = tmp_path / "config" / "agents.yaml"

    session.save_agents_config(target)

    entry = yaml.safe_load(target.read_text(encoding="utf-8"))["agents"]["dev"]
    assert entry["adapter"] == "codex"
    reloaded = load_or_detect_agents(cwd=tmp_path)["dev"]
    assert isinstance(reloaded, CodexCLIAdapter)
    assert reloaded.sandbox == sandbox
    assert reloaded.model == "gpt-5.5"
    assert reloaded.default_args.count("--sandbox") == 1
