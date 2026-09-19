"""Leader-Worker Conductor Orchestrator."""

import json
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

from modue_harness.adapters import BaseCLIAdapter, create_adapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.types import Task, TaskStatus, TurnContext, TurnResult
from modue_harness.engine.workflow import WorkflowConfig


class ConductorRunner:
    """Orchestrates hierarchical dynamic task breakdown and execution with Leader and Workers."""

    def __init__(
        self,
        goal: str,
        conductor_agent_name: str,
        worker_agents: Dict[str, BaseCLIAdapter],
        blackboard: Optional[Blackboard] = None,
        workspace_dir: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
        max_subtasks: int = 10,
    ) -> None:
        self.goal = goal
        self.conductor_name = conductor_agent_name
        self.worker_adapters = worker_agents
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = blackboard or Blackboard(self.workspace_dir / "blackboard", event_bus=self.event_bus)
        self.blackboard.event_bus = self.event_bus
        self.max_subtasks = max_subtasks

    def _extract_tasks_json(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON task list from conductor response."""
        # Try direct json loads first
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "tasks" in parsed:
                return parsed["tasks"]
        except Exception:
            pass

        # Try finding markdown ```json ... ``` block
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        # Fallback to empty
        return []

    def run(self) -> Dict[str, Any]:
        """Execute the Leader-Worker workflow."""
        self.blackboard.initialize()
        start_time = time.time()

        conductor_adapter = self.worker_adapters.get(self.conductor_name)
        if not conductor_adapter:
            raise ValueError(f"Conductor agent '{self.conductor_name}' not found in provided adapters.")

        available_workers = [k for k in self.worker_adapters.keys() if k != self.conductor_name]
        if not available_workers:
            available_workers = [self.conductor_name]

        # Phase 1: Planning / Task Decomposition
        decomposition_prompt = (
            f"You are the Conductor/Leader AI.\n"
            f"Goal: {self.goal}\n"
            f"Target Project Directory: {self.workspace_dir}\n"
            f"Shared Blackboard Directory: {self.blackboard.root_dir}\n"
            f"Available Worker Agents: {', '.join(available_workers)}\n\n"
            f"Please decompose this goal into concrete subtasks for the workers.\n"
            f"Important:\n"
            f"- All actual source code and implementation files must be created in the project directory: {self.workspace_dir}\n"
            f"- Use the blackboard directory ({self.blackboard.root_dir}) only for coordination, planning, and task artifacts.\n\n"
            f"Output your plan as a JSON array of task objects:\n"
            f"[\n"
            f'  {{"id": "subtask_1", "assigned_agent": "<agent_name>", "instruction": "...", "output_artifact": "artifact_name.md"}}\n'
            f"]"
        )

        plan_context = TurnContext(
            step_id="conductor_planning",
            instruction=decomposition_prompt,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=self.workspace_dir,
        )

        plan_result = conductor_adapter.execute(plan_context)
        if not plan_result.is_success:
            return {
                "status": "failed",
                "stage": "planning",
                "error_message": plan_result.error_message or "Conductor failed during planning",
                "success": False,
            }

        # Save plan to blackboard
        self.blackboard.write_artifact("plan.json", plan_result.stdout.strip(), author_agent=self.conductor_name)
        subtasks_data = self._extract_tasks_json(plan_result.stdout)

        if not subtasks_data:
            # If no JSON tasks parsed, treat full response as plan document
            self.blackboard.write_artifact("plan.md", plan_result.stdout.strip(), author_agent=self.conductor_name)
            subtasks_data = [
                {
                    "id": "task_1",
                    "assigned_agent": available_workers[0] if available_workers else self.conductor_name,
                    "instruction": f"Implement goal according to plan: {self.goal}",
                    "output_artifact": "result.txt",
                }
            ]

        # Phase 2: Execute Workers
        worker_results: List[Dict[str, Any]] = []
        overall_success = True

        for task_info in subtasks_data[:self.max_subtasks]:
            task_id = task_info.get("id", f"task_{len(worker_results)+1}")
            assigned = task_info.get("assigned_agent", available_workers[0] if available_workers else self.conductor_name)
            instruction = task_info.get("instruction", "")
            output_art = task_info.get("output_artifact")

            worker_adapter = self.worker_adapters.get(assigned, conductor_adapter)

            task = Task(
                id=task_id,
                title=task_id,
                description=instruction,
                assigned_agent=assigned,
                status=TaskStatus.IN_PROGRESS,
                output_artifact=output_art,
            )
            self.blackboard.create_task(task)

            turn_ctx = TurnContext(
                step_id=task_id,
                instruction=instruction,
                blackboard_dir=self.blackboard.root_dir,
                workspace_dir=self.workspace_dir,
            )

            res = worker_adapter.execute(turn_ctx)
            if res.is_success:
                if output_art and res.stdout:
                    self.blackboard.write_artifact(output_art, res.stdout.strip(), author_agent=assigned)
                self.blackboard.update_task_status(task_id, TaskStatus.COMPLETED)
                worker_results.append({"task_id": task_id, "agent": assigned, "is_success": True})
            else:
                self.blackboard.update_task_status(task_id, TaskStatus.FAILED, {"error": res.error_message})
                worker_results.append({"task_id": task_id, "agent": assigned, "is_success": False})
                overall_success = False
                break

        # Phase 3: Conductor Synthesis / Review
        synthesis_prompt = (
            f"You are the Conductor AI.\n"
            f"All worker subtasks have concluded.\n"
            f"Goal: {self.goal}\n"
            f"Subtasks execution status: {json.dumps(worker_results, indent=2)}\n"
            f"Provide your final evaluation, synthesis, and status report."
        )

        synth_ctx = TurnContext(
            step_id="conductor_synthesis",
            instruction=synthesis_prompt,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=self.workspace_dir,
        )
        synth_res = conductor_adapter.execute(synth_ctx)
        if synth_res.is_success:
            self.blackboard.write_artifact("synthesis_report.md", synth_res.stdout.strip(), author_agent=self.conductor_name)

        total_duration = time.time() - start_time
        final_status = "completed" if overall_success else "failed"

        # Collect created/modified files in project workspace
        project_files = []
        if self.workspace_dir.exists():
            for p in self.workspace_dir.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    try:
                        project_files.append(str(p.relative_to(self.workspace_dir)))
                    except Exception:
                        pass

        return {
            "status": final_status,
            "success": overall_success,
            "goal": self.goal,
            "subtasks": worker_results,
            "total_duration_sec": total_duration,
            "project_files": sorted(project_files),
        }
