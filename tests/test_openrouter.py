"""Tests for the OpenRouter agent adapter and its workspace-scoped tools (no network)."""

import json
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from modue_harness.adapters import (
    OpenRouterAgentAdapter,
    create_adapter,
)
from modue_harness.adapters.agent_tools import WorkspaceTools
from modue_harness.core.types import TaskStatus, TurnContext


# --------------------------------------------------------------------------- fakes
def _tool_call(call_id: str, name: str, args: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _response(content: str = "", tool_calls: Optional[List[Any]] = None, prompt: int = 10, completion: int = 5, cost: Optional[float] = None) -> SimpleNamespace:
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, cost=cost)
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


class FakeClient:
    """Mimics openai.OpenAI().chat.completions.create with scripted responses."""

    def __init__(self, responses: List[Any]) -> None:
        self.responses = list(responses)
        self.requests: List[Dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.requests.append(json.loads(json.dumps(kwargs, default=str)))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item()
        return item


def _context(workspace: Path, instruction: str = "do the task") -> TurnContext:
    board = workspace.parent / "board"
    board.mkdir(exist_ok=True)
    return TurnContext(step_id="s1", instruction=instruction, blackboard_dir=board, workspace_dir=workspace)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "project"
    ws.mkdir()
    (ws / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    return ws


# ----------------------------------------------------------------- agent loop
def test_tool_loop_writes_file_and_returns_final_answer(workspace: Path):
    client = FakeClient([
        _response(tool_calls=[_tool_call("c1", "write_file", {"path": "src/calc.py", "content": "def add(a, b):\n    return a + b\n"})]),
        _response(tool_calls=[_tool_call("c2", "read_file", {"path": "src/calc.py"})]),
        _response("Created src/calc.py", cost=0.002),
    ])
    adapter = OpenRouterAgentAdapter(model="test/model", tools="full", client=client)

    result = adapter.execute(_context(workspace))

    assert result.is_success, result.error_message
    assert result.stdout == "Created src/calc.py"
    assert (workspace / "src" / "calc.py").read_text(encoding="utf-8").startswith("def add")
    # The tool result is fed back to the model on the next request.
    tool_msgs = [m for m in client.requests[2]["messages"] if m["role"] == "tool"]
    assert "return a + b" in tool_msgs[-1]["content"]
    assert result.metadata["turns"] == 3
    assert [c["tool"] for c in result.metadata["tool_calls"]] == ["write_file", "read_file"]
    usage = result.metadata["usage"]
    assert usage["input_tokens"] == 30 and usage["output_tokens"] == 15
    assert usage["cost_usd"] == pytest.approx(0.002)
    assert usage["is_estimated"] is False


def test_request_carries_model_tools_effort_and_system_instruction(workspace: Path):
    client = FakeClient([_response("done")])
    adapter = OpenRouterAgentAdapter(
        model="test/model", effort="high", tools="read", system_instruction="Be a reviewer.", client=client
    )

    adapter.execute(_context(workspace, "review it"))

    req = client.requests[0]
    assert req["model"] == "test/model"
    assert {t["function"]["name"] for t in req["tools"]} == {"list_dir", "read_file", "search"}
    assert req["extra_body"]["reasoning"] == {"effort": "high"}
    assert req["messages"][0]["role"] == "system"
    assert "Be a reviewer." in req["messages"][0]["content"]
    assert "review it" in req["messages"][-1]["content"]


def test_tools_none_sends_no_tools(workspace: Path):
    client = FakeClient([_response("opinion")])
    adapter = OpenRouterAgentAdapter(model="m", tools="none", client=client)

    result = adapter.execute(_context(workspace))

    assert result.is_success
    assert "tools" not in client.requests[0]


def test_custom_base_url_omits_openrouter_only_fields(workspace: Path):
    client = FakeClient([_response("ok")])
    adapter = OpenRouterAgentAdapter(model="m", effort="high", base_url="http://localhost:11434/v1", client=client)

    adapter.execute(_context(workspace))

    assert "extra_body" not in client.requests[0]


def test_read_level_rejects_write_tool_even_if_model_calls_it(workspace: Path):
    client = FakeClient([
        _response(tool_calls=[_tool_call("c1", "write_file", {"path": "x.txt", "content": "x"})]),
        _response("gave up"),
    ])
    adapter = OpenRouterAgentAdapter(model="m", client=client)  # default tools: read

    result = adapter.execute(_context(workspace))

    assert result.is_success
    assert not (workspace / "x.txt").exists()
    assert result.metadata["tool_calls"][0]["ok"] is False


def test_invalid_tool_arguments_are_reported_to_model(workspace: Path):
    bad = SimpleNamespace(id="c1", type="function", function=SimpleNamespace(name="read_file", arguments="{not json"))
    client = FakeClient([_response(tool_calls=[bad]), _response("recovered")])
    adapter = OpenRouterAgentAdapter(model="m", client=client)

    result = adapter.execute(_context(workspace))

    assert result.is_success
    tool_msg = [m for m in client.requests[1]["messages"] if m["role"] == "tool"][0]
    assert tool_msg["content"].startswith("Error: could not parse arguments")


def test_empty_reply_is_nudged_then_completes(workspace: Path):
    client = FakeClient([_response(""), _response("finished")])
    adapter = OpenRouterAgentAdapter(model="m", client=client)

    result = adapter.execute(_context(workspace))

    assert result.is_success and result.stdout == "finished"
    assert client.requests[1]["messages"][-1]["role"] == "user"


def test_repeated_empty_replies_fail(workspace: Path):
    client = FakeClient([_response(""), _response(""), _response("")])
    adapter = OpenRouterAgentAdapter(model="m", client=client)

    result = adapter.execute(_context(workspace))

    assert result.status == TaskStatus.FAILED
    assert "empty response" in result.error_message


def test_empty_path_means_workspace_root(workspace: Path):
    tools = WorkspaceTools(workspace, level="read")

    assert "hello.py" in tools.run("list_dir", {"path": ""})


def test_max_turns_exceeded_fails(workspace: Path):
    loop = [_response(tool_calls=[_tool_call(f"c{i}", "list_dir", {})]) for i in range(3)]
    adapter = OpenRouterAgentAdapter(model="m", max_turns=3, client=FakeClient(loop))

    result = adapter.execute(_context(workspace))

    assert result.status == TaskStatus.FAILED
    assert "max_turns (3)" in result.error_message


def test_timeout_fails(workspace: Path, monkeypatch):
    import modue_harness.adapters.openrouter as mod

    clock = iter([100.0, 100.0, 200.0, 200.0, 200.0])
    monkeypatch.setattr(mod.time, "time", lambda: next(clock, 200.0))
    client = FakeClient([_response(tool_calls=[_tool_call("c1", "list_dir", {})])])
    adapter = OpenRouterAgentAdapter(model="m", client=client)

    result = adapter.execute(_context(workspace), timeout=30)

    assert result.status == TaskStatus.FAILED
    assert result.exit_code == 124


def test_cancel_stops_loop(workspace: Path):
    adapter_ref: Dict[str, Any] = {}

    def cancel_then_call():
        adapter_ref["a"].cancel()
        return _response(tool_calls=[_tool_call("c1", "list_dir", {})])

    client = FakeClient([cancel_then_call, _response("should not be reached")])
    adapter = OpenRouterAgentAdapter(model="m", client=client)
    adapter_ref["a"] = adapter

    result = adapter.execute(_context(workspace))

    assert result.status == TaskStatus.FAILED
    assert "취소" in result.error_message
    assert len(client.requests) == 1


def test_rate_limit_error_is_detectable_by_usage_tracker(workspace: Path):
    from modue_harness.core.usage import detect_limit_signal

    err = Exception("Rate limited")
    err.status_code = 429  # type: ignore[attr-defined]
    adapter = OpenRouterAgentAdapter(model="m", client=FakeClient([err]))

    result = adapter.execute(_context(workspace))

    assert result.status == TaskStatus.FAILED
    assert detect_limit_signal(result.stdout, result.stderr)["is_rate_limited"] is True


def test_missing_api_key_fails_with_clear_message(workspace: Path, monkeypatch, tmp_path: Path):
    monkeypatch.delenv("MODUE_TEST_MISSING_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    adapter = OpenRouterAgentAdapter(model="m", api_key_env="MODUE_TEST_MISSING_KEY")

    result = adapter.execute(_context(workspace))

    assert result.status == TaskStatus.FAILED
    assert "MODUE_TEST_MISSING_KEY" in result.error_message


def test_missing_sdk_raises_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ImportError, match=r"modue-harness\[openrouter\]"):
        OpenRouterAgentAdapter(model="m")


def test_model_is_required():
    with pytest.raises(ValueError, match="requires a model"):
        OpenRouterAgentAdapter(client=FakeClient([]))


def test_execute_stream_yields_tool_progress_and_answer(workspace: Path):
    client = FakeClient([
        _response(tool_calls=[_tool_call("c1", "list_dir", {})]),
        _response("final"),
    ])
    adapter = OpenRouterAgentAdapter(model="m", client=client)

    gen = adapter.execute_stream(_context(workspace))
    lines = []
    try:
        while True:
            lines.append(next(gen))
    except StopIteration as stop:
        result = stop.value

    assert lines[0].startswith("🔧 list_dir")
    assert lines[-1] == "final"
    assert result.is_success


# -------------------------------------------------------------- path safety
def test_paths_outside_workspace_are_rejected(workspace: Path, tmp_path: Path):
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    tools = WorkspaceTools(workspace, level="full")

    assert "outside the workspace" in tools.run("read_file", {"path": "../secret.txt"})
    assert "outside the workspace" in tools.run("read_file", {"path": str(tmp_path / "secret.txt")})
    assert "outside the workspace" in tools.run("write_file", {"path": "../escape.txt", "content": "x"})
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlink_escape_is_rejected(workspace: Path, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "link").symlink_to(outside, target_is_directory=True)
    tools = WorkspaceTools(workspace, level="full")

    assert "outside the workspace" in tools.run("write_file", {"path": "link/pwned.txt", "content": "x"})
    assert not (outside / "pwned.txt").exists()


def test_writing_inside_git_is_rejected(workspace: Path):
    (workspace / ".git").mkdir()
    tools = WorkspaceTools(workspace, level="full")

    assert "inside .git" in tools.run("write_file", {"path": ".git/config", "content": "x"})


def test_tool_levels_control_exposed_tools(workspace: Path):
    assert WorkspaceTools(workspace, level="none").tool_names() == []
    assert set(WorkspaceTools(workspace, level="read").tool_names()) == {"list_dir", "read_file", "search"}
    full = set(WorkspaceTools(workspace, level="full").tool_names())
    assert {"write_file", "edit_file", "run_command"} <= full
    no_cmd = set(WorkspaceTools(workspace, level="full", allowed_commands=[]).tool_names())
    assert "run_command" not in no_cmd


def test_edit_file_requires_unique_match(workspace: Path):
    (workspace / "a.txt").write_text("x = 1\nx = 1\ny = 2\n", encoding="utf-8")
    tools = WorkspaceTools(workspace, level="full")

    assert "matches 2 places" in tools.run("edit_file", {"path": "a.txt", "old_string": "x = 1", "new_string": "x = 3"})
    assert tools.run("edit_file", {"path": "a.txt", "old_string": "y = 2", "new_string": "y = 5"}).startswith("Edited")
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "x = 1\nx = 1\ny = 5\n"


def test_read_and_search_tools(workspace: Path):
    tools = WorkspaceTools(workspace, level="read")

    assert "1\tprint('hi')" in tools.run("read_file", {"path": "hello.py"})
    assert "hello.py:1:" in tools.run("search", {"pattern": r"print\("})
    assert "hello.py" in tools.run("list_dir", {})
    assert tools.run("search", {"pattern": "("}).startswith("Error: invalid regex")


# ------------------------------------------------------------- run_command
def test_run_command_allowlist(workspace: Path):
    tools = WorkspaceTools(workspace, level="full")

    assert "not in allow list" in tools.run("run_command", {"command": "rm -rf ."})
    assert "not in allow list" in tools.run("run_command", {"command": "python hello.py"})
    out = tools.run("run_command", {"command": "ls"})
    assert out.startswith("[exit code 0]") and "hello.py" in out
    assert (workspace / "hello.py").exists()


def test_run_command_rejects_paths_outside_workspace(workspace: Path):
    tools = WorkspaceTools(workspace, level="full")

    assert "outside the workspace" in tools.run("run_command", {"command": "ls /"})
    assert "outside the workspace" in tools.run("run_command", {"command": "ls ../"})
    assert "outside the workspace" in tools.run("run_command", {"command": "git diff --output=/tmp/x"})


def test_run_command_does_not_use_shell(workspace: Path):
    tools = WorkspaceTools(workspace, level="full", allowed_commands=["ls"])

    # 허용된 접두어 뒤의 ';' 'touch' 는 셸이 아니라 ls 의 인자로 전달될 뿐이다.
    out = tools.run("run_command", {"command": "ls . ; touch pwned"})
    assert not (workspace / "pwned").exists()
    assert out.startswith("[exit code")
    assert "not in allow list" in tools.run("run_command", {"command": "ls; touch pwned"})


def test_run_command_custom_allowlist_and_timeout(workspace: Path):
    tools = WorkspaceTools(
        workspace,
        level="full",
        allowed_commands=[f"{sys.executable} -c"],
        command_timeout=0.5,
    )

    out = tools.run("run_command", {"command": f"{sys.executable} -c 'import time; time.sleep(5)'"})
    assert out.startswith("[timed out after 0.5s]")


# ------------------------------------------------------------ config wiring
def test_create_adapter_passes_openrouter_options(workspace: Path):
    adapter = create_adapter(
        "openrouter",
        name="dev",
        default_args=[],
        model="m",
        tools="full",
        max_turns=7,
        allowed_commands=["pytest"],
        client=FakeClient([]),
    )
    assert isinstance(adapter, OpenRouterAgentAdapter)
    assert adapter.tools == "full" and adapter.max_turns == 7
    assert adapter.config_extras() == {"tools": "full", "max_turns": 7, "allowed_commands": ["pytest"]}


def test_openrouter_options_are_ignored_by_cli_adapters():
    adapter = create_adapter("claude", name="c", tools="full", max_turns=3)
    assert adapter.__class__.__name__ == "ClaudeCLIAdapter"


def test_agents_yaml_options_reach_adapter(tmp_path: Path, monkeypatch):
    from modue_harness.engine.interactive import load_or_detect_agents

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agents.yaml").write_text(
        "agents:\n"
        "  dev:\n"
        "    adapter: openrouter\n"
        "    model: qwen/qwen3-coder\n"
        "    tools: full\n"
        "    max_turns: 12\n"
        "    allowed_commands: [pytest]\n",
        encoding="utf-8",
    )
    agents = load_or_detect_agents(cwd=tmp_path)

    dev = agents["dev"]
    assert isinstance(dev, OpenRouterAgentAdapter)
    assert (dev.model, dev.tools, dev.max_turns, dev.allowed_commands) == ("qwen/qwen3-coder", "full", 12, ["pytest"])


def test_workflow_agent_options_reach_pipeline_adapter():
    from modue_harness.engine.workflow import WorkflowAgentConfig

    cfg = WorkflowAgentConfig.from_dict("dev", {"adapter": "openrouter", "model": "m", "tools": "full", "role": "x"})
    assert cfg.options == {"tools": "full"}


def test_save_agents_config_roundtrip(tmp_path: Path):
    import yaml

    from modue_harness.engine.interactive import InteractiveSession

    session = InteractiveSession.__new__(InteractiveSession)
    session.agents = {"dev": OpenRouterAgentAdapter(name="dev", model="m", tools="full", client=FakeClient([]))}
    session.conductor_name = "dev"
    session.agents_file = None
    target = tmp_path / "agents.yaml"

    session.save_agents_config(target)

    entry = yaml.safe_load(target.read_text(encoding="utf-8"))["agents"]["dev"]
    assert entry == {"adapter": "openrouter", "model": "m", "tools": "full"}


def test_openrouter_effort_normalization_and_fallback():
    # 1. Effort normalization: 'default' or 'off' must not send reasoning effort
    a_def = OpenRouterAgentAdapter(name="a", model="m", effort="default", client=FakeClient([]))
    kwargs_def = a_def._request_kwargs([], [], None)
    assert "reasoning" not in kwargs_def.get("extra_body", {})

    # 2. 'high' or 'max' mapped properly
    a_max = OpenRouterAgentAdapter(name="b", model="m", effort="max", client=FakeClient([]))
    kwargs_max = a_max._request_kwargs([], [], None)
    assert kwargs_max["extra_body"]["reasoning"] == {"effort": "high"}
