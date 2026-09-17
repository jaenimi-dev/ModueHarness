"""Debate and Consensus Orchestration Topology."""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from modue_harness.adapters import BaseCLIAdapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.types import TurnContext


class DebateRunner:
    """Orchestrates an adversarial or collaborative multi-round debate followed by Judge consensus."""

    def __init__(
        self,
        topic: str,
        proposer_adapter: BaseCLIAdapter,
        challenger_adapter: BaseCLIAdapter,
        judge_adapter: BaseCLIAdapter,
        blackboard: Optional[Blackboard] = None,
        workspace_dir: Optional[Path] = None,
        rounds: int = 2,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.topic = topic
        self.proposer = proposer_adapter
        self.challenger = challenger_adapter
        self.judge = judge_adapter
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = blackboard or Blackboard(self.workspace_dir / "blackboard", event_bus=self.event_bus)
        self.rounds = max(1, rounds)

    def run(self) -> Dict[str, Any]:
        """Run the debate rounds and produce final consensus."""
        self.blackboard.initialize()
        start_time = time.time()

        transcript: List[Dict[str, str]] = []

        # Round 1: Initial Proposal
        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.WORKFLOW_STARTED,
                payload={"topology": "debate", "topic": self.topic, "rounds": self.rounds},
            )
        )

        current_proposal = ""
        current_critique = ""

        for round_num in range(1, self.rounds + 1):
            # Proposer turn
            if round_num == 1:
                prop_instruction = (
                    f"Topic for Debate: {self.topic}\n"
                    f"You are the Proposer. Present your primary architectural approach or solution."
                )
            else:
                prop_instruction = (
                    f"Topic: {self.topic}\n"
                    f"Previous Challenger Critique:\n{current_critique}\n\n"
                    f"Defend your position, address criticisms, and refine your proposal."
                )

            prop_ctx = TurnContext(
                step_id=f"debate_proposer_r{round_num}",
                instruction=prop_instruction,
                blackboard_dir=self.blackboard.root_dir,
                workspace_dir=self.workspace_dir,
            )
            prop_res = self.proposer.execute(prop_ctx)
            current_proposal = prop_res.stdout.strip()
            transcript.append({"round": f"Round {round_num}", "speaker": "Proposer", "content": current_proposal})
            self.blackboard.write_artifact(f"proposal_r{round_num}.md", current_proposal, author_agent=self.proposer.name)

            # Challenger turn
            chal_instruction = (
                f"Topic: {self.topic}\n"
                f"Current Proposal:\n{current_proposal}\n\n"
                f"You are the Critic / Challenger. Identify flaws, edge cases, risks, and offer alternative improvements."
            )
            chal_ctx = TurnContext(
                step_id=f"debate_challenger_r{round_num}",
                instruction=chal_instruction,
                blackboard_dir=self.blackboard.root_dir,
                workspace_dir=self.workspace_dir,
            )
            chal_res = self.challenger.execute(chal_ctx)
            current_critique = chal_res.stdout.strip()
            transcript.append({"round": f"Round {round_num}", "speaker": "Challenger", "content": current_critique})
            self.blackboard.write_artifact(f"critique_r{round_num}.md", current_critique, author_agent=self.challenger.name)

        # Final Judge Consensus
        full_transcript_text = "\n\n".join(
            [f"=== {t['round']} - {t['speaker']} ===\n{t['content']}" for t in transcript]
        )

        judge_instruction = (
            f"Topic: {self.topic}\n\n"
            f"Below is the complete transcript of the debate between Proposer and Challenger:\n\n"
            f"{full_transcript_text}\n\n"
            f"You are the impartial Judge / Arbiter. Evaluate both perspectives, resolve trade-offs, "
            f"and formulate the final optimal Consensus Decision."
        )

        judge_ctx = TurnContext(
            step_id="debate_judge_consensus",
            instruction=judge_instruction,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=self.workspace_dir,
        )

        judge_res = self.judge.execute(judge_ctx)
        consensus_text = judge_res.stdout.strip()

        consensus_path = self.blackboard.write_artifact("consensus.md", consensus_text, author_agent=self.judge.name)
        total_duration = time.time() - start_time

        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.WORKFLOW_COMPLETED,
                payload={"consensus_artifact": str(consensus_path), "duration_sec": total_duration},
            )
        )

        return {
            "status": "completed",
            "topic": self.topic,
            "rounds": self.rounds,
            "transcript": transcript,
            "consensus": consensus_text,
            "total_duration_sec": total_duration,
            "success": True,
        }
