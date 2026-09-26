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
    assert ctrl.blackboard_dir == board_dir / "alpha"
    assert ctrl.blackboard_root == board_dir
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


def test_ui_controller_project_deletion(tmp_path: Path):
    """Test deleting a project via UIController and CLI."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="to_delete",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )
    ctrl.switch_project("keep_me")
    ctrl.switch_project("to_delete")

    assert (projects_dir / "to_delete").exists()
    assert (board_dir / "to_delete").exists()
    assert "to_delete" in ctrl.get_projects()

    # Delete project
    success = ctrl.delete_project("to_delete")
    assert success is True
    assert not (projects_dir / "to_delete").exists()
    assert not (board_dir / "to_delete").exists()
    assert "to_delete" not in ctrl.get_projects()
    # It should have switched to keep_me
    assert ctrl.project_name == "keep_me"

    # Test CLI projects --delete
    (projects_dir / "cli_del").mkdir(parents=True, exist_ok=True)
    (board_dir / "cli_del").mkdir(parents=True, exist_ok=True)
    ret = main(["projects", "--projects-dir", str(projects_dir), "--dir", str(board_dir), "--delete", "cli_del"])
    assert ret == 0
    assert not (projects_dir / "cli_del").exists()


def test_ui_controller_artifacts_and_tasks(tmp_path: Path):
    """Test reading artifacts and tasks via UIController."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    board = Blackboard(root_dir=board_dir, project="demo")
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

    # Verify OpenRouter adapter model retrieval and agent recognition
    models = ctrl.get_adapter_models("openrouter")
    assert isinstance(models, list)
    assert len(models) >= 1
    assert any("claude" in m["id"] or "gpt" in m["id"] or "qwen" in m["id"] for m in models)

    # Test adding an openrouter agent
    ctrl.add_agent(
        name="or_coder",
        adapter_type="openrouter",
        model="qwen/qwen3-coder",
    )
    agents_after = ctrl.get_agents_info()
    or_agent = next((a for a in agents_after if a["name"] == "or_coder"), None)
    assert or_agent is not None
    assert or_agent["adapter"] == "openrouter"
    assert or_agent["model"] == "qwen/qwen3-coder"


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

    # 2b. Switch adapter to codex with gpt-5.6-terra
    updated_codex = ctrl.update_agent("qa_tester", adapter_type="codex", model="gpt-5.6-terra")
    assert updated_codex is True
    qa_codex = next(a for a in ctrl.get_agents_info() if a["name"] == "qa_tester")
    assert qa_codex["adapter"] == "codex"
    assert qa_codex["model"] == "gpt-5.6-terra"

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


def test_ui_controller_agent_config_persistence(tmp_path: Path):
    """Test modifying AI agents in UI persists to config YAML, not modifying code."""
    import yaml

    config_file = tmp_path / "config" / "agents.yaml"
    ctrl = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
        agents_file=config_file,
    )

    # 1. Update an agent
    first_agent = ctrl.get_agents_info()[0]["name"]
    ctrl.update_agent(first_agent, model="claude-3-7-sonnet", effort="high")

    assert config_file.exists(), "Configuration file must be created/updated!"
    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "agents" in data
    assert first_agent in data["agents"]
    assert data["agents"][first_agent]["model"] == "claude-3-7-sonnet"
    assert data["agents"][first_agent]["effort"] == "high"

    # 2. Add a new agent
    ctrl.add_agent("security_auditor", adapter_type="claude", model="opus")
    with open(config_file, "r", encoding="utf-8") as f:
        data2 = yaml.safe_load(f)
    assert "security_auditor" in data2["agents"]
    assert data2["agents"]["security_auditor"]["model"] == "opus"


