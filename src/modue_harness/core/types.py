"""Core data types and structures for ModueHarness."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    """Lifecycle status of a harness task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TurnContext:
    """Context provided to an AI CLI adapter for executing a turn."""

    step_id: str
    instruction: str
    blackboard_dir: Path
    workspace_dir: Path
    input_artifacts: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """Standardized result returned after an AI CLI execution turn."""

    status: TaskStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_sec: float = 0.0
    output_artifact: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Return True if the turn completed successfully."""
        return self.status == TaskStatus.COMPLETED and self.exit_code == 0


@dataclass
class Task:
    """A unit of work tracked on the blackboard."""

    id: str
    title: str
    description: str
    assigned_agent: str
    status: TaskStatus = TaskStatus.PENDING
    input_artifacts: List[str] = field(default_factory=list)
    output_artifact: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value,
            "input_artifacts": self.input_artifacts,
            "output_artifact": self.output_artifact,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Reconstruct a Task instance from a dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            assigned_agent=data.get("assigned_agent", "unassigned"),
            status=TaskStatus(data.get("status", "pending")),
            input_artifacts=data.get("input_artifacts", []),
            output_artifact=data.get("output_artifact"),
            result=data.get("result"),
        )
