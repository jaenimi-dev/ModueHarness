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

