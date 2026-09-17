"""Tests for PipelineRunner and end-to-end multi-agent workflow."""

from pathlib import Path
import sys
import pytest

from modue_harness.adapters.generic import GenericCLIAdapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.types import TaskStatus
from modue_harness.engine.pipeline import PipelineRunner
from modue_harness.engine.workflow import (
    WorkflowAgentConfig,
    WorkflowConfig,
    WorkflowStepConfig,
)


def test_pipeline_runner_end_to_end(tmp_path: Path):
    """Verify multi-step pipeline execution and artifact exchange via blackboard."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    # Step 1: Agent writes a spec
    # Step 2: Agent reads the spec and outputs a confirmation
    config = WorkflowConfig(
        name="test-pipeline",
        topology="pipeline",
        agents={
            "agent_a": WorkflowAgentConfig(name="agent_a", adapter="generic"),
            "agent_b": WorkflowAgentConfig(name="agent_b", adapter="generic"),
        },
        steps=[
            WorkflowStepConfig(
                id="step_1_spec",
                agent="agent_a",
                instruction="Produce the architectural specification",
                output_artifact="spec.md",
            ),
            WorkflowStepConfig(
                id="step_2_impl",
                agent="agent_b",
                instruction="Confirm specification received",
                input_artifacts=["spec.md"],
                output_artifact="result.txt",
            ),
        ],
    )

    # Injected mock adapters using Python one-liners
    mock_adapter_a = GenericCLIAdapter(
        name="agent_a",
        command=sys.executable,
        default_args=["-c", "print('SPECIFICATION: Module Architecture V1')"],
    )
    mock_adapter_b = GenericCLIAdapter(
        name="agent_b",
        command=sys.executable,
        default_args=["-c", "import sys; content = sys.stdin.read(); print('RECEIVED_SPEC:' + ('Module Architecture' in content and 'YES' or 'NO'))"],
    )

    runner = PipelineRunner(
        config=config,
        blackboard=board,
        workspace_dir=tmp_path,
        adapters_override={"agent_a": mock_adapter_a, "agent_b": mock_adapter_b},
    )

    summary = runner.run()
    assert summary["success"] is True
    assert summary["status"] == "completed"
    assert len(summary["steps"]) == 2

    # Verify artifacts were created on blackboard
    assert board.has_artifact("spec.md")
    assert "SPECIFICATION: Module Architecture V1" in board.read_artifact("spec.md")

    assert board.has_artifact("result.txt")
    assert "RECEIVED_SPEC:YES" in board.read_artifact("result.txt")

    # Verify tasks on blackboard
    tasks = board.list_tasks()
    assert len(tasks) == 2
    assert tasks[0].status == TaskStatus.COMPLETED
    assert tasks[1].status == TaskStatus.COMPLETED

    # Verify logs on blackboard
    assert (board.logs_dir / "agent_a_step_1_spec.log").exists()
    assert (board.logs_dir / "agent_b_step_2_impl.log").exists()


def test_pipeline_runner_step_failure(tmp_path: Path):
    """Verify pipeline halts when a step fails."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    config = WorkflowConfig(
        name="failing-pipeline",
        topology="pipeline",
        agents={"agent_fail": WorkflowAgentConfig(name="agent_fail", adapter="generic")},
        steps=[
            WorkflowStepConfig(
                id="fail_step",
                agent="agent_fail",
                instruction="Fail intentionally",
            )
        ],
    )

    failing_adapter = GenericCLIAdapter(
        name="agent_fail",
        command=sys.executable,
        default_args=["-c", "import sys; sys.exit(42)"],
    )

    runner = PipelineRunner(
        config=config,
        blackboard=board,
        workspace_dir=tmp_path,
        adapters_override={"agent_fail": failing_adapter},
    )

    summary = runner.run()
    assert summary["success"] is False
    assert summary["status"] == "failed"
    assert summary["steps"][0]["exit_code"] == 42


def test_pipeline_condition_and_interpolation(tmp_path: Path):
    """Verify conditional execution skipping and template variable replacement."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()
    board.write_artifact("notes.txt", "Architecture Note 42")

    config = WorkflowConfig(
        name="condition-pipeline",
        topology="pipeline",
        agents={"tester": WorkflowAgentConfig(name="tester", adapter="generic")},
        steps=[
            # This step should execute because notes.txt exists
            WorkflowStepConfig(
                id="step_read",
                agent="tester",
                instruction="Notes are: ${artifact:notes.txt}",
                condition="artifact_exists:notes.txt",
                output_artifact="echo.txt",
            ),
            # This step should be skipped because missing.txt does not exist
            WorkflowStepConfig(
                id="step_skipped",
                agent="tester",
                instruction="Should not run",
                condition="artifact_exists:missing.txt",
            ),
        ],
    )

    mock_adapter = GenericCLIAdapter(
        name="tester",
        command=sys.executable,
        default_args=["-c", "import sys; print('GOT:' + sys.stdin.read().strip())"],
    )

    runner = PipelineRunner(
        config=config,
        blackboard=board,
        workspace_dir=tmp_path,
        adapters_override={"tester": mock_adapter},
    )

    summary = runner.run()
    assert summary["success"] is True
    assert len(summary["steps"]) == 2
    assert summary["steps"][0]["is_success"] is True
    assert summary["steps"][1].get("skipped") is True
    assert "Architecture Note 42" in board.read_artifact("echo.txt")


def test_pipeline_fallback_agent(tmp_path: Path):
    """Verify fallback agent handles task when primary agent fails."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    config = WorkflowConfig(
        name="fallback-pipeline",
        topology="pipeline",
        agents={
            "failing_primary": WorkflowAgentConfig(name="failing_primary", adapter="generic"),
            "backup_hero": WorkflowAgentConfig(name="backup_hero", adapter="generic"),
        },
        steps=[
            WorkflowStepConfig(
                id="step_with_fallback",
                agent="failing_primary",
                fallback_agent="backup_hero",
                instruction="Try primary then backup",
                output_artifact="backup_out.txt",
            )
        ],
    )

    failing_adapter = GenericCLIAdapter(
        name="failing_primary",
        command=sys.executable,
        default_args=["-c", "import sys; sys.exit(1)"],
    )
    backup_adapter = GenericCLIAdapter(
        name="backup_hero",
        command=sys.executable,
        default_args=["-c", "print('RECOVERED_BY_BACKUP')"],
    )

    runner = PipelineRunner(
        config=config,
        blackboard=board,
        workspace_dir=tmp_path,
        adapters_override={
            "failing_primary": failing_adapter,
            "backup_hero": backup_adapter,
        },
    )

    summary = runner.run()
    assert summary["success"] is True
    assert board.has_artifact("backup_out.txt")
    assert "RECOVERED_BY_BACKUP" in board.read_artifact("backup_out.txt")
