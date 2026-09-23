"""Workflow definitions and configuration loader supporting split AI and Task specifications."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _parse_file(file_path: Path) -> Dict[str, Any]:
    """Parse a YAML or JSON file into a dictionary."""
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    suffix = file_path.suffix.lower()
    content = file_path.read_text(encoding="utf-8-sig")

    if suffix in [".yaml", ".yml"]:
        if not HAS_YAML:
            raise RuntimeError("PyYAML is required to load .yaml configuration files.")
        return yaml.safe_load(content) or {}
    elif suffix == ".json":
        return json.loads(content) or {}
    else:
        if HAS_YAML:
            try:
                return yaml.safe_load(content) or {}
            except Exception:
                return json.loads(content) or {}
        return json.loads(content) or {}


@dataclass
class WorkflowAgentConfig:
    """Configuration for an individual AI CLI agent in the workflow."""

    name: str
    adapter: str = "generic"
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    role: str = "Agent"
    model: Optional[str] = None
    effort: Optional[str] = None
    system_instruction: Optional[str] = None
    # 어댑터별 선택 설정 (permission_mode, tools, max_turns 등). create_adapter 가 지원 여부를 거른다.
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "WorkflowAgentConfig":
        from modue_harness.adapters import AGENT_CONFIG_PASSTHROUGH_KEYS

        return cls(
            name=name,
            adapter=data.get("adapter", "generic"),
            command=data.get("command"),
            args=data.get("args", []),
            role=data.get("role", "Agent"),
            model=data.get("model"),
            effort=data.get("effort"),
            system_instruction=data.get("system_instruction"),
            options={k: data[k] for k in AGENT_CONFIG_PASSTHROUGH_KEYS if k in data},
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
    condition: Optional[str] = None  # e.g., "artifact_exists:plan.md" or None
    retry_count: int = 0
    fallback_agent: Optional[str] = None
    isolation: Optional[str] = None  # "worktree" or None
    requires_approval: bool = False
    stall_timeout: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_timeout: float = 300.0) -> "WorkflowStepConfig":
        return cls(
            id=data["id"],
            agent=data["agent"],
            instruction=data["instruction"],
            input_artifacts=data.get("input_artifacts", []),
            output_artifact=data.get("output_artifact"),
            timeout=float(data.get("timeout", default_timeout)),
            condition=data.get("condition"),
            retry_count=int(data.get("retry_count", 0)),
            fallback_agent=data.get("fallback_agent"),
            isolation=data.get("isolation"),
            requires_approval=bool(data.get("requires_approval", False)),
            stall_timeout=float(data["stall_timeout"]) if "stall_timeout" in data else None,
        )


@dataclass
class WorkflowConfig:
    """Top-level workflow configuration specification."""

    name: str
    topology: str = "pipeline"
    timeout_per_step: float = 300.0
    agents: Dict[str, WorkflowAgentConfig] = field(default_factory=dict)
    steps: List[WorkflowStepConfig] = field(default_factory=list)
    agents_file: Optional[str] = None

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
            agents_file=data.get("agents_file") or data.get("team_file"),
        )

    @classmethod
    def load(
        cls,
        file_path: Path,
        agents_file_override: Optional[Path] = None,
    ) -> "WorkflowConfig":
        """Load workflow configuration, supporting split AI agent specifications."""
        file_path = file_path.resolve()
        data = _parse_file(file_path)

        # Determine target agents specification file
        target_agents_file = None
        if agents_file_override:
            target_agents_file = agents_file_override.resolve()
        else:
            rel_agents_file = data.get("agents_file") or data.get("team_file")
            if rel_agents_file:
                target_agents_file = (file_path.parent / rel_agents_file).resolve()

        # If a separate agents file is specified, load and merge agents
        if target_agents_file:
            agents_data = _parse_file(target_agents_file)
            extracted_agents = agents_data.get("agents", agents_data)

            # Workflow file's explicit agents override or merge with external agents
            current_agents = data.get("agents", {})
            merged_agents = dict(extracted_agents)
            merged_agents.update(current_agents)
            data["agents"] = merged_agents

        return cls.from_dict(data)
