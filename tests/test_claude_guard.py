"""Tests for the per-run Claude Code write guard (--settings with Edit deny rules)."""

import json
import sys
from pathlib import Path

import pytest

from modue_harness.adapters import ClaudeCLIAdapter, create_adapter
from modue_harness.adapters import agy_guard
from modue_harness.core.types import TurnContext

# 가짜 claude: 받은 --settings 파일 경로와 내용을 JSON 으로 출력한다.
FAKE_CLAUDE = """
import json, sys
args = sys.argv[1:]
out = {"args": args, "settings": None, "path": None}
if "--settings" in args:
    path = args[args.index("--settings") + 1]
    out["path"] = path
    out["settings"] = json.load(open(path, encoding="utf-8"))
print(json.dumps(out))
"""


@pytest.fixture
def repo_run(tmp_path: Path, monkeypatch):
    root = tmp_path / "harness"
    ws = root / "projects" / "p"
    board = root / "blackboard" / "p"
    for d in (ws, board, root / "src", root / "tests"):
        d.mkdir(parents=True)
    monkeypatch.chdir(root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE_CLAUDE, encoding="utf-8")
    ctx = TurnContext(step_id="s", instruction="x", blackboard_dir=board, workspace_dir=ws)
    return root, ctx, script


def _fake_claude(script: Path, **kwargs) -> ClaudeCLIAdapter:
    adapter = ClaudeCLIAdapter(command=sys.executable, permission_mode="", **kwargs)
    adapter.default_args = [str(script)] + adapter.default_args
    return adapter


def _run(adapter: ClaudeCLIAdapter, ctx: TurnContext) -> dict:
    result = adapter.execute(ctx)
    assert result.is_success, result.error_message
    return json.loads(result.stdout)


@pytest.mark.skipif(sys.platform == "win32", reason="claude write guard is disabled on Windows")
def test_claude_gets_per_run_deny_rules_and_file_is_removed(repo_run):
    root, ctx, script = repo_run

    out = _run(_fake_claude(script), ctx)

    deny = out["settings"]["permissions"]["deny"]
    # Claude Code 절대 경로 규칙은 // 로 시작해야 한다.
    assert f"Edit(/{(root / 'src').as_posix()})" in deny
    assert f"Edit(/{(root / 'tests').as_posix()})" in deny
    assert all(r.startswith("Edit(//") for r in deny)
    assert not any("/projects" in r or "/blackboard" in r for r in deny)
    assert not Path(out["path"]).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="claude write guard is disabled on Windows")
def test_claude_guard_in_stream_mode(repo_run):
    root, ctx, script = repo_run
    gen = _fake_claude(script).execute_stream(ctx)
    lines = []
    try:
        while True:
            lines.append(next(gen))
    except StopIteration:
        pass
    out = json.loads("".join(lines))
    assert out["settings"]["permissions"]["deny"]
    assert not Path(out["path"]).exists()


def test_claude_guard_does_not_touch_global_settings(repo_run, isolated_agy_settings):
    root, ctx, script = repo_run
    _run(_fake_claude(script), ctx)
    assert not isolated_agy_settings.exists()


def test_claude_guard_can_be_disabled(repo_run):
    root, ctx, script = repo_run
    adapter = _fake_claude(script, write_guard=False)

    assert _run(adapter, ctx)["settings"] is None
    assert adapter.config_extras() == {"write_guard": False}
    assert create_adapter("claude", write_guard=False).write_guard is False


def test_claude_guard_skipped_when_user_passes_settings(repo_run, tmp_path: Path):
    root, ctx, script = repo_run
    own = tmp_path / "own.json"
    own.write_text("{}", encoding="utf-8")
    adapter = _fake_claude(script)
    adapter.default_args += ["--settings", str(own)]

    out = _run(adapter, ctx)

    assert out["args"].count("--settings") == 1
    assert out["path"] == str(own)


def test_claude_guard_skipped_when_workspace_outside_cwd(repo_run, tmp_path: Path):
    root, ctx, script = repo_run
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    ctx.workspace_dir = elsewhere

    assert _run(_fake_claude(script), ctx)["settings"] is None


def test_claude_rules_share_paths_with_agy_rules(tmp_path: Path):
    root = tmp_path / "r"
    (root / "src").mkdir(parents=True)
    agy = agy_guard.build_guard_rules(root, home=tmp_path)
    claude = agy_guard.build_claude_deny_rules(root, home=tmp_path)
    assert [r[len("write_file("):] for r in agy] == [r[len("Edit(/"):] for r in claude]
