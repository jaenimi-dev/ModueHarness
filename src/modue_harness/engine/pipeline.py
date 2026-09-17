"""Sequential pipeline execution runner."""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from modue_harness.adapters import BaseCLIAdapter, create_adapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.types import Task, TaskStatus, TurnContext, TurnResult
from modue_harness.engine.workflow import WorkflowConfig, WorkflowStepConfig


class PipelineRunner:
    """Executes a linear sequence of workflow steps using AI CLI adapters and a Blackboard."""

    def __init__(
        self,
        config: WorkflowConfig,
        blackboard: Optional[Blackboard] = None,
        workspace_dir: Optional[Path] = None,
        adapters_override: Optional[Dict[str, BaseCLIAdapter]] = None,
    ) -> None:
        self.config = config
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.blackboard = blackboard or Blackboard(self.workspace_dir / "blackboard")
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
                self.adapters[agent_name] = create_adapter(agent_cfg.adapter, **kwargs)

        if adapters_override:
            for name, adapter in adapters_override.items():
                if name not in self.adapters:
                    self.adapters[name] = adapter

    def run(self) -> Dict[str, Any]:
        """Execute the entire pipeline step by step."""
        self.blackboard.initialize()
        start_time = time.time()

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
            "completed_steps": len([r for r in results if r["is_success"]]),
        })

        return {
            "workflow_name": self.config.name,
            "status": final_status,
            "total_duration_sec": total_duration,
            "steps": results,
            "success": overall_success,
        }

    def _execute_step(self, step: WorkflowStepConfig, step_index: int) -> Dict[str, Any]:
        """Execute an individual step in the pipeline."""
        agent_name = step.agent
        adapter = self.adapters.get(agent_name)

        if not adapter:
            raise ValueError(f"No adapter configured for agent '{agent_name}' in step '{step.id}'")

        # 1. Record task on Blackboard
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

        # 2. Build TurnContext
        context = TurnContext(
            step_id=step.id,
            instruction=step.instruction,
            blackboard_dir=self.blackboard.root_dir,
            workspace_dir=self.workspace_dir,
            input_artifacts=step.input_artifacts,
        )

        # 3. Execute adapter
        turn_result: TurnResult = adapter.execute(context=context, timeout=step.timeout)

        # 4. Log execution details to Blackboard
        combined_logs = f"=== STDOUT ===\n{turn_result.stdout}\n\n=== STDERR ===\n{turn_result.stderr}"
        self.blackboard.append_log(agent_name=agent_name, step_id=step.id, content=combined_logs)

        # 5. Handle output artifact creation if defined
        if step.output_artifact and turn_result.is_success:
            # If the tool generated text on stdout, and the artifact file doesn't exist yet, save stdout
            artifact_rel = step.output_artifact.replace("blackboard/artifacts/", "")
            if not self.blackboard.has_artifact(artifact_rel) and turn_result.stdout:
                self.blackboard.write_artifact(artifact_rel, turn_result.stdout.strip())

        # 6. Update task status on Blackboard
        task_status = TaskStatus.COMPLETED if turn_result.is_success else TaskStatus.FAILED
        task_result_summary = {
            "exit_code": turn_result.exit_code,
            "duration_sec": turn_result.duration_sec,
            "error_message": turn_result.error_message,
        }
        self.blackboard.update_task_status(step.id, status=task_status, result=task_result_summary)

        return {
            "step_id": step.id,
            "agent": agent_name,
            "is_success": turn_result.is_success,
            "exit_code": turn_result.exit_code,
            "duration_sec": turn_result.duration_sec,
            "error_message": turn_result.error_message,
        }
