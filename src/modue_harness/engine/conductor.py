"""Leader-Worker Conductor Orchestrator."""

import json
from pathlib import Path
import re
import shlex
import time
from typing import Any, Callable, Dict, List, Optional

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
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self.goal = goal
        self.conductor_name = conductor_agent_name
        self.worker_adapters = worker_agents
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = blackboard or Blackboard(self.workspace_dir / "blackboard", event_bus=self.event_bus)
        self.blackboard.event_bus = self.event_bus
        self.max_subtasks = max_subtasks
        self.progress_callback = progress_callback
        self._is_cancelled: bool = False

    def cancel(self) -> None:
        """Request cancellation of running workflow."""
        self._is_cancelled = True

    def _notify(self, event: str, data: Dict[str, Any]) -> None:
        """Emit real-time progress event to registered callback."""
        if self.progress_callback:
            try:
                self.progress_callback(event, data)
            except Exception:
                pass

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

        if self._is_cancelled:
            return {
                "status": "cancelled",
                "success": False,
                "goal": self.goal,
                "subtasks": [],
                "error_message": "작업이 취소되었습니다 (User cancelled)",
                "total_duration_sec": time.time() - start_time,
            }

        # Phase 1: Planning / Task Decomposition
        plan_context = TurnContext(
            step_id="conductor_planning",
            instruction=decomposition_prompt,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=self.workspace_dir,
        )
        plan_prompt = conductor_adapter.prepare_prompt(plan_context)
        plan_cmd = conductor_adapter.build_command(plan_prompt)
        plan_cmd_display = conductor_adapter.format_command_display(plan_cmd, max_prompt_len=None)
        try:
            plan_full_cmd_str = shlex.join(plan_cmd)
        except Exception:
            plan_full_cmd_str = " ".join(plan_cmd)

        self._notify("planning_start", {
            "conductor": self.conductor_name,
            "goal": self.goal,
            "command": plan_cmd_display,
            "full_command_str": plan_full_cmd_str,
        })

        plan_result = conductor_adapter.execute(plan_context)
        if not plan_result.is_success:
            self._notify("planning_end", {"conductor": self.conductor_name, "is_success": False, "error": plan_result.error_message})
            return {
                "status": "failed",
                "stage": "planning",
                "error_message": plan_result.error_message or "Conductor failed during planning",
                "success": False,
                "goal": self.goal,
                "subtasks": [],
                "total_duration_sec": time.time() - start_time,
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

        self._notify("planning_end", {"conductor": self.conductor_name, "is_success": True, "tasks": subtasks_data[:self.max_subtasks]})

        # Phase 2: Execute Workers
        worker_results: List[Dict[str, Any]] = []
        overall_success = True
        failure_reason: Optional[str] = None
        total_subtasks = len(subtasks_data[:self.max_subtasks])

        for idx, task_info in enumerate(subtasks_data[:self.max_subtasks]):
            if self._is_cancelled:
                overall_success = False
                failure_reason = "작업이 취소되었습니다 (User cancelled)"
                break

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
            worker_prompt = worker_adapter.prepare_prompt(turn_ctx)
            worker_cmd = worker_adapter.build_command(worker_prompt)
            worker_cmd_display = worker_adapter.format_command_display(worker_cmd, max_prompt_len=None)
            try:
                worker_full_cmd_str = shlex.join(worker_cmd)
            except Exception:
                worker_full_cmd_str = " ".join(worker_cmd)

            self._notify("task_start", {
                "task_id": task_id,
                "agent": assigned,
                "instruction": instruction,
                "index": idx + 1,
                "total": total_subtasks,
                "command": worker_cmd_display,
                "full_command_str": worker_full_cmd_str,
            })

            res = worker_adapter.execute(turn_ctx)
            task_record = {
                "task_id": task_id,
                "agent": assigned,
                "is_success": res.is_success,
                "command": worker_cmd_display,
                "full_command_str": worker_full_cmd_str,
                "duration_sec": res.duration_sec,
            }
            if res.is_success:
                if output_art and res.stdout:
                    self.blackboard.write_artifact(output_art, res.stdout.strip(), author_agent=assigned)
                self.blackboard.update_task_status(task_id, TaskStatus.COMPLETED)
                worker_results.append(task_record)
                self._notify("task_end", {
                    "task_id": task_id,
                    "agent": assigned,
                    "is_success": True,
                    "duration_sec": res.duration_sec,
                    "command": worker_cmd_display,
                    "full_command_str": worker_full_cmd_str,
                })
            else:
                self.blackboard.update_task_status(task_id, TaskStatus.FAILED, {"error": res.error_message})
                task_record["error"] = res.error_message
                worker_results.append(task_record)
                self._notify("task_end", {
                    "task_id": task_id,
                    "agent": assigned,
                    "is_success": False,
                    "duration_sec": res.duration_sec,
                    "error": res.error_message,
                    "command": worker_cmd_display,
                    "full_command_str": worker_full_cmd_str,
                })
                overall_success = False
                failure_reason = f"서브태스크 [{task_id}] 실행 실패: {res.error_message}"
                break

        # Phase 3: Conductor Synthesis / Review
        if not self._is_cancelled and overall_success:
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
            synth_prompt = conductor_adapter.prepare_prompt(synth_ctx)
            synth_cmd = conductor_adapter.build_command(synth_prompt)
            synth_cmd_display = conductor_adapter.format_command_display(synth_cmd, max_prompt_len=None)
            try:
                synth_full_cmd_str = shlex.join(synth_cmd)
            except Exception:
                synth_full_cmd_str = " ".join(synth_cmd)

            self._notify("synthesis_start", {
                "conductor": self.conductor_name,
                "command": synth_cmd_display,
                "full_command_str": synth_full_cmd_str,
            })
            synth_res = conductor_adapter.execute(synth_ctx)
            if synth_res.is_success:
                self.blackboard.write_artifact("synthesis_report.md", synth_res.stdout.strip(), author_agent=self.conductor_name)
            else:
                overall_success = False
                if not failure_reason:
                    failure_reason = f"Conductor 종합 보고서 작성 실패: {synth_res.error_message}"

            self._notify("synthesis_end", {
                "conductor": self.conductor_name,
                "is_success": synth_res.is_success,
                "error": synth_res.error_message if not synth_res.is_success else None,
                "command": synth_cmd_display,
                "full_command_str": synth_full_cmd_str,
            })

        total_duration = time.time() - start_time
        if self._is_cancelled:
            final_status = "cancelled"
            overall_success = False
            if not failure_reason:
                failure_reason = "작업이 취소되었습니다 (User cancelled)"
        else:
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
            "error_message": failure_reason,
        }
