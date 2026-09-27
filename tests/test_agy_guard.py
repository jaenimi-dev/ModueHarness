"""Tests for the agy sandbox default, headless auto-denied detection, and agy-guard deny rules."""

import json
import sys
from pathlib import Path

import pytest

from modue_harness.adapters import AGYCLIAdapter, create_adapter
from modue_harness.adapters import agy_guard
from modue_harness.adapters.agy import detect_auto_denied
from modue_harness.core.types import TaskStatus, TurnContext, TurnResult

AUTO_DENIED = (
    'No output produced — a tool required the "write_file" permission that headless mode cannot '
    "prompt for, so it was auto-denied. Add an allow-rule under permissions.allow in settings.json"
)


# ------------------------------------------------------------------ sandbox flag
@pytest.mark.skipif(sys.platform == "win32", reason="sandbox is off by default on Windows")
def test_agy_adds_sandbox_by_default():
    cmd = AGYCLIAdapter(model="m").build_command("hi")
    assert "--sandbox" in cmd
    assert "--dangerously-skip-permissions" in cmd


def test_agy_sandbox_can_be_disabled_from_config():
    adapter = create_adapter("agy", sandbox=False)
    assert "--sandbox" not in adapter.build_command("hi")
    assert adapter.config_extras().get("sandbox") is False


def test_agy_sandbox_default_follows_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert AGYCLIAdapter().sandbox is False
    monkeypatch.setattr(sys, "platform", "linux")
    assert AGYCLIAdapter().sandbox is True


def test_sandbox_option_is_ignored_by_other_adapters():
    adapter = create_adapter("claude", sandbox=True)
    assert adapter.__class__.__name__ == "ClaudeCLIAdapter"


def test_agents_yaml_sandbox_reaches_agy_adapter(tmp_path: Path):
    from modue_harness.engine.interactive import load_or_detect_agents

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "agents.yaml").write_text(
        "agents:\n  dev:\n    adapter: agy\n    sandbox: false\n", encoding="utf-8"
    )
    agents = load_or_detect_agents(cwd=tmp_path)
    assert agents["dev"].sandbox is False


# ------------------------------------------------------------ auto-denied check
def test_detect_auto_denied_finds_notice_in_either_stream():
    assert detect_auto_denied("", AUTO_DENIED) is not None
    assert detect_auto_denied(AUTO_DENIED, "") is not None
    assert detect_auto_denied("all good", "") is None


def _python_echo_adapter(tmp_path: Path, text: str) -> AGYCLIAdapter:
    script = tmp_path / "fake_agy.py"
    script.write_text(f"import sys\nsys.stderr.write({text!r})\n", encoding="utf-8")
    adapter = AGYCLIAdapter(command=sys.executable, skip_permissions=False, sandbox=False)
    adapter.default_args = [str(script)]
    adapter.prompt_delivery = "stdin"
    return adapter


def _ctx(tmp_path: Path) -> TurnContext:
    return TurnContext(step_id="s", instruction="x", blackboard_dir=tmp_path, workspace_dir=tmp_path)


def test_auto_denied_turn_with_exit_zero_is_marked_failed(tmp_path: Path):
    result = _python_echo_adapter(tmp_path, AUTO_DENIED).execute(_ctx(tmp_path))

    assert result.status == TaskStatus.FAILED
    assert result.exit_code == 1
    assert "자동 거부" in result.error_message


def test_auto_denied_is_detected_in_stream_mode(tmp_path: Path):
    gen = _python_echo_adapter(tmp_path, AUTO_DENIED).execute_stream(_ctx(tmp_path))
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        result = stop.value
    assert result.status == TaskStatus.FAILED


def test_normal_agy_output_stays_successful(tmp_path: Path):
    result = _python_echo_adapter(tmp_path, "done\n").execute(_ctx(tmp_path))
    assert result.is_success


