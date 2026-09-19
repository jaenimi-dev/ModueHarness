"""Tests for InteractiveSession, CLI direct prompt execution, and project/blackboard isolation."""

import json
from pathlib import Path
import sys
import pytest

from modue_harness.adapters.generic import GenericCLIAdapter
from modue_harness.cli import main
from modue_harness.core.blackboard import Blackboard
from modue_harness.engine.interactive import InteractiveSession, load_or_detect_agents


def test_interactive_session_project_management(tmp_path: Path):
    """Test project switching and file isolation in InteractiveSession."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    session = InteractiveSession(
        project_name="proj_alpha",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    # Initial project dir
    assert session.project_dir == projects_dir / "proj_alpha"
    assert session.project_name == "proj_alpha"

    # Switch project
    session.switch_project("proj_beta")
    assert session.project_name == "proj_beta"
    assert session.project_dir == projects_dir / "proj_beta"
    assert session.project_dir.exists()

    # List projects
    projects = session.list_projects()
    assert "proj_beta" in projects


def test_interactive_session_command_execution(tmp_path: Path):
    """Test command execution: actual files in project directory, coordination on blackboard."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    # Custom mock agents where worker writes a file into cwd (which is project_dir)
    tasks_json = json.dumps([
        {
            "id": "write_code",
            "assigned_agent": "coder",
            "instruction": "Write hello.py",
            "output_artifact": "result.txt",
        }
    ])

    # Conductor outputs json plan on decompose, else synthesis
    conductor = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"import sys; content = sys.stdin.read(); print('{tasks_json}' if 'decompose' in content else 'SYNTHESIS_DONE')"],
    )

    # Coder creates hello.py in current working directory
    coder = GenericCLIAdapter(
        name="coder",
        command=sys.executable,
        default_args=["-c", "from pathlib import Path; Path('hello.py').write_text('print(\"Hello Project!\")'); print('Created hello.py')"],
    )

    session = InteractiveSession(
        project_name="my_calculator",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"conductor": conductor, "coder": coder},
        conductor_name="conductor",
    )

    summary = session.execute_command("Create hello application")

    assert summary["success"] is True
    assert summary["project"] == "my_calculator"

    # Verify implementation file is inside projects/my_calculator/
    project_file = session.project_dir / "hello.py"
    assert project_file.exists()
    assert "Hello Project!" in project_file.read_text()
    assert "hello.py" in summary["project_files"]

    # Verify blackboard holds tasks, state, and coordination artifacts
    board = Blackboard(root_dir=board_dir)
    assert board.has_artifact("plan.json")
    assert board.has_artifact("synthesis_report.md")
    assert board.has_artifact("result.txt")

    state = board.load_state()
    assert state.get("current_project") == "my_calculator"


def test_cli_direct_prompt_flag(tmp_path: Path, capsys):
    """Test CLI execution with -p / --prompt flag."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"
    agents_file = tmp_path / "agents.json"

    agents_data = {
        "agents": {
            "conductor": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", "print('[]')"],
            },
            "worker": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", "from pathlib import Path; Path('calc.py').write_text('def add(a, b): return a + b'); print('Done')"],
            }
        }
    }
    agents_file.write_text(json.dumps(agents_data), encoding="utf-8")

    exit_code = main([
        "-p", "Build calculator module",
        "-P", "calc_proj",
        "--projects-dir", str(projects_dir),
        "--dir", str(board_dir),
        "--agents", str(agents_file),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "작업 실행" in captured.out or "Executing" in captured.out
    assert (projects_dir / "calc_proj" / "calc.py").exists()


def test_cli_positional_prompt(tmp_path: Path, capsys):
    """Test CLI execution with positional prompt string."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"
    agents_file = tmp_path / "agents.json"

    agents_data = {
        "agents": {
            "conductor": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", "print('[]')"],
            },
            "worker": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", "print('OK')"],
            }
        }
    }
    agents_file.write_text(json.dumps(agents_data), encoding="utf-8")

    exit_code = main([
        "Build fast api server",
        "-P", "web_api",
        "--projects-dir", str(projects_dir),
        "--dir", str(board_dir),
        "--agents", str(agents_file),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "web_api" in captured.out


def test_cli_projects_command(tmp_path: Path, capsys):
    """Test modue-harness projects subcommand."""
    projects_dir = tmp_path / "projects"
    (projects_dir / "project_1").mkdir(parents=True)
    (projects_dir / "project_2").mkdir(parents=True)

    exit_code = main(["projects", "--projects-dir", str(projects_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "project_1" in captured.out
    assert "project_2" in captured.out


def test_interactive_repl_special_commands(tmp_path: Path, capsys, monkeypatch):
    """Test REPL special commands like /project, /projects, /files, /status, /help, exit."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    # Simulate user entering slash commands then exit
    commands = iter([
        "/help",
        "/projects",
        "/project new_app",
        "/files",
        "/status",
        "exit",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(commands))

    session = InteractiveSession(
        project_name="initial_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )

    session.start_repl()

    captured = capsys.readouterr()
    assert "사용 가능한 명령어" in captured.out
    assert "new_app" in captured.out
    assert "대화형 세션을 종료합니다" in captured.out


def test_interactive_session_live_progress(tmp_path: Path, capsys):
    """Verify real-time progress callbacks emit during foreground execution."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    conductor = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", "print('[]')"],
    )

    session = InteractiveSession(
        project_name="prog_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"conductor": conductor},
        conductor_name="conductor",
    )

    summary = session.execute_command("Run progress test", live_progress=True)
    captured = capsys.readouterr()

    assert "작업 목표 분석 및 계획 수립 중" in captured.out
    assert summary["project"] == "prog_app"


def test_interactive_session_background_job_and_cancel(tmp_path: Path):
    """Verify background job execution and cancel capability."""
    import time
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    # Worker that sleeps
    sleeper = GenericCLIAdapter(
        name="sleeper",
        command=sys.executable,
        default_args=["-c", "import time; time.sleep(0.5); print('Done')"],
    )

    session = InteractiveSession(
        project_name="bg_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"conductor": sleeper},
        conductor_name="conductor",
    )

    job = session.execute_command_async("Sleep in background")
    assert job.id in session.jobs
    assert job.status == "running"

    # Wait for completion
    if job.thread:
        job.thread.join(timeout=5.0)
    assert job.status in ["completed", "failed"]

    # Test cancellation on new job
    job2 = session.execute_command_async("Long task to cancel")
    time.sleep(0.1)
    cancelled = session.cancel_job(job2.id)
    assert cancelled is True
    assert job2.status == "cancelled"

