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


def test_cli_ui_command_missing_dep(capsys):
    """Test 'modue-harness ui' command prints installation instructions and exits 1."""
    ret = main(["ui", "-P", "testproj"])
    out, _ = capsys.readouterr()
    assert ret == 1
    assert "NiceGUI is not installed" in out or "pip install 'modue-harness[ui]'" in out


def test_cli_tui_command_missing_dep(capsys):
    """Test 'modue-harness tui' command prints installation instructions and exits 1."""
    ret = main(["tui", "-P", "testproj"])
    out, _ = capsys.readouterr()
    assert ret == 1
    assert "Textual is not installed" in out or "pip install 'modue-harness[ui]'" in out


def test_cli_flags_ui_and_tui(capsys):
    """Test '--ui' and '--tui' flags invoke handlers properly."""
    ret_ui = main(["--ui", "-P", "testproj"])
    out_ui, _ = capsys.readouterr()
    assert ret_ui == 1

    ret_tui = main(["--tui", "-P", "testproj"])
    out_tui, _ = capsys.readouterr()
    assert ret_tui == 1