# ------------------------------------------------------------- auto guard
@pytest.fixture
def repo_run(tmp_path: Path, monkeypatch, isolated_agy_settings):
    """A harness-like root (cwd) with projects/p as the workspace and a fake agy binary."""
    root = tmp_path / "harness"
    ws = root / "projects" / "p"
    board = root / "blackboard" / "p"
    for d in (ws, board, root / "src", root / "tests"):
        d.mkdir(parents=True)
    monkeypatch.chdir(root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    script = tmp_path / "fake_agy.py"
    script.write_text("print('done')\n", encoding="utf-8")
    ctx = TurnContext(step_id="s", instruction="x", blackboard_dir=board, workspace_dir=ws)
    return root, ctx, script, isolated_agy_settings


def _fake_agy(script: Path, **kwargs) -> AGYCLIAdapter:
    adapter = AGYCLIAdapter(command=sys.executable, sandbox=False, **kwargs)
    adapter.default_args = [str(script)]
    adapter.prompt_delivery = "stdin"
    return adapter


def test_execute_auto_installs_guard_rules_once(repo_run, capsys):
    root, ctx, script, settings = repo_run
    adapter = _fake_agy(script)

    assert adapter.execute(ctx).is_success
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert f"write_file({(root / 'src').as_posix()})" in deny
    assert f"write_file({(root / 'tests').as_posix()})" in deny
    assert not any("/projects" in r or "/blackboard" in r for r in deny)
    assert "agy 보호 규칙" in capsys.readouterr().out

    # 두 번째 실행은 이미 설치돼 있으므로 파일을 바꾸지 않고 안내도 없다.
    mtime = settings.stat().st_mtime_ns
    assert adapter.execute(ctx).is_success
    assert settings.stat().st_mtime_ns == mtime
    assert capsys.readouterr().out == ""


def test_new_top_level_entry_is_guarded_on_next_run(repo_run):
    root, ctx, script, settings = repo_run
    adapter = _fake_agy(script)
    adapter.execute(ctx)

    (root / "newdir").mkdir()
    adapter.execute(ctx)

    assert f"write_file({(root / 'newdir').as_posix()})" in json.loads(settings.read_text())["permissions"]["deny"]


def test_auto_guard_in_stream_mode(repo_run):
    root, ctx, script, settings = repo_run
    gen = _fake_agy(script).execute_stream(ctx)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        assert stop.value.is_success
    assert settings.exists()


def test_auto_guard_can_be_disabled(repo_run):
    root, ctx, script, settings = repo_run
    adapter = create_adapter("agy", write_guard=False)
    assert adapter.config_extras().get("write_guard") is False
    adapter = _fake_agy(script, write_guard=False)

    assert adapter.execute(ctx).is_success
    assert not settings.exists()


def test_auto_guard_skipped_when_workspace_outside_cwd(repo_run, tmp_path: Path):
    root, ctx, script, settings = repo_run
    outside_ws = tmp_path / "elsewhere"
    outside_ws.mkdir()
    ctx.workspace_dir = outside_ws

    assert _fake_agy(script).execute(ctx).is_success
    assert not settings.exists()


def test_auto_guard_skipped_when_cwd_is_home(tmp_path: Path, monkeypatch, isolated_agy_settings):
    from modue_harness.adapters import agy_guard as g

    home = tmp_path / "home"
    (home / "projects" / "p").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    assert g.is_safe_guard_root(home, home / "projects" / "p") is False
    assert g.is_safe_guard_root(tmp_path, home / "projects" / "p") is False
    assert g.is_safe_guard_root(home / "projects", home / "projects" / "p") is True


def test_broken_settings_file_fails_the_turn(repo_run):
    root, ctx, script, settings = repo_run
    settings.write_text("{not json")

    result = _fake_agy(script).execute(ctx)

    assert result.status == TaskStatus.FAILED
    assert "write_guard: false" in result.error_message


def test_backup_keeps_the_original_settings(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"trustedWorkspaces": ["/w"]}))

    agy_guard.install_guard_rules(["write_file(/a)"], settings)
    agy_guard.install_guard_rules(["write_file(/b)"], settings)

    backup = json.loads((tmp_path / "settings.json.modue-backup").read_text())
    assert backup == {"trustedWorkspaces": ["/w"]}


