"""Tests for ConductorRunner (Leader-Worker topology)."""

import json
from pathlib import Path
import sys
from modue_harness.adapters.generic import GenericCLIAdapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.types import TaskStatus
from modue_harness.engine.conductor import ConductorRunner


def test_conductor_runner_decomposition_and_execution(tmp_path: Path):
    """Verify conductor decomposes goal into JSON tasks and workers execute them."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    # Conductor outputs a JSON plan on step 1, and final synthesis on step 3
    tasks_json = json.dumps([
        {
            "id": "build_api",
            "assigned_agent": "backend_dev",
            "instruction": "Build REST API endpoint",
            "output_artifact": "api.py",
        },
        {
            "id": "write_tests",
            "assigned_agent": "qa_tester",
            "instruction": "Write pytest tests",
            "output_artifact": "test_api.py",
        },
    ])

    conductor_adapter = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"import sys; content = sys.stdin.read(); print('{tasks_json}' if 'decompose' in content else 'FINAL_SYNTHESIS_REPORT: ALL_DONE')"],
    )

    backend_adapter = GenericCLIAdapter(
        name="backend_dev",
        command=sys.executable,
        default_args=["-c", "print('def api(): return True')"],
    )

    qa_adapter = GenericCLIAdapter(
        name="qa_tester",
        command=sys.executable,
        default_args=["-c", "print('def test_api(): assert api()')"],
    )

    runner = ConductorRunner(
        goal="Create tested API endpoint",
        conductor_agent_name="conductor",
        worker_agents={
            "conductor": conductor_adapter,
            "backend_dev": backend_adapter,
            "qa_tester": qa_adapter,
        },
        blackboard=board,
        workspace_dir=tmp_path,
    )

    summary = runner.run()
    assert summary["success"] is True
    assert summary["status"] == "completed"
    assert len(summary["subtasks"]) == 2

    # Verify artifacts were created
    assert board.has_artifact("api.py")
    assert "def api()" in board.read_artifact("api.py")

    assert board.has_artifact("test_api.py")
    assert "def test_api()" in board.read_artifact("test_api.py")

    assert board.has_artifact("synthesis_report.md")
    assert "FINAL_SYNTHESIS_REPORT: ALL_DONE" in board.read_artifact("synthesis_report.md")

    # Verify task board
    tasks = board.list_tasks()
    assert len(tasks) == 2
    assert all(t.status == TaskStatus.COMPLETED for t in tasks)


def test_conductor_runner_subtask_failure_reports_reason(tmp_path: Path):
    """Verify conductor reports failure reason when a worker subtask fails."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    tasks_json = json.dumps([
        {
            "id": "failing_task",
            "assigned_agent": "failing_dev",
            "instruction": "Do something that crashes",
            "output_artifact": "fail.txt",
        },
    ])

    conductor_adapter = GenericCLIAdapter(
        name="conductor",
        command=sys.executable,
        default_args=["-c", f"print('{tasks_json}')"],
    )

    failing_adapter = GenericCLIAdapter(
        name="failing_dev",
        command=sys.executable,
        default_args=["-c", "import sys; sys.stderr.write('ModuleNotFoundError: No module named fake_package\\n'); sys.exit(1)"],
    )

    runner = ConductorRunner(
        goal="Run failing task",
        conductor_agent_name="conductor",
        worker_agents={
            "conductor": conductor_adapter,
            "failing_dev": failing_adapter,
        },
        blackboard=board,
        workspace_dir=tmp_path,
    )

    summary = runner.run()
    assert summary["success"] is False
    assert summary["status"] == "failed"
    assert "ModuleNotFoundError" in summary["error_message"]
    assert "failing_task" in summary["error_message"]
    assert len(summary["subtasks"]) == 1
    assert summary["subtasks"][0]["is_success"] is False
    assert "ModuleNotFoundError" in summary["subtasks"][0]["error"]



def test_detect_external_writes_flags_files_outside_workspace(tmp_path: Path):
    """Files written outside the assigned project directory must be reported."""
    import time

    from modue_harness.engine.conductor import detect_external_writes

    guard_root = tmp_path
    workspace = guard_root / "projects" / "calculator"
    board_dir = guard_root / "blackboard" / "calculator"
    workspace.mkdir(parents=True)
    board_dir.mkdir(parents=True)

    # Pre-existing repository file that the run does not touch
    repo_tests = guard_root / "tests"
    repo_tests.mkdir()
    untouched = repo_tests / "test_existing.py"
    untouched.write_text("# untouched\n", encoding="utf-8")
    old_ts = time.time() - 3600
    import os

    os.utime(untouched, (old_ts, old_ts))

    since = time.time() - 0.05
    time.sleep(0.01)

    # Legitimate writes: inside the workspace and the blackboard
    (workspace / "calculator.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (board_dir / "plan.json").write_text("[]", encoding="utf-8")
    # Escaped write: the repository's own test suite
    (repo_tests / "test_calculator.py").write_text("# stray\n", encoding="utf-8")

    found = detect_external_writes(guard_root, [workspace, board_dir], since)

    assert found == ["tests/test_calculator.py"], found


def test_detect_external_writes_returns_empty_when_contained(tmp_path: Path):
    """A run that stays inside its workspace reports nothing."""
    import time

    from modue_harness.engine.conductor import detect_external_writes

    workspace = tmp_path / "projects" / "demo"
    board_dir = tmp_path / "blackboard" / "demo"
    workspace.mkdir(parents=True)
    board_dir.mkdir(parents=True)

    since = time.time()
    time.sleep(0.01)
    (workspace / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (board_dir / "notes.md").write_text("# notes\n", encoding="utf-8")

    assert detect_external_writes(tmp_path, [workspace, board_dir], since) == []


def test_detect_external_writes_skips_noise_directories(tmp_path: Path):
    """Cache and dependency directories are not reported as agent writes."""
    import time

    from modue_harness.engine.conductor import detect_external_writes

    workspace = tmp_path / "projects" / "demo"
    workspace.mkdir(parents=True)
    noise = tmp_path / "__pycache__"
    noise.mkdir()
    hidden = tmp_path / ".git"
    hidden.mkdir()

    since = time.time()
    time.sleep(0.01)
    (noise / "module.cpython-314.pyc").write_bytes(b"\x00")
    (hidden / "COMMIT_EDITMSG").write_text("msg\n", encoding="utf-8")

    assert detect_external_writes(tmp_path, [workspace], since) == []
