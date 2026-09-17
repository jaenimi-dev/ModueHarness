"""Workflow definitions and configuration loader."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class WorkflowAgentConfig:
    """Configuration for an individual AI CLI agent in the workflow."""

    name: str
    adapter: str = "generic"
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    role: str = "Agent"

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "WorkflowAgentConfig":
        return cls(
            name=name,
            adapter=data.get("adapter", "generic"),
            command=data.get("command"),
            args=data.get("args", []),
            role=data.get("role", "Agent"),
        )


@dataclass
class WorkflowStepConfig:
    """Configuration for a single step in the workflow."""

    id: str
    agent: str
    instruction: str
    input_artifacts: List[str] = field(default_factory=list)
    output_artifact: Optional[str] = None
    timeout: float = 300.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_timeout: float = 300.0) -> "WorkflowStepConfig":
        return cls(
            id=data["id"],
            agent=data["agent"],
            instruction=data["instruction"],
            input_artifacts=data.get("input_artifacts", []),
            output_artifact=data.get("output_artifact"),
            timeout=float(data.get("timeout", default_timeout)),
        )


@dataclass
class WorkflowConfig:
    """Top-level workflow configuration specification."""

    name: str
    topology: str = "pipeline"
    timeout_per_step: float = 300.0
    agents: Dict[str, WorkflowAgentConfig] = field(default_factory=dict)
    steps: List[WorkflowStepConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        default_timeout = float(data.get("workflow", {}).get("timeout_per_step", 300.0))
        topology = data.get("workflow", {}).get("topology", "pipeline")

        agents = {}
        for agent_name, agent_data in data.get("agents", {}).items():
            agents[agent_name] = WorkflowAgentConfig.from_dict(agent_name, agent_data)

        steps = []
        for step_data in data.get("workflow", {}).get("steps", []):
            steps.append(WorkflowStepConfig.from_dict(step_data, default_timeout=default_timeout))

        return cls(
            name=data.get("name", "modue-workflow"),
            topology=topology,
            timeout_per_step=default_timeout,
            agents=agents,
            steps=steps,
        )

    @classmethod
    def load(cls, file_path: Path) -> "WorkflowConfig":
        """Load workflow configuration from a YAML or JSON file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {file_path}")

        suffix = file_path.suffix.lower()
        content = file_path.read_text(encoding="utf-8")

        if suffix in [".yaml", ".yml"]:
            if not HAS_YAML:
                raise RuntimeError("PyYAML is required to load .yaml workflow files.")
            data = yaml.safe_load(content)
        elif suffix == ".json":
            data = json.loads(content)
        else:
            # Attempt yaml safe_load first, fallback to json
            if HAS_YAML:
                data = yaml.safe_load(content)
            else:
                data = json.loads(content)

        return cls.from_dict(data)