def test_ui_controller_project_artifacts_isolation(tmp_path: Path):
    """Test switching projects switches the artifacts view accordingly."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    board = Blackboard(root_dir=board_dir)
    board.initialize()

    # Project A writes an artifact with metadata
    board.write_artifact("plan_a.md", "# Project A Plan", metadata={"project": "projA"})

    ctrl = UIController(
        project_name="projA",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    # In projA: plan_a.md is listed and readable
    arts_a = ctrl.get_artifacts()
    assert len(arts_a) == 1
    assert arts_a[0]["name"] == "plan_a.md"
    assert ctrl.get_artifact_content("plan_a.md") == "# Project A Plan"

    # Switch to projB: plan_a.md should NOT be listed for projB!
    ctrl.switch_project("projB")
    arts_b = ctrl.get_artifacts()
    assert len(arts_b) == 0

    # Project B writes its own artifact
    board.write_artifact("plan_b.md", "# Project B Plan", metadata={"project": "projB"})
    arts_b_after = ctrl.get_artifacts()
    assert len(arts_b_after) == 1
    assert arts_b_after[0]["name"] == "plan_b.md"
    assert ctrl.get_artifact_content("plan_b.md") == "# Project B Plan"

    # Switch back to projA
    ctrl.switch_project("projA")
    arts_a_again = ctrl.get_artifacts()
    assert len(arts_a_again) == 1
    assert arts_a_again[0]["name"] == "plan_a.md"


def test_corrupt_artifact_metadata_and_windows_paths(tmp_path: Path):
    """Test that Blackboard and UIController safely handle corrupt .meta.json and Windows paths."""
    board_dir = tmp_path / "blackboard"
    board = Blackboard(root_dir=board_dir)
    board.initialize()

    # 1. Normal artifact
    board.write_artifact("valid.md", "valid content")

    # 2. Corrupt .meta.json
    corrupt_meta = board.artifacts_dir / ".valid.md.meta.json"
    corrupt_meta.write_text("NOT_JSON{", encoding="utf-8")

    assert board.read_artifact_metadata("valid.md") is None

    # 3. UTF-8 with BOM .meta.json (exact Windows Notepad / PowerShell behavior)
    bom_meta = board.artifacts_dir / ".bom.md.meta.json"
    bom_meta.write_bytes(b'\xef\xbb\xbf{"path": "bom.md", "custom": {"project": "default"}}')
    (board.artifacts_dir / "bom.md").write_bytes(b'\xef\xbb\xbf# BOM Document')

    meta = board.read_artifact_metadata("bom.md")
    assert meta is not None
    assert meta.get("custom", {}).get("project") == "default"
    assert "BOM Document" in board.read_artifact("bom.md")

    # 4. Windows path resolution test
    resolved = board.resolve_artifact_path("blackboard\\artifacts\\subdir\\test.txt")
    assert resolved == board.artifacts_dir / "subdir" / "test.txt"

    # 5. Controller get_artifacts with corrupt and BOM metadata should not crash
    ctrl = UIController(project_name="default", blackboard_dir=board_dir, projects_root=tmp_path / "projects")
    artifacts = ctrl.get_artifacts()
    # bom.md was tagged with project='default' so it is in matched artifacts for default project
    assert any(a["name"] == "bom.md" for a in artifacts)
    assert "BOM Document" in ctrl.get_artifact_content("bom.md")


def test_ui_controller_posix_paths(tmp_path: Path):
    """Test that file paths are normalized to POSIX style (forward slashes)."""
    projects_dir = tmp_path / "projects"
    p_dir = projects_dir / "myproj"
    (p_dir / "sub" / "deep").mkdir(parents=True, exist_ok=True)
    (p_dir / "sub" / "deep" / "module.py").write_text("x = 1", encoding="utf-8")

    ctrl = UIController(
        project_name="myproj",
        projects_root=projects_dir,
        blackboard_dir=tmp_path / "blackboard",
    )

    files = ctrl.get_project_files()
    assert "sub/deep/module.py" in files
    assert "\\" not in files[0]

    # Content retrieval with posix path
    content = ctrl.get_project_file_content("sub/deep/module.py")
    assert content == "x = 1"


def test_web_app_error_boundary(monkeypatch):
    """Test that run_app's build_dashboard handles unexpected errors gracefully without crashing."""
    import sys
    from unittest.mock import MagicMock

    mock_ui = MagicMock()
    mock_app = MagicMock()

    registered_page_func = None

    def fake_page(path):
        def decorator(fn):
            nonlocal registered_page_func
            registered_page_func = fn
            return fn
        return decorator

    mock_ui.page = fake_page

    def fake_run(root=None, **kwargs):
        pass

    mock_ui.run = fake_run
    monkeypatch.setitem(sys.modules, "nicegui", MagicMock(ui=mock_ui, app=mock_app))

    run_app(open_browser=False)

    assert registered_page_func is not None

    # Mock _build_dashboard_impl raising an error
    monkeypatch.setattr(
        "modue_harness.ui.web.app.UIController.get_projects",
        MagicMock(side_effect=RuntimeError("Simulated Controller Crash")),
    )

    # Calling the page function should not raise an unhandled exception
    try:
        registered_page_func()
    except Exception as e:
        pytest.fail(f"build_dashboard raised an unhandled exception: {e}")


