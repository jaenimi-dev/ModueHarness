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
