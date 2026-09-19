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


def test_interactive_session_model_and_effort(tmp_path: Path):
    """Test setting and querying model and effort in interactive session."""
    from modue_harness.adapters.claude import ClaudeCLIAdapter

    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    claude_arch = ClaudeCLIAdapter(name="architect", model="sonnet", effort="high")
    claude_dev = ClaudeCLIAdapter(name="developer", model="sonnet", effort="medium")

    session = InteractiveSession(
        project_name="model_test_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"architect": claude_arch, "developer": claude_dev},
        conductor_name="architect",
    )

    # Verify initial settings
    assert claude_arch.model == "sonnet"
    assert claude_arch.effort == "high"
    assert claude_dev.effort == "medium"

    # Test changing model for all
    updated = session.set_model("opus")
    assert "architect" in updated and "developer" in updated
    assert claude_arch.model == "opus"
    assert claude_dev.model == "opus"

    # Test changing effort for specific agent
    updated = session.set_effort("max", agent_name="architect")
    assert updated == ["architect"]
    assert claude_arch.effort == "max"
    assert claude_dev.effort == "medium"

    # Test special command handler for /model and /effort
    session._handle_special_command("/model haiku")
    assert claude_arch.model == "haiku"
    assert claude_dev.model == "haiku"

    session._handle_special_command("/effort low")
    assert claude_arch.effort == "low"
    assert claude_dev.effort == "low"

    session._handle_special_command("/model developer sonnet")
    assert claude_dev.model == "sonnet"
    assert claude_arch.model == "haiku"

    session._handle_special_command("/effort architect max")
    assert claude_arch.effort == "max"
    assert claude_dev.effort == "low"


def test_interactive_session_command_display(tmp_path: Path, capsys):
    """Test CLI command display and /cmd history inspection."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    # Mock agent returning valid json tasks
    tasks_json = json.dumps([
        {
            "id": "task_sub_1",
            "assigned_agent": "worker",
            "instruction": "Do work",
        }
    ])
    worker = GenericCLIAdapter(
        name="worker",
        command=sys.executable,
        default_args=["-c", f"import sys; content = sys.stdin.read(); print('{tasks_json}' if 'decompose' in content else 'WORK_DONE')"],
    )

    session = InteractiveSession(
        project_name="cmd_display_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"conductor": worker, "worker": worker},
        conductor_name="conductor",
    )

    summary = session.execute_command("Test display command", live_progress=True)
    captured = capsys.readouterr()

    # Verify that CLI execution line was printed to the screen
    assert "💻 CLI 실행:" in captured.out
    assert len(session.last_commands) >= 2

    # Test /cmd slash command
    session._handle_special_command("/cmd")
    captured_cmd = capsys.readouterr()
    assert "최근 실행된 실제 AI CLI 명령어 목록" in captured_cmd.out
    assert sys.executable in captured_cmd.out


def test_interactive_session_failure_reason_displayed(tmp_path: Path, capsys):
    """Test that failure reason is captured and printed in interactive session."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    tasks_json = json.dumps([
        {
            "id": "crash_task",
            "assigned_agent": "crasher",
            "instruction": "Trigger error",
        }
    ])
    conductor = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"print('{tasks_json}')"],
    )
    crasher = GenericCLIAdapter(
        name="crasher",
        command=sys.executable,
        default_args=["-c", "import sys; sys.stderr.write('FatalError: database connection refused\\n'); sys.exit(2)"],
    )

    session = InteractiveSession(
        project_name="fail_app",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents={"conductor": conductor, "crasher": crasher},
        conductor_name="conductor",
    )

    summary = session.execute_command("Run crashing command", live_progress=True)
    captured = capsys.readouterr()

    assert summary["success"] is False
    assert "FatalError: database connection refused" in summary["error"]
    assert "database connection refused" in captured.out
    assert "서브태스크 실패 원인" in captured.out


def test_cli_prompt_mode_failure_output(tmp_path: Path, capsys):
    """Test that CLI prompt mode prints failure reason clearly on stderr/stdout."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"
    agents_file = tmp_path / "agents.json"

    tasks_json = json.dumps([
        {
            "id": "fail_subtask",
            "assigned_agent": "broken_worker",
            "instruction": "Fail badly",
        }
    ])
    agents_data = {
        "agents": {
            "conductor": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", f"print('{tasks_json}')"],
            },
            "broken_worker": {
                "adapter": "generic",
                "command": sys.executable,
                "args": ["-c", "import sys; sys.stderr.write('SyntaxError: invalid syntax\\n'); sys.exit(1)"],
            }
        }
    }
    agents_file.write_text(json.dumps(agents_data), encoding="utf-8")

    exit_code = main([
        "-p", "Run breaking workflow",
        "-P", "broken_proj",
        "--projects-dir", str(projects_dir),
        "--dir", str(board_dir),
        "--agents", str(agents_file),
    ])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "상태: FAILED" in captured.out
    assert "❌ [실패 상세 원인]:" in captured.out
    assert "SyntaxError: invalid syntax" in captured.out
    assert "❌ 오류 상세:" in captured.out


def test_jobs_slash_command_displays_failure_reason(tmp_path: Path, capsys):
    """Test that /jobs displays the failure reason for failed background jobs."""
    projects_dir = tmp_path / "projects"
    board_dir = tmp_path / "blackboard"

    session = InteractiveSession(
        project_name="job_fail_proj",
        projects_root=projects_dir,
        blackboard_dir=board_dir,
    )
    from modue_harness.engine.interactive import BackgroundJob
    failed_job = BackgroundJob(
        id="job_99",
        command="Failing background task",
        project="job_fail_proj",
        project_dir=session.project_dir,
        status="failed",
        stage="done",
        error="ConnectionTimeout: network timeout after 30s",
    )
    session.jobs["job_99"] = failed_job

    session._handle_special_command("/jobs")
    captured = capsys.readouterr()
    assert "job_99" in captured.out
    assert "❌ 실패 사유: ConnectionTimeout: network timeout after 30s" in captured.out




