"""Unit tests for ModueHarness UI Controller, Web UI, TUI, and CLI UI commands."""

import io
from pathlib import Path
import sys
import pytest

from modue_harness.cli import main
from modue_harness.core.blackboard import Blackboard, Task, TaskStatus
from modue_harness.ui.controller import UIController
from modue_harness.ui.web.app import run_app
from modue_harness.ui.tui.app import run_tui_app


def test_ui_controller_basic(tmp_path: Path):
    """Test UIController initialization and basic properties."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="alpha",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        timeout=30.0,
    )

    assert ctrl.project_name == "alpha"
    assert ctrl.project_dir == projects_dir / "alpha"
    assert ctrl.blackboard_dir == board_dir
    assert ctrl.timeout == 30.0

    # Status check
    status = ctrl.get_status()
    assert status["project_name"] == "alpha"
    assert status["timeout"] == 30.0
    assert status["running_jobs_count"] == 0


def test_ui_controller_project_switching_and_files(tmp_path: Path):
    """Test switching projects and inspecting project files."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="proj1",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    p1_dir = projects_dir / "proj1"
    p1_dir.mkdir(parents=True, exist_ok=True)
    (p1_dir / "main.py").write_text("print('hello')", encoding="utf-8")

    assert "main.py" in ctrl.get_project_files()
    assert ctrl.get_project_file_content("main.py") == "print('hello')"

    # Switch project
    ctrl.switch_project("proj2")
    assert ctrl.project_name == "proj2"
    p2_dir = projects_dir / "proj2"
    assert p2_dir.exists()


