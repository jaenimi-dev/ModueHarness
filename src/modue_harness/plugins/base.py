"""Base plugin architecture and lifecycle hooks."""

from abc import ABC
from pathlib import Path
from typing import Any, Dict, List, Optional

from modue_harness.core.types import TurnResult


class BasePlugin(ABC):
    """Abstract base class for ModueHarness lifecycle plugins."""

    def __init__(self, name: str = "base_plugin") -> None:
        self.name = name

    def on_workflow_start(self, workflow_name: str, total_steps: int) -> None:
        """Called immediately before workflow execution commences."""
        pass

    def on_step_start(self, step_id: str, agent_name: str, instruction: str) -> None:
        """Called before an individual workflow step begins."""
        pass

    def on_step_finish(
        self,
        step_id: str,
        agent_name: str,
        is_success: bool,
        turn_result: Optional[TurnResult] = None,
    ) -> None:
        """Called after a step concludes."""
        pass

    def on_artifact_created(self, artifact_path: str, size_bytes: int) -> None:
        """Called when an artifact is committed to the blackboard."""
        pass

    def on_workflow_finish(self, summary: Dict[str, Any]) -> None:
        """Called after the entire workflow has terminated."""
        pass


class PluginManager:
    """Manages plugin registrations and dispatches lifecycle hooks."""

    def __init__(self, plugins: Optional[List[BasePlugin]] = None) -> None:
        self.plugins: List[BasePlugin] = plugins or []

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin instance."""
        self.plugins.append(plugin)

    def dispatch_workflow_start(self, workflow_name: str, total_steps: int) -> None:
        for p in self.plugins:
            try:
                p.on_workflow_start(workflow_name, total_steps)
            except Exception:
                pass

    def dispatch_step_start(self, step_id: str, agent_name: str, instruction: str) -> None:
        for p in self.plugins:
            try:
                p.on_step_start(step_id, agent_name, instruction)
            except Exception:
                pass

    def dispatch_step_finish(
        self,
        step_id: str,
        agent_name: str,
        is_success: bool,
        turn_result: Optional[TurnResult] = None,
    ) -> None:
        for p in self.plugins:
            try:
                p.on_step_finish(step_id, agent_name, is_success, turn_result)
            except Exception:
                pass

    def dispatch_artifact_created(self, artifact_path: str, size_bytes: int) -> None:
        for p in self.plugins:
            try:
                p.on_artifact_created(artifact_path, size_bytes)
            except Exception:
                pass

    def dispatch_workflow_finish(self, summary: Dict[str, Any]) -> None:
        for p in self.plugins:
            try:
                p.on_workflow_finish(summary)
            except Exception:
                pass