def test_concurrent_ensure_loses_no_rules(tmp_path: Path):
    import threading

    settings = tmp_path / "settings.json"
    rule_sets = [[f"write_file(/r/{i})", "write_file(/shared)"] for i in range(8)]
    threads = [threading.Thread(target=agy_guard.ensure_guard_rules, args=(rs, settings)) for rs in rule_sets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert sorted(deny) == sorted({r for rs in rule_sets for r in rs})


# ------------------------------------------------------------------ guard rules
@pytest.fixture
def harness(tmp_path: Path) -> Path:
    root = tmp_path / "harness"
    for d in ("src", "tests", "projects", "blackboard", ".git"):
        (root / d).mkdir(parents=True)
    (root / "README.md").write_text("x", encoding="utf-8")
    return root


def test_build_guard_rules_protects_repo_but_not_workspaces(harness: Path, tmp_path: Path):
    rules = agy_guard.build_guard_rules(harness, home=tmp_path / "home")

    for name in ("src", "tests", ".git", "README.md"):
        assert f"write_file({(harness / name).as_posix()})" in rules
    assert not any("/projects)" in r or "/blackboard)" in r for r in rules)
    assert f"write_file({(tmp_path / 'home' / '.ssh').as_posix()})" in rules
    assert f"write_file({(tmp_path / 'home' / '.gemini/antigravity-cli/settings.json').as_posix()})" in rules


def test_build_guard_rules_skips_entries_containing_custom_allowed_dirs(harness: Path, tmp_path: Path):
    custom = harness / "work" / "projects"
    custom.mkdir(parents=True)

    rules = agy_guard.build_guard_rules(harness, allowed_dirs=[custom], home=tmp_path)

    assert f"write_file({(harness / 'work').as_posix()})" not in rules


def test_install_merges_backs_up_and_is_idempotent(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"trustedWorkspaces": ["/w"], "permissions": {"deny": ["command(sudo)"], "allow": ["command(git)"]}}))
    rules = ["write_file(/r/src)", "write_file(/r/tests)"]

    assert agy_guard.install_guard_rules(rules, settings) == rules
    data = json.loads(settings.read_text())
    assert data["trustedWorkspaces"] == ["/w"]
    assert data["permissions"]["allow"] == ["command(git)"]
    assert data["permissions"]["deny"] == ["command(sudo)"] + rules
    assert (tmp_path / "settings.json.modue-backup").exists()

    assert agy_guard.install_guard_rules(rules, settings) == []
    assert agy_guard.missing_guard_rules(rules, settings) == []


def test_install_creates_missing_settings_file(tmp_path: Path):
    settings = tmp_path / "sub" / "settings.json"
    agy_guard.install_guard_rules(["write_file(/r/src)"], settings)
    assert json.loads(settings.read_text())["permissions"]["deny"] == ["write_file(/r/src)"]


def test_uninstall_removes_only_guard_rules(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {"deny": ["command(sudo)", "write_file(/r/src)"]}}))

    assert agy_guard.uninstall_guard_rules(["write_file(/r/src)"], settings) == ["write_file(/r/src)"]
    assert json.loads(settings.read_text())["permissions"]["deny"] == ["command(sudo)"]


def test_missing_rules_when_settings_unreadable(tmp_path: Path):
    settings = tmp_path / "settings.json"
    settings.write_text("{not json")
    assert agy_guard.missing_guard_rules(["write_file(/r)"], settings) == ["write_file(/r)"]
    with pytest.raises(ValueError):
        agy_guard.install_guard_rules(["write_file(/r)"], settings)


# ---------------------------------------------------------------------- CLI
def test_cli_agy_guard_install_and_status(harness: Path, tmp_path: Path, monkeypatch, capsys):
    from modue_harness import cli

    settings = tmp_path / "agy" / "settings.json"
    monkeypatch.setattr(agy_guard, "AGY_SETTINGS_PATH", settings)
    monkeypatch.chdir(harness)

    assert cli.main(["agy-guard", "install"]) == 0
    deny = json.loads(settings.read_text())["permissions"]["deny"]
    assert f"write_file({(harness / 'src').as_posix()})" in deny

    capsys.readouterr()
    assert cli.main(["agy-guard"]) == 0
    out = capsys.readouterr().out
    assert f"{len(deny)}개 중 {len(deny)}개 설치됨" in out

    assert cli.main(["agy-guard", "uninstall"]) == 0
    assert json.loads(settings.read_text())["permissions"]["deny"] == []


def test_warning_only_for_agy_without_auto_guard(tmp_path: Path, monkeypatch, capsys):
    import argparse

    from modue_harness import cli

    monkeypatch.setattr(agy_guard, "AGY_SETTINGS_PATH", tmp_path / "missing.json")
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace()

    cli.warn_if_agy_guard_missing([create_adapter("claude")], args)
    assert capsys.readouterr().out == ""
    cli.warn_if_agy_guard_missing([AGYCLIAdapter(skip_permissions=False)], args)
    assert capsys.readouterr().out == ""
    cli.warn_if_agy_guard_missing([AGYCLIAdapter()], args)  # 자동 설치가 켜져 있으면 경고 불필요
    assert capsys.readouterr().out == ""
    cli.warn_if_agy_guard_missing([AGYCLIAdapter(write_guard=False)], args)
    assert "agy-guard install" in capsys.readouterr().out