def test_ui_controller_artifacts_and_tasks(tmp_path: Path):
    """Test reading artifacts and tasks via UIController."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    board = Blackboard(root_dir=board_dir)
    board.initialize()
    board.write_artifact("notes.md", "# Test Notes\nContent here.")

    t = Task(
        id="task-1",
        title="Sample task",
        assigned_agent="claude",
        status=TaskStatus.IN_PROGRESS,
        description="do something",
    )
    board.create_task(t)

    ctrl = UIController(
        project_name="demo",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    artifacts = ctrl.get_artifacts()
    assert any(a["name"] == "notes.md" for a in artifacts)
    assert "# Test Notes" in ctrl.get_artifact_content("notes.md")

    tasks = ctrl.get_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == "task-1"
    assert tasks[0]["assigned_agent"] == "claude"
    assert tasks[0]["status"] == "in_progress"


def test_ui_controller_dynamic_settings(tmp_path: Path):
    """Test updating model, effort, timeout via UIController."""
    ctrl = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
    )

    ctrl.set_timeout(45.0)
    assert ctrl.timeout == 45.0

    ctrl.set_timeout(None)
    assert ctrl.timeout is None

    agents = ctrl.get_agents_info()
    assert isinstance(agents, list)
    assert len(agents) >= 1


def test_web_app_missing_dependency(monkeypatch):
    """Test run_app raises informative ImportError when nicegui is missing."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("nicegui"):
            raise ImportError("No module named 'nicegui'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(ImportError) as excinfo:
        run_app()
    assert "NiceGUI is not installed" in str(excinfo.value)


def test_tui_app_missing_dependency(monkeypatch):
    """Test run_tui_app raises informative ImportError when textual is missing."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("textual"):
            raise ImportError("No module named 'textual'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(ImportError) as excinfo:
        run_tui_app()
    assert "Textual is not installed" in str(excinfo.value)


def test_cli_ui_command_missing_dep(monkeypatch, capsys):
    """Test 'modue-harness ui' command prints installation instructions and exits 1."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("nicegui"):
            raise ImportError("No module named 'nicegui'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    ret = main(["ui", "-P", "testproj"])
    out, _ = capsys.readouterr()
    assert ret == 1
    assert "NiceGUI is not installed" in out or "pip install 'modue-harness[ui]'" in out


def test_cli_ui_command_success(monkeypatch):
    """Test 'modue-harness ui' calls run_app successfully."""
    from unittest.mock import MagicMock
    mock_run = MagicMock()
    monkeypatch.setattr("modue_harness.ui.web.app.run_app", mock_run)

    ret = main(["ui", "-P", "myproj", "--port", "9001", "--no-browser"])
    assert ret == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["port"] == 9001
    assert mock_run.call_args[1]["open_browser"] is False


def test_cli_ui_keyboard_interrupt(monkeypatch, capsys):
    """Test 'modue-harness ui' gracefully handles KeyboardInterrupt."""
    def mock_run_app(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr("modue_harness.ui.web.app.run_app", mock_run_app)
    ret = main(["ui", "-P", "myproj"])
    out, _ = capsys.readouterr()
    assert ret == 0
    assert "정상 종료되었습니다" in out


def test_cli_tui_command_missing_dep(capsys):
    """Test 'modue-harness tui' command prints installation instructions and exits 1."""
    ret = main(["tui", "-P", "testproj"])
    out, _ = capsys.readouterr()
    assert ret == 1
    assert "Textual is not installed" in out or "pip install 'modue-harness[ui]'" in out


def test_cli_flags_ui_and_tui(monkeypatch, capsys):
    """Test '--ui' and '--tui' flags invoke handlers properly."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name.startswith("nicegui") or name.startswith("textual"):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    ret_ui = main(["--ui", "-P", "testproj"])
    out_ui, _ = capsys.readouterr()
    assert ret_ui == 1

    ret_tui = main(["--tui", "-P", "testproj"])
    out_tui, _ = capsys.readouterr()
    assert ret_tui == 1


def test_web_app_runs_with_mock_nicegui_with_root(monkeypatch):
    """Test run_app passes root when ui.run accepts root."""
    from unittest.mock import MagicMock

    mock_ui = MagicMock()
    mock_app = MagicMock()

    called_args = {}
    def fake_run(root=None, **kwargs):
        called_args["root"] = root
        called_args.update(kwargs)

    mock_ui.run = fake_run
    monkeypatch.setitem(sys.modules, "nicegui", MagicMock(ui=mock_ui, app=mock_app))

    run_app(open_browser=False)
    assert called_args.get("reload") is False
    assert called_args.get("show") is False
    assert callable(called_args.get("root"))


def test_web_app_runs_with_mock_nicegui_fallback_page(monkeypatch):
    """Test run_app falls back to ui.page('/') when ui.run does not accept root."""
    from unittest.mock import MagicMock

    mock_ui = MagicMock()
    mock_app = MagicMock()

    called_args = {}
    def fake_run(**kwargs):
        called_args.update(kwargs)

    mock_ui.run = fake_run
    monkeypatch.setitem(sys.modules, "nicegui", MagicMock(ui=mock_ui, app=mock_app))

    run_app(open_browser=False)
    assert called_args.get("reload") is False
    mock_ui.page.assert_called_with("/")


def test_ui_controller_agent_crud_and_conductor(tmp_path: Path):
    """Test dynamic agent CRUD operations and setting conductor in UIController."""
    ctrl = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
    )

    # 1. Add agent
    res = ctrl.add_agent("qa_tester", adapter_type="claude", model="sonnet", effort="high")
    assert res["success"] is True
    agents = ctrl.get_agents_info()
    qa = next((a for a in agents if a["name"] == "qa_tester"), None)
    assert qa is not None
    assert qa["adapter"] == "claude"
    assert qa["model"] == "sonnet"
    assert qa["effort"] == "high"

    # 2. Update agent (switch adapter to agy and set leader)
    updated = ctrl.update_agent("qa_tester", adapter_type="agy", model="gemini-3.8-flash-high", is_conductor=True)
    assert updated is True
    agents_after = ctrl.get_agents_info()
    qa_after = next(a for a in agents_after if a["name"] == "qa_tester")
    assert qa_after["adapter"] == "agy"
    assert qa_after["model"] == "gemini-3.8-flash-high"
    assert qa_after["is_leader"] is True

    # 3. Set conductor explicitly
    first_agent = agents_after[0]["name"]
    ctrl.set_conductor(first_agent)
    agents_leader = ctrl.get_agents_info()
    assert any(a["name"] == first_agent and a["is_leader"] for a in agents_leader)

    # 4. Remove agent
    assert ctrl.remove_agent("qa_tester") is True
    agents_rem = ctrl.get_agents_info()
    assert not any(a["name"] == "qa_tester" for a in agents_rem)


def test_i18n_module_translations():
    """Test i18n translations consistency and formatting."""
    from modue_harness.ui.i18n import I18n, SUPPORTED_LANGUAGES, TRANSLATIONS, get_text

    assert "ko" in SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES

    # Ensure all English keys exist in Korean
    en_keys = set(TRANSLATIONS["en"].keys())
    ko_keys = set(TRANSLATIONS["ko"].keys())
    assert en_keys == ko_keys

    # Check basic translation and formatting
    ko_text = get_text("notify_agent_removed", lang="ko", name="bot1")
    assert "bot1" in ko_text
    assert "삭제되었습니다" in ko_text

    en_text = get_text("notify_agent_removed", lang="en", name="bot1")
    assert "bot1" in en_text
    assert "Removed agent" in en_text

    # Check fallback for unknown key
    assert get_text("non_existent_key", lang="ko") == "non_existent_key"

    # Check I18n class
    i18n = I18n(lang="ko")
    assert i18n.lang == "ko"
    assert "대시보드" in i18n("app_title")
    i18n.lang = "en"
    assert i18n.lang == "en"
    assert "Dashboard" in i18n("app_title")


def test_ui_controller_language_setting(tmp_path: Path):
    """Test UIController language initialization."""
    ctrl_ko = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
        lang="ko",
    )
    assert ctrl_ko.lang == "ko"

    ctrl_en = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
        lang="en",
    )
    assert ctrl_en.lang == "en"


def test_cli_ui_command_language_flags(monkeypatch):
    """Test 'modue-harness ui --lang en' passes language to run_app."""
    from unittest.mock import MagicMock
    mock_run = MagicMock()
    monkeypatch.setattr("modue_harness.ui.web.app.run_app", mock_run)

    ret = main(["ui", "-P", "myproj", "--lang", "en"])
    assert ret == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["lang"] == "en"

    mock_run.reset_mock()
    ret_ko = main(["ui", "-P", "myproj", "-L", "ko"])
    assert ret_ko == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["lang"] == "ko"

