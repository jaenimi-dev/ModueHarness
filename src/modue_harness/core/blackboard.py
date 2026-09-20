"""Blackboard shared workspace and state coordination."""

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.types import Task, TaskStatus


class Blackboard:
    """Manages the shared blackboard directory, state, tasks, artifacts, and logs."""

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.root_dir = (root_dir or Path.cwd() / "blackboard").resolve()
        self.state_file = self.root_dir / "state.json"
        self.tasks_dir = self.root_dir / "tasks"
        self.artifacts_dir = self.root_dir / "artifacts"
        self.logs_dir = self.root_dir / "logs"
        self.event_bus = event_bus

    def initialize(self) -> None:
        """Create the blackboard folder hierarchy and initial state if not present."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        if not self.state_file.exists():
            initial_state = {
                "session_id": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
                "status": "initialized",
                "current_step": None,
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat(),
                "metadata": {},
            }
            self.save_state(initial_state)

    def is_initialized(self) -> bool:
        """Check whether the blackboard directory and state file exist."""
        return (
            self.root_dir.exists()
            and self.state_file.exists()
            and self.tasks_dir.exists()
            and self.artifacts_dir.exists()
        )

    # ---------------- State Management ---------------- #

    def load_state(self) -> Dict[str, Any]:
        """Load state.json contents."""
        if not self.state_file.exists():
            return {}
        with open(self.state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self, state: Dict[str, Any]) -> None:
        """Save dictionary to state.json atomically."""
        state["updated_at"] = datetime.datetime.now().isoformat()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.state_file)

    def update_state(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update selected fields in state.json."""
        state = self.load_state()
        state.update(updates)
        self.save_state(state)
        return state

    # ---------------- Task Management ---------------- #

    def create_task(self, task: Task) -> Task:
        """Save a new task into blackboard/tasks/<task_id>.json."""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        task_path = self.tasks_dir / f"{task.id}.json"
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

        if self.event_bus:
            self.event_bus.publish(
                HarnessEvent(
                    event_type=EventType.TASK_STATUS_CHANGED,
                    step_id=task.id,
                    agent_name=task.assigned_agent,
                    payload={"task_id": task.id, "status": task.status.value},
                )
            )
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetch a task by ID."""
        task_path = self.tasks_dir / f"{task_id}.json"
        if not task_path.exists():
            return None
        with open(task_path, "r", encoding="utf-8") as f:
            return Task.from_dict(json.load(f))

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[Task]:
        """Update the status and optional result of a task."""
        task = self.get_task(task_id)
        if not task:
            return None
        task.status = status
        if result is not None:
            task.result = result

        updated = self.create_task(task)
        return updated

    def list_tasks(self) -> List[Task]:
        """List all tasks sorted by task ID."""
        if not self.tasks_dir.exists():
            return []
        tasks: List[Task] = []
        for file in sorted(self.tasks_dir.glob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    tasks.append(Task.from_dict(json.load(f)))
            except Exception:
                continue
        return tasks

    # ---------------- Artifact Management ---------------- #

    def resolve_artifact_path(self, relative_path: str) -> Path:
        """Resolve a relative artifact path under blackboard/artifacts/."""
        clean_path = (
            relative_path.replace("\\", "/")
            .replace("blackboard/artifacts/", "")
            .lstrip("/")
        )
        return self.artifacts_dir / clean_path

    def write_artifact(
        self,
        relative_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        author_agent: Optional[str] = None,
    ) -> Path:
        """Write content and companion metadata to blackboard/artifacts/."""
        target_path = self.resolve_artifact_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        meta_file = target_path.with_name(f".{target_path.name}.meta.json")
        meta_payload = {
            "path": relative_path,
            "author": author_agent or "unknown",
            "size_bytes": len(content.encode("utf-8")),
            "created_at": datetime.datetime.now().isoformat(),
            "custom": metadata or {},
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2, ensure_ascii=False)

        if self.event_bus:
            self.event_bus.publish(
                HarnessEvent(
                    event_type=EventType.ARTIFACT_PRODUCED,
                    agent_name=author_agent,
                    payload={"artifact_path": relative_path, "size_bytes": len(content)},
                )
            )

        return target_path

    def read_artifact(self, relative_path: str) -> str:
        """Read artifact file content as a string."""
        target_path = self.resolve_artifact_path(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Artifact not found: {relative_path} (resolved: {target_path})")
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()

    def read_artifact_metadata(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Read companion metadata for an artifact."""
        try:
            target_path = self.resolve_artifact_path(relative_path)
            meta_file = target_path.with_name(f".{target_path.name}.meta.json")
            if not meta_file.exists():
                return None
            with open(meta_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def has_artifact(self, relative_path: str) -> bool:
        """Check if an artifact exists."""
        return self.resolve_artifact_path(relative_path).exists()

    def list_artifacts(self) -> List[str]:
        """List all artifact paths relative to artifacts/ (excluding meta files)."""
        if not self.artifacts_dir.exists():
            return []
        try:
            return [
                p.relative_to(self.artifacts_dir).as_posix()
                for p in sorted(self.artifacts_dir.rglob("*"))
                if p.is_file() and not p.name.startswith(".")
            ]
        except Exception:
            return []

    # ---------------- Logs Management ---------------- #

    def append_log(self, agent_name: str, step_id: str, content: str) -> Path:
        """Append output logs for a specific agent execution step."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.logs_dir / f"{agent_name}_{step_id}.log"
        timestamp = datetime.datetime.now().isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] === Step: {step_id} (Agent: {agent_name}) ===\n")
            f.write(content)
            f.write("\n\n")

        if self.event_bus:
            self.event_bus.publish(
                HarnessEvent(
                    event_type=EventType.LOG_EMITTED,
                    step_id=step_id,
                    agent_name=agent_name,
                    payload={"log_file": str(log_file)},
                )
            )

        return log_file