def test_project_isolated_blackboards(tmp_path: Path):
    """Verify that multiple projects maintain isolated subfolders under blackboard/."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="project_alpha",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    # Initial state: project_alpha isolated blackboard folder
    assert ctrl.blackboard_dir == board_dir / "project_alpha"
    assert ctrl.blackboard_root == board_dir

    # Project Alpha writes artifact and task
    ctrl.session.blackboard.initialize()
    ctrl.session.blackboard.write_artifact("spec.md", "# Alpha Specification")
    t_a = Task(
        id="task_alpha_1",
        title="Alpha Task",
        assigned_agent="developer",
        status=TaskStatus.COMPLETED,
        description="Build Alpha",
    )
    ctrl.session.blackboard.create_task(t_a)

    # Verify Project Alpha files on disk
    assert (board_dir / "project_alpha" / "artifacts" / "spec.md").exists()
    assert (board_dir / "project_alpha" / "tasks" / "task_alpha_1.json").exists()

    # Query via UIController in project_alpha
    arts_a = ctrl.get_artifacts()
    assert len(arts_a) == 1
    assert arts_a[0]["name"] == "spec.md"
    assert ctrl.get_artifact_content("spec.md") == "# Alpha Specification"
    tasks_a = ctrl.get_tasks()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == "task_alpha_1"

    # Switch to Project Beta
    ctrl.switch_project("project_beta")
    assert ctrl.project_name == "project_beta"
    assert ctrl.blackboard_dir == board_dir / "project_beta"

    # In Project Beta: Alpha's artifacts and tasks must NOT be visible
    arts_b = ctrl.get_artifacts()
    assert len(arts_b) == 0
    tasks_b = ctrl.get_tasks()
    assert len(tasks_b) == 0

    # Project Beta writes its own artifact and task
    ctrl.session.blackboard.write_artifact("spec.md", "# Beta Specification")
    t_b = Task(
        id="task_beta_1",
        title="Beta Task",
        assigned_agent="developer",
        status=TaskStatus.IN_PROGRESS,
        description="Build Beta",
    )
    ctrl.session.blackboard.create_task(t_b)

    # Verify Project Beta files on disk
    assert (board_dir / "project_beta" / "artifacts" / "spec.md").exists()
    assert (board_dir / "project_beta" / "tasks" / "task_beta_1.json").exists()

    # Verify query in project_beta
    arts_b_after = ctrl.get_artifacts()
    assert len(arts_b_after) == 1
    assert arts_b_after[0]["name"] == "spec.md"
    assert ctrl.get_artifact_content("spec.md") == "# Beta Specification"
    tasks_b_after = ctrl.get_tasks()
    assert len(tasks_b_after) == 1
    assert tasks_b_after[0]["id"] == "task_beta_1"

    # Switch back to Project Alpha: must see only Alpha's contents
    ctrl.switch_project("project_alpha")
    arts_a_again = ctrl.get_artifacts()
    assert len(arts_a_again) == 1
    assert ctrl.get_artifact_content("spec.md") == "# Alpha Specification"
    tasks_a_again = ctrl.get_tasks()
    assert len(tasks_a_again) == 1
    assert tasks_a_again[0]["id"] == "task_alpha_1"

    # Root blackboard inspection should discover both subprojects without collisions
    root_board = Blackboard(root_dir=board_dir)
    assert root_board.has_artifact("spec.md")
    all_tasks = root_board.list_tasks()
    assert len(all_tasks) == 2
    task_ids = {t.id for t in all_tasks}
    assert "task_alpha_1" in task_ids
    assert "task_beta_1" in task_ids

    # Projects discovery lists both projects
    all_projects = ctrl.get_projects()
    assert "project_alpha" in all_projects
    assert "project_beta" in all_projects


def test_no_default_project_created_automatically(tmp_path: Path):
    """Verify that launching session or UIController without arguments does not create a 'default' folder."""
    from modue_harness.engine.interactive import InteractiveSession

    proj_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    # Session initialized with None project_name
    session = InteractiveSession(
        project_name=None,
        projects_root=proj_root,
        blackboard_dir=board_root,
    )
    assert session.project_name is None
    assert session.project_dir is None
    assert session.blackboard_dir is None

    # Should not create default folders on disk
    assert not (proj_root / "default").exists()
    assert not (board_root / "default").exists()

    # Controller initialized with None project_name
    ctrl = UIController(
        project_name=None,
        projects_root=proj_root,
        blackboard_dir=board_root,
    )
    assert ctrl.project_name is None
    assert ctrl.get_projects() == []
    assert ctrl.get_artifacts() == []
    assert ctrl.get_tasks() == []
    assert ctrl.get_project_files() == []

    # Status summary should be safe and healthy
    status = ctrl.get_status()
    assert status["project_name"] == "None"

    # Switching to a newly named project creates project dynamically without touching 'default'
    ctrl.switch_project("my_web_app")
    assert ctrl.project_name == "my_web_app"
    assert (proj_root / "my_web_app").exists()
    assert (board_root / "my_web_app").exists()
    assert not (proj_root / "default").exists()
    assert not (board_root / "default").exists()


def test_ui_controller_dynamic_refresh_on_new_files(tmp_path: Path):
    """Test that UIController immediately detects new files and artifacts on disk without restart."""
    proj_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="app_test",
        projects_root=proj_root,
        blackboard_dir=board_root,
    )
    ctrl.session.project_dir.mkdir(parents=True, exist_ok=True)
    ctrl.session.blackboard.initialize()

    # 1. Initially empty
    assert ctrl.get_project_files() == []
    assert ctrl.get_artifacts() == []

    # 2. External creation of project file
    new_code_file = ctrl.session.project_dir / "service.py"
    new_code_file.write_text("def hello(): return 'world'", encoding="utf-8")

    # Dynamic refresh: should immediately discover service.py and its content
    files = ctrl.get_project_files()
    assert "service.py" in files
    assert "hello()" in ctrl.get_project_file_content("service.py")

    # 3. External modification of project file
    new_code_file.write_text("def hello(): return 'updated'", encoding="utf-8")
    assert "updated" in ctrl.get_project_file_content("service.py")

    # 4. External creation of blackboard artifact
    art_file = ctrl.session.blackboard.artifacts_dir / "spec.md"
    art_file.write_text("# Spec Document v1", encoding="utf-8")

    # Dynamic refresh: should immediately discover spec.md and its content
    artifacts = ctrl.get_artifacts()
    assert any(a["name"] == "spec.md" for a in artifacts)
    assert "# Spec Document v1" in ctrl.get_artifact_content("spec.md")

    # 5. External modification of artifact
    art_file.write_text("# Spec Document v2", encoding="utf-8")
    assert "# Spec Document v2" in ctrl.get_artifact_content("spec.md")


def test_ui_controller_execute_command_streaming_progress(tmp_path: Path):
    """Test that UIController.execute_command delivers real-time formatted log lines via on_progress."""
    import json
    from modue_harness.adapters.generic import GenericCLIAdapter

    proj_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    tasks_json = json.dumps([
        {
            "id": "task-ui-1",
            "assigned_agent": "developer",
            "instruction": "Create main UI script",
            "output_artifact": "app.py",
        }
    ])

    conductor = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"import sys; content = sys.stdin.read(); print('{tasks_json}' if 'decompose' in content else 'REPORT: DONE')"],
    )
    dev = GenericCLIAdapter(
        name="developer",
        command=sys.executable,
        default_args=["-c", "print('hello from dev')"],
    )

    ctrl = UIController(
        project_name="stream_proj",
        projects_root=proj_root,
        blackboard_dir=board_root,
        agents={"conductor": conductor, "developer": dev},
    )

    received_events = []
    received_lines = []

    def on_progress(event: str, data: dict):
        received_events.append(event)
        if "lines" in data:
            received_lines.extend(data["lines"])

    res = ctrl.execute_command("Create app", on_progress=on_progress)
    assert res["success"] is True

    # Check that key phases were reported
    assert "planning_start" in received_events
    assert "planning_end" in received_events
    assert "task_start" in received_events
    assert "task_end" in received_events
    assert "synthesis_start" in received_events
    assert "synthesis_end" in received_events

    # Check formatted lines
    combined_log = "\n".join(received_lines)
    assert "[1/3] 🧠 Conductor" in combined_log
    assert "기획 완료" in combined_log
    assert "[2/3] 🛠️" in combined_log
    assert "[task-ui-1]" in combined_log
    assert "[3/3] 📝 Conductor" in combined_log

    # Tasks should now be available via ctrl.get_tasks()
    tasks = ctrl.get_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == "task-ui-1"
    assert tasks[0]["status"] == "completed"
    assert tasks[0]["assigned_agent"] == "developer"
    assert tasks[0]["instruction"] == "Create main UI script"


def test_ui_controller_execute_command_async_logs(tmp_path: Path):
    """Test that UIController.execute_command_async records live progress in job.logs and get_jobs()."""
    import json
    import time
    from modue_harness.adapters.generic import GenericCLIAdapter

    proj_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    tasks_json = json.dumps([
        {
            "id": "task-bg-1",
            "assigned_agent": "developer",
            "instruction": "Run background task",
            "output_artifact": "result.txt",
        }
    ])

    conductor = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"import sys; content = sys.stdin.read(); print('{tasks_json}' if 'decompose' in content else 'REPORT: DONE')"],
    )
    dev = GenericCLIAdapter(
        name="developer",
        command=sys.executable,
        default_args=["-c", "print('bg executed')"],
    )

    ctrl = UIController(
        project_name="async_proj",
        projects_root=proj_root,
        blackboard_dir=board_root,
        agents={"conductor": conductor, "developer": dev},
    )

    job = ctrl.execute_command_async("Build in background")
    assert job.id == "job_1"

    # Wait for completion
    timeout_sec = 10.0
    start = time.time()
    while job.status == "running" and (time.time() - start) < timeout_sec:
        time.sleep(0.05)

    assert job.status == "completed"
    assert len(job.logs) > 0

    combined_logs = "\n".join(job.logs)
    assert "[1/3] 🧠 Conductor" in combined_logs
    assert "기획 완료" in combined_logs
    assert "[2/3] 🛠️" in combined_logs
    assert "[task-bg-1]" in combined_logs
    assert "작업 완료" in combined_logs

    jobs = ctrl.get_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job_1"
    assert jobs[0]["status"] == "completed"
    assert jobs[0]["logs"] == job.logs


def test_project_switch_auto_refreshes_tasks_and_artifacts(tmp_path: Path):
    """Test that switching projects isolates and automatically refreshes tasks and artifacts."""
    proj_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    # Set up project A with an artifact and task
    ctrl = UIController(
        project_name="proj_a",
        projects_root=proj_root,
        blackboard_dir=board_root,
    )
    ctrl.session.project_dir.mkdir(parents=True, exist_ok=True)
    ctrl.session.blackboard.initialize()
    ctrl.session.blackboard.write_artifact("spec_a.md", "# Specification A")
    ctrl.session.blackboard.create_task(Task(
        id="task_a",
        title="Task A",
        assigned_agent="developer",
        status=TaskStatus.COMPLETED,
        description="Do work on A",
        output_artifact="spec_a.md",
    ))

    # Set up project B on disk with different artifact and task
    board_b = Blackboard(root_dir=board_root, project="proj_b")
    board_b.initialize()
    board_b.write_artifact("spec_b.md", "# Specification B")
    board_b.create_task(Task(
        id="task_b",
        title="Task B",
        assigned_agent="reviewer",
        status=TaskStatus.IN_PROGRESS,
        description="Review B",
        output_artifact="spec_b.md",
    ))

    # Currently on proj_a
    tasks_a = ctrl.get_tasks()
    arts_a = ctrl.get_artifacts()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == "task_a"
    assert any(a["name"] == "spec_a.md" for a in arts_a)
    assert not any(a["name"] == "spec_b.md" for a in arts_a)

    # Switch project to proj_b
    ctrl.switch_project("proj_b")
    tasks_b = ctrl.get_tasks()
    arts_b = ctrl.get_artifacts()

    # Must immediately and automatically reflect proj_b tasks & artifacts
    assert len(tasks_b) == 1
    assert tasks_b[0]["id"] == "task_b"
    assert tasks_b[0]["assigned_agent"] == "reviewer"
    assert any(a["name"] == "spec_b.md" for a in arts_b)
    assert not any(a["name"] == "spec_a.md" for a in arts_b)

    # Switch back to proj_a
    ctrl.switch_project("proj_a")
    tasks_a_again = ctrl.get_tasks()
    arts_a_again = ctrl.get_artifacts()
    assert len(tasks_a_again) == 1
    assert tasks_a_again[0]["id"] == "task_a"
    assert any(a["name"] == "spec_a.md" for a in arts_a_again)
    assert not any(a["name"] == "spec_b.md" for a in arts_a_again)


def test_job_history_populated_and_persisted(tmp_path: Path):
    """Test that task executions are tracked in get_jobs() and persisted on blackboard."""
    projects_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="job_demo",
        projects_root=projects_root,
        blackboard_dir=board_root,
    )

    # Initial jobs should be empty
    assert len(ctrl.get_jobs()) == 0

    # Save a mock job directly to blackboard
    job_dict = {
        "id": "job_1",
        "command": "build login page",
        "project": "job_demo",
        "status": "completed",
        "stage": "완료 (done)",
        "started_at": 1000.0,
        "ended_at": 1005.0,
        "duration_sec": 5.0,
        "error": None,
        "logs": ["Planning started", "Task completed"],
    }
    ctrl.session.blackboard.save_job(job_dict)

    # Must be returned by ctrl.get_jobs()
    jobs = ctrl.get_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == "job_1"
    assert jobs[0]["command"] == "build login page"
    assert jobs[0]["status"] == "completed"

    # Now create a new controller pointing to same storage - must still find the job
    ctrl2 = UIController(
        project_name="job_demo",
        projects_root=projects_root,
        blackboard_dir=board_root,
    )
    jobs2 = ctrl2.get_jobs()
    assert len(jobs2) == 1
    assert jobs2[0]["id"] == "job_1"


def test_job_cancellation_flow(tmp_path: Path):
    """Test that ctrl.cancel_job() cancels active running jobs and updates status."""
    projects_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="cancel_demo",
        projects_root=projects_root,
        blackboard_dir=board_root,
    )

    # Submit an async job with an echo command
    job = ctrl.execute_command_async("echo 'running'")
    assert job.status in ("running", "completed")

    # Cancel the job
    ctrl.cancel_job(job.id)
    jobs = ctrl.get_jobs()
    assert len(jobs) == 1
    assert jobs[0]["id"] == job.id
    assert jobs[0]["status"] in ("cancelled", "completed")


def test_adapter_cancel_terminates_subprocess(tmp_path: Path):
    """Test that BaseCLIAdapter.cancel() terminates a running process."""
    import time
    import threading
    from modue_harness.adapters.generic import GenericCLIAdapter
    from modue_harness.core.types import TurnContext

    adapter = GenericCLIAdapter(name="tester", command="python3", default_args=["-c", "import time; time.sleep(10)"])
    ctx = TurnContext(
        step_id="step1",
        instruction="run",
        blackboard_dir=tmp_path / "board",
        workspace_dir=tmp_path / "ws",
    )
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    def _run():
        return adapter.execute(ctx)

    t = threading.Thread(target=_run)
    t.start()

    # Wait until the process is running. Spawning is slow on Windows under
    # load, so poll instead of assuming a fixed delay is enough.
    deadline = time.time() + 5.0
    while adapter._current_process is None and time.time() < deadline:
        time.sleep(0.01)
    assert adapter._current_process is not None

    # Call cancel
    adapter.cancel()
    t.join(timeout=3.0)
    assert not t.is_alive()
    assert adapter._is_cancelled


def test_sync_execution_records_job_in_controller(tmp_path: Path):
    """Test that synchronous execute_command also registers a job in get_jobs()."""
    projects_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="sync_demo",
        projects_root=projects_root,
        blackboard_dir=board_root,
    )

    # Use a dummy agent so it runs fast
    from modue_harness.adapters.generic import GenericCLIAdapter
    dummy_agent = GenericCLIAdapter(name="architect", command="python3", default_args=["-c", "print('[]')"])
    ctrl.session.agents = {"architect": dummy_agent}
    ctrl.session.conductor_name = "architect"

    assert len(ctrl.get_jobs()) == 0

    res = ctrl.execute_command("test command")
    jobs = ctrl.get_jobs()
    assert len(jobs) >= 1
    assert jobs[0]["command"] == "test command"
    assert jobs[0]["project"] == "sync_demo"
    assert jobs[0]["status"] in ("completed", "failed")


def test_ui_controller_artifact_metadata_and_chronology(tmp_path: Path):
    """Test that UIController.get_artifacts returns newest first with metadata fields."""
    import time

    projects_root = tmp_path / "projects"
    board_root = tmp_path / "blackboard"

    ctrl = UIController(
        project_name="art_demo",
        projects_root=projects_root,
        blackboard_dir=board_root,
    )
    ctrl.session.project_dir.mkdir(parents=True, exist_ok=True)
    ctrl.session.blackboard.initialize()

    ctrl.session.blackboard.write_artifact(
        "older.md",
        "Older content",
        author_agent="coder",
        job_id="job_1",
    )
    time.sleep(0.05)
    ctrl.session.blackboard.write_artifact(
        "newer.md",
        "Newer content",
        author_agent="conductor",
        job_id="job_2",
    )

    artifacts = ctrl.get_artifacts()
    assert len(artifacts) == 2
    # Newest first
    assert artifacts[0]["name"] == "newer.md"
    assert artifacts[0]["author"] == "conductor"
    assert artifacts[0]["job_id"] == "job_2"
    assert "size_str" in artifacts[0]
    assert artifacts[0]["time_str"] != ""

    assert artifacts[1]["name"] == "older.md"
    assert artifacts[1]["author"] == "coder"
    assert artifacts[1]["job_id"] == "job_1"




