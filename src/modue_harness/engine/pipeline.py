"""Enhanced sequential pipeline execution runner with condition, retry, isolation, and safety supervisor."""

from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional

from modue_harness.adapters import BaseCLIAdapter, create_adapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.supervisor import ProcessSupervisor
from modue_harness.core.types import Task, TaskStatus, TurnContext, TurnResult
from modue_harness.engine.workflow import WorkflowConfig, WorkflowStepConfig
from modue_harness.workspace import GitWorkspaceManager


class PipelineRunner:
    """Executes a linear sequence of workflow steps using AI CLI adapters, Blackboard, and Workspaces."""

    def __init__(
        self,
        config: WorkflowConfig,
        blackboard: Optional[Blackboard] = None,
        workspace_dir: Optional[Path] = None,
        adapters_override: Optional[Dict[str, BaseCLIAdapter]] = None,
        event_bus: Optional[EventBus] = None,
        workspace_manager: Optional[GitWorkspaceManager] = None,
        approval_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self.config = config
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = blackboard or Blackboard(self.workspace_dir / "blackboard", event_bus=self.event_bus)
        self.blackboard.event_bus = self.event_bus
        self.workspace_manager = workspace_manager or GitWorkspaceManager(self.workspace_dir)
        self.approval_callback = approval_callback
        self.adapters: Dict[str, BaseCLIAdapter] = {}

        # Initialize adapters from config
        for agent_name, agent_cfg in self.config.agents.items():
            if adapters_override and agent_name in adapters_override:
                self.adapters[agent_name] = adapters_override[agent_name]
            else:
                kwargs: Dict[str, Any] = {
                    "name": agent_name,
                    "default_args": agent_cfg.args,
                }
                if agent_cfg.command:
                    kwargs["command"] = agent_cfg.command
                if agent_cfg.model:
                    kwargs["model"] = agent_cfg.model
                if agent_cfg.effort:
                    kwargs["effort"] = agent_cfg.effort
                if agent_cfg.system_instruction:
                    kwargs["system_instruction"] = agent_cfg.system_instruction

                self.adapters[agent_name] = create_adapter(agent_cfg.adapter, **kwargs)

        if adapters_override:
            for name, adapter in adapters_override.items():
                if name not in self.adapters:
                    self.adapters[name] = adapter

    def run(self) -> Dict[str, Any]:
        """Execute the entire pipeline step by step."""
        self.blackboard.initialize()
        start_time = time.time()

        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.WORKFLOW_STARTED,
                payload={"workflow_name": self.config.name, "steps_count": len(self.config.steps)},
            )
        )

        self.blackboard.update_state({
            "workflow_name": self.config.name,
            "status": "running",
            "start_time": start_time,
            "total_steps": len(self.config.steps),
            "completed_steps": 0,
        })

        results: List[Dict[str, Any]] = []
        overall_success = True

        for idx, step in enumerate(self.config.steps):
            # Check condition if specified
            if not self._evaluate_condition(step.condition):
                results.append({
                    "step_id": step.id,
                    "agent": step.agent,
                    "is_success": True,
                    "skipped": True,
                    "exit_code": 0,
                    "duration_sec": 0.0,
                    "error_message": "Skipped due to unsatisfied condition",
                })
                continue

            step_result = self._execute_step(step, step_index=idx)
            results.append(step_result)

            if not step_result["is_success"]:
                overall_success = False
                break

        total_duration = time.time() - start_time
        final_status = "completed" if overall_success else "failed"

        self.blackboard.update_state({
            "status": final_status,
            "end_time": time.time(),
            "total_duration_sec": total_duration,
            "completed_steps": len([r for r in results if r["is_success"] and not r.get("skipped")]),
        })

        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.WORKFLOW_COMPLETED if overall_success else EventType.WORKFLOW_FAILED,
                payload={"status": final_status, "duration_sec": total_duration},
            )
        )

        return {
            "workflow_name": self.config.name,
            "status": final_status,
            "total_duration_sec": total_duration,
            "steps": results,
            "success": overall_success,
        }

    def _evaluate_condition(self, condition: Optional[str]) -> bool:
        """Evaluate a step precondition string."""
        if not condition or condition.lower() in ["always", "true"]:
            return True

        if condition.startswith("artifact_exists:"):
            art_path = condition.split(":", 1)[1].strip()
            return self.blackboard.has_artifact(art_path)

        if condition.startswith("not_exists:"):
            art_path = condition.split(":", 1)[1].strip()
            return not self.blackboard.has_artifact(art_path)

        return True

    def _resolve_template_variables(self, text: str) -> str:
        """Replace template variables such as ${artifact:path.md} in instructions."""
        pattern = re.compile(r"\$\{artifact:([^}]+)\}")

        def replacer(match):
            art_name = match.group(1).strip()
            try:
                return self.blackboard.read_artifact(art_name)
            except Exception:
                return f"[Missing Artifact: {art_name}]"

        return pattern.sub(replacer, text)

    def _execute_step(self, step: WorkflowStepConfig, step_index: int) -> Dict[str, Any]:
        """Execute a step with retry, fallback, worktree isolation, and supervisor."""
        agent_name = step.agent
        adapter = self.adapters.get(agent_name)

        if not adapter:
            raise ValueError(f"No adapter configured for agent '{agent_name}' in step '{step.id}'")

        # Supervisor & Human-In-The-Loop Checkpoint
        supervisor = ProcessSupervisor(
            timeout=step.timeout,
            stall_timeout=step.stall_timeout,
            approval_callback=self.approval_callback,
        )

        if step.requires_approval:
            approved = supervisor.request_approval(step.id, step.instruction)
            if not approved:
                return {
                    "step_id": step.id,
                    "agent": agent_name,
                    "is_success": False,
                    "exit_code": 130,
                    "duration_sec": 0.0,
                    "error_message": "Step rejected by human approval checkpoint",
                }

        # Record task on Blackboard
        task = Task(
            id=step.id,
            title=f"Step {step_index + 1}: {step.id}",
            description=step.instruction,
            assigned_agent=agent_name,
            status=TaskStatus.IN_PROGRESS,
            input_artifacts=step.input_artifacts,
            output_artifact=step.output_artifact,
        )
        self.blackboard.create_task(task)
        self.blackboard.update_state({"current_step": step.id})

        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.STEP_STARTED,
                step_id=step.id,
                agent_name=agent_name,
            )
        )

        resolved_instruction = self._resolve_template_variables(step.instruction)

        # Worktree isolation setup if requested
        step_workspace_dir = self.workspace_dir
        isolated_worktree_path: Optional[Path] = None

        if step.isolation == "worktree" and self.workspace_manager.is_git_repo():
            isolated_worktree_path = self.workspace_dir / ".modue_worktrees" / step.id
            try:
                self.workspace_manager.create_worktree(
                    branch_name=f"harness/{step.id}",
                    target_dir=isolated_worktree_path,
                )
                step_workspace_dir = isolated_worktree_path
            except Exception:
                # If worktree creation fails, continue on main workspace
                step_workspace_dir = self.workspace_dir
                isolated_worktree_path = None

        # Context
        context = TurnContext(
            step_id=step.id,
            instruction=resolved_instruction,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=step_workspace_dir,
            input_artifacts=step.input_artifacts,
        )

        # Execute with retries
        max_attempts = max(1, 1 + step.retry_count)
        turn_result: Optional[TurnResult] = None

        for attempt in range(max_attempts):
            turn_result = adapter.execute(context=context, timeout=step.timeout)
            if turn_result.is_success:
                break

        # Fallback agent support
        if turn_result and not turn_result.is_success and step.fallback_agent:
            fallback_adapter = self.adapters.get(step.fallback_agent)
            if fallback_adapter:
                agent_name = step.fallback_agent
                task.assigned_agent = agent_name
                self.blackboard.create_task(task)
                turn_result = fallback_adapter.execute(context=context, timeout=step.timeout)

        # Clean up isolated worktree if created
        if isolated_worktree_path:
            self.workspace_manager.remove_worktree(isolated_worktree_path)

        # Log
        combined_logs = f"=== STDOUT ===\n{turn_result.stdout}\n\n=== STDERR ===\n{turn_result.stderr}"
        self.blackboard.append_log(agent_name=agent_name, step_id=step.id, content=combined_logs)

        # Output artifact
        if step.output_artifact and turn_result.is_success:
            artifact_rel = step.output_artifact.replace("blackboard/artifacts/", "")
            if not self.blackboard.has_artifact(artifact_rel) and turn_result.stdout:
                self.blackboard.write_artifact(
                    relative_path=artifact_rel,
                    content=turn_result.stdout.strip(),
                    author_agent=agent_name,
                )

        # Final task update
        task_status = TaskStatus.COMPLETED if turn_result.is_success else TaskStatus.FAILED
        task_result_summary = {
            "exit_code": turn_result.exit_code,
            "duration_sec": turn_result.duration_sec,
            "error_message": turn_result.error_message,
        }
        self.blackboard.update_task_status(step.id, status=task_status, result=task_result_summary)

        self.event_bus.publish(
            HarnessEvent(
                event_type=EventType.STEP_COMPLETED if turn_result.is_success else EventType.STEP_FAILED,
                step_id=step.id,
                agent_name=agent_name,
                payload=task_result_summary,
            )
        )

        return {
            "step_id": step.id,
            "agent": agent_name,
            "is_success": turn_result.is_success,
            "exit_code": turn_result.exit_code,
            "duration_sec": turn_result.duration_sec,
            "error_message": turn_result.error_message,
            "command": turn_result.metadata.get("command_display"),
            "full_command": turn_result.metadata.get("full_command_str"),
        }
