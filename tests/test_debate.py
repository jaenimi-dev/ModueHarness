"""Tests for DebateRunner (Debate & Consensus topology)."""

from pathlib import Path
import sys
from modue_harness.adapters.generic import GenericCLIAdapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.engine.debate import DebateRunner


def test_debate_runner_lifecycle(tmp_path: Path):
    """Verify multi-round debate produces artifacts and final consensus."""
    board = Blackboard(tmp_path / "blackboard")
    board.initialize()

    proposer_adapter = GenericCLIAdapter(
        name="proposer",
        command=sys.executable,
        default_args=["-c", "print('PROPOSAL: Use Microservices for flexibility.')"],
    )

    challenger_adapter = GenericCLIAdapter(
        name="challenger",
        command=sys.executable,
        default_args=["-c", "print('CRITIQUE: Microservices add excessive operational complexity. Consider Monolith first.')"],
    )

    judge_adapter = GenericCLIAdapter(
        name="judge",
        command=sys.executable,
        default_args=["-c", "print('CONSENSUS: Start with a Modular Monolith, transition to Microservices if needed.')"],
    )

    runner = DebateRunner(
        topic="Microservices vs Modular Monolith",
        proposer_adapter=proposer_adapter,
        challenger_adapter=challenger_adapter,
        judge_adapter=judge_adapter,
        blackboard=board,
        rounds=1,
    )

    result = runner.run()
    assert result["success"] is True
    assert result["status"] == "completed"
    assert len(result["transcript"]) == 2

    # Verify artifacts
    assert board.has_artifact("proposal_r1.md")
    assert board.has_artifact("critique_r1.md")
    assert board.has_artifact("consensus.md")
    assert "Modular Monolith" in board.read_artifact("consensus.md")
