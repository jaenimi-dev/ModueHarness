"""Tests for Blackboard shared workspace management."""

import json
from pathlib import Path
import pytest

from modue_harness.core.blackboard import Blackboard
from modue_harness.core.types import Task, TaskStatus


@pytest.fixture
def temp_board(tmp_path: Path) -> Blackboard:
    """Fixture providing an initialized blackboard in a temporary directory."""
    board = Blackboard(root_dir=tmp_path / "blackboard")
    board.initialize()
    return board


def test_blackboard_initialization(temp_board: Blackboard):
    """Verify blackboard directory and state structure is properly created."""
    assert temp_board.is_initialized()
    assert temp_board.root_dir.exists()
    assert temp_board.tasks_dir.exists()
    assert temp_board.artifacts_dir.exists()
    assert temp_board.logs_dir.exists()
    assert temp_board.state_file.exists()

    state = temp_board.load_state()
    assert state["status"] == "initialized"
    assert "session_id" in state


def test_blackboard_update_state(temp_board: Blackboard):
    """Verify state updating."""
    temp_board.update_state({"status": "running", "current_step": "step_1"})
    state = temp_board.load_state()
    assert state["status"] == "running"
    assert state["current_step"] == "step_1"


def test_blackboard_task_lifecycle(temp_board: Blackboard):
    """Verify task creation, retrieval, listing, and status updates."""
    task = Task(
        id="task_001",
        title="Design Spec",
        description="Write architecture document",
        assigned_agent="planner",
        status=TaskStatus.PENDING,
    )
    temp_board.create_task(task)

    fetched = temp_board.get_task("task_001")
    assert fetched is not None
    assert fetched.title == "Design Spec"
    assert fetched.status == TaskStatus.PENDING

    tasks = temp_board.list_tasks()
    assert len(tasks) == 1
    assert tasks[0].id == "task_001"

    # Update status
    updated = temp_board.update_task_status(
        "task_001",
        status=TaskStatus.COMPLETED,
        result={"file": "plan.md"},
    )
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.result == {"file": "plan.md"}

    # Clear tasks
    cleared_count = temp_board.clear_tasks()
    assert cleared_count == 1
    assert len(temp_board.list_tasks()) == 0


def test_blackboard_artifacts(temp_board: Blackboard):
    """Verify writing, reading, and listing artifacts."""
    assert not temp_board.has_artifact("specs/design.md")

    temp_board.write_artifact("specs/design.md", "# System Design\nHello world.")
    assert temp_board.has_artifact("specs/design.md")

    content = temp_board.read_artifact("specs/design.md")
    assert "Hello world." in content

    artifacts = temp_board.list_artifacts()
    assert "specs/design.md" in artifacts


def test_blackboard_logs(temp_board: Blackboard):
    """Verify appending execution logs."""
    log_file = temp_board.append_log("claude", "step_1", "Execution output log line.")
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Step: step_1 (Agent: claude)" in content
    assert "Execution output log line." in content


def test_blackboard_artifact_metadata(tmp_path: Path):
    """Verify artifact metadata persistence and EventBus notifications."""
    from modue_harness.core.events import EventBus, EventType
    bus = EventBus()
    board = Blackboard(root_dir=tmp_path / "board_with_bus", event_bus=bus)
    board.initialize()

    board.write_artifact(
        "report.txt",
        "Sample content",
        metadata={"category": "test"},
        author_agent="tester",
    )

    meta = board.read_artifact_metadata("report.txt")
    assert meta is not None
    assert meta["author"] == "tester"
    assert meta["custom"]["category"] == "test"

    produced_events = bus.get_history(EventType.ARTIFACT_PRODUCED)
    assert len(produced_events) == 1
    assert produced_events[0].payload["artifact_path"] == "report.txt"


def test_blackboard_artifact_history_and_detailed(temp_board: Blackboard):
    """Verify artifact overwrites archive to .history/ and detailed list includes job_id."""
    temp_board.write_artifact(
        "summary.md",
        "Version 1 content",
        author_agent="conductor",
        job_id="job_001",
    )
    detailed = temp_board.list_artifacts_detailed(newest_first=True)
    assert len(detailed) == 1
    assert detailed[0]["name"] == "summary.md"
    assert detailed[0]["author"] == "conductor"
    assert detailed[0]["job_id"] == "job_001"
    assert detailed[0]["time_str"] != ""

    # Overwrite with different content
    temp_board.write_artifact(
        "summary.md",
        "Version 2 content updated",
        author_agent="conductor",
        job_id="job_002",
    )
    assert temp_board.read_artifact("summary.md") == "Version 2 content updated"

    # Check history archiving
    history_dir = temp_board.artifacts_dir / ".history"
    assert history_dir.exists()
    archived_files = list(history_dir.glob("summary_*.md"))
    assert len(archived_files) >= 1
    assert "Version 1 content" in archived_files[0].read_text(encoding="utf-8")

    # Check updated detailed list
    detailed_updated = temp_board.list_artifacts_detailed(newest_first=True)
    assert detailed_updated[0]["job_id"] == "job_002"

