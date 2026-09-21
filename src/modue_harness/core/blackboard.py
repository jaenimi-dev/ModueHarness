"""Blackboard shared workspace and state coordination."""

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.types import Task, TaskStatus
from modue_harness.core.usage import UsageTracker


#: Directory names the blackboard owns itself; they are never project names.
RESERVED_DIR_NAMES = frozenset({"tasks", "artifacts", "logs", "jobs", "usage"})


class Blackboard:
    """Manages the shared blackboard directory, state, tasks, artifacts, and logs."""

    def __init__(
        self,
        root_dir: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
        project: Optional[str] = None,
    ) -> None:
        base = (root_dir or Path.cwd() / "blackboard").resolve()
        self.project = project
        if project:
            if base.name == project:
                self.base_root_dir = base.parent
                self.root_dir = base
            else:
                self.base_root_dir = base
                self.root_dir = base / project
        else:
            self.base_root_dir = base
            self.root_dir = base

        self.state_file = self.root_dir / "state.json"
        self.tasks_dir = self.root_dir / "tasks"
        self.artifacts_dir = self.root_dir / "artifacts"
        self.logs_dir = self.root_dir / "logs"
        self.jobs_dir = self.root_dir / "jobs"
        self.usage_dir = self.root_dir / "usage"
        self.event_bus = event_bus
        self.usage_tracker = UsageTracker(self.root_dir)

    def for_project(self, project_name: str) -> "Blackboard":
        """Return a Blackboard instance isolated to a specific project subfolder."""
        clean_name = project_name.strip()
        return Blackboard(
            root_dir=self.base_root_dir,
            event_bus=self.event_bus,
            project=clean_name,
        )

    @staticmethod
    def find_project_dirs(root: Path) -> List[Path]:
        """Return the per-project blackboard subdirectories directly under `root`.

        Reserved directories the blackboard creates for itself (tasks/, jobs/,
        usage/, ...) are skipped, and a candidate must carry at least one
        project marker file, so unrelated folders are never listed as projects.
        """
        if not root.exists() or not root.is_dir():
            return []
        subdirs = []
        try:
            for d in root.iterdir():
                if d.is_dir() and not d.name.startswith(".") and d.name not in RESERVED_DIR_NAMES:
                    if (d / "state.json").exists() or (d / "artifacts").exists() or (d / "tasks").exists() or (d / "jobs").exists():
                        subdirs.append(d)
        except Exception:
            pass
        return subdirs

    def _get_subproject_dirs(self) -> List[Path]:
        """Find any project blackboard subdirectories under root_dir."""
        return self.find_project_dirs(self.root_dir)

    @staticmethod
    def _clean_relative_path(relative_path: str) -> str:
        return (
            relative_path.replace("\\", "/")
            .replace("blackboard/artifacts/", "")
            .lstrip("/")
        )

    def initialize(self) -> None:
        """Create the blackboard folder hierarchy and initial state if not present."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.usage_dir.mkdir(parents=True, exist_ok=True)

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
        if (
            self.root_dir.exists()
            and self.state_file.exists()
            and self.tasks_dir.exists()
            and self.artifacts_dir.exists()
        ):
            return True
        if self.project and self.root_dir != self.base_root_dir:
            if (
                self.base_root_dir.exists()
                and (
                    (self.base_root_dir / "state.json").exists()
                    or (self.base_root_dir / "artifacts").exists()
                    or (self.base_root_dir / "tasks").exists()
                )
            ):
                return True
        if not self.project:
            for sub in self._get_subproject_dirs():
                if (sub / "state.json").exists() and (sub / "tasks").exists():
                    return True
        return False

    # ---------------- State Management ---------------- #

    def load_state(self) -> Dict[str, Any]:
        """Load state.json contents."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                return {}
        if not self.project:
            for sub in self._get_subproject_dirs():
                sub_state = sub / "state.json"
                if sub_state.exists():
                    try:
                        with open(sub_state, "r", encoding="utf-8-sig") as f:
                            return json.load(f)
                    except Exception:
                        pass
        return {}

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
        if task_path.exists():
            try:
                with open(task_path, "r", encoding="utf-8-sig") as f:
                    return Task.from_dict(json.load(f))
            except Exception:
                return None
        if self.project and self.root_dir != self.base_root_dir:
            base_task = self.base_root_dir / "tasks" / f"{task_id}.json"
            if base_task.exists():
                try:
                    with open(base_task, "r", encoding="utf-8-sig") as f:
                        return Task.from_dict(json.load(f))
                except Exception:
                    pass
        elif not self.project:
            for sub in self._get_subproject_dirs():
                sub_task = sub / "tasks" / f"{task_id}.json"
                if sub_task.exists():
                    try:
                        with open(sub_task, "r", encoding="utf-8-sig") as f:
                            return Task.from_dict(json.load(f))
                    except Exception:
                        pass
        return None

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

    def clear_tasks(self) -> int:
        """Clear all active subtasks from tasks/ directory for a fresh execution."""
        count = 0
        if self.tasks_dir.exists():
            for file in self.tasks_dir.glob("*.json"):
                try:
                    file.unlink()
                    count += 1
                except Exception:
                    pass
        return count

    def list_tasks(self) -> List[Task]:
        """List all tasks sorted by task ID."""
        tasks: List[Task] = []
        task_ids = set()
        if self.tasks_dir.exists():
            for file in sorted(self.tasks_dir.glob("*.json")):
                try:
                    with open(file, "r", encoding="utf-8-sig") as f:
                        t = Task.from_dict(json.load(f))
                        tasks.append(t)
                        task_ids.add(t.id)
                except Exception:
                    continue
        if self.project and self.root_dir != self.base_root_dir:
            base_tasks_dir = self.base_root_dir / "tasks"
            if base_tasks_dir.exists():
                for file in sorted(base_tasks_dir.glob("*.json")):
                    try:
                        with open(file, "r", encoding="utf-8-sig") as f:
                            t = Task.from_dict(json.load(f))
                            if t.id not in task_ids:
                                tasks.append(t)
                                task_ids.add(t.id)
                    except Exception:
                        continue
        elif not self.project:
            for sub in self._get_subproject_dirs():
                sub_tasks_dir = sub / "tasks"
                if sub_tasks_dir.exists():
                    for file in sorted(sub_tasks_dir.glob("*.json")):
                        try:
                            with open(file, "r", encoding="utf-8-sig") as f:
                                t = Task.from_dict(json.load(f))
                                if t.id not in task_ids:
                                    tasks.append(t)
                                    task_ids.add(t.id)
                        except Exception:
                            continue
        return sorted(tasks, key=lambda x: x.id)

    # ---------------- Artifact Management ---------------- #

    def resolve_artifact_path(self, relative_path: str) -> Path:
        """Resolve a relative artifact path under blackboard/artifacts/."""
        clean_path = self._clean_relative_path(relative_path)
        direct = self.artifacts_dir / clean_path
        if direct.exists():
            return direct
        if self.project:
            if self.root_dir != self.base_root_dir:
                base_art = self.base_root_dir / "artifacts" / clean_path
                if base_art.exists():
                    meta_file = base_art.with_name(f".{base_art.name}.meta.json")
                    if meta_file.exists():
                        try:
                            with open(meta_file, "r", encoding="utf-8-sig") as f:
                                m = json.load(f)
                            proj_meta = (
                                m.get("custom", {}).get("project")
                                if isinstance(m.get("custom"), dict)
                                else m.get("project")
                            )
                            if proj_meta == self.project:
                                return base_art
                        except Exception:
                            pass
            return direct
        for sub_dir in self._get_subproject_dirs():
            sub_art = sub_dir / "artifacts" / clean_path
            if sub_art.exists():
                return sub_art
        return direct

    def write_artifact(
        self,
        relative_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        author_agent: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Path:
        """Write content and companion metadata to blackboard/artifacts/."""
        target_path = self.resolve_artifact_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        effective_job = job_id or ((metadata or {}).get("job_id") if isinstance(metadata, dict) else None)

        # Archive previous version to .history/ if file already exists with different content
        if target_path.exists() and not target_path.name.startswith("."):
            try:
                old_content = target_path.read_text(encoding="utf-8", errors="ignore")
                if old_content.strip() != content.strip():
                    history_dir = self.artifacts_dir / ".history"
                    history_dir.mkdir(parents=True, exist_ok=True)
                    mtime = os.path.getmtime(target_path)
                    old_ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")
                    archived_name = f"{target_path.stem}_{old_ts}{target_path.suffix}"
                    (history_dir / archived_name).write_text(old_content, encoding="utf-8")
            except Exception:
                pass

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)

        meta_file = target_path.with_name(f".{target_path.name}.meta.json")
        meta_payload = {
            "path": relative_path,
            "author": author_agent or "unknown",
            "job_id": effective_job,
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
                    payload={"artifact_path": relative_path, "size_bytes": len(content), "job_id": effective_job},
                )
            )

        return target_path

    def list_artifacts_detailed(self, newest_first: bool = True) -> List[Dict[str, Any]]:
        """List all artifacts with path, created_at, author, job_id, size_bytes, and formatted time."""
        paths = self.list_artifacts()
        detailed: List[Dict[str, Any]] = []
        for rel in paths:
            meta = self.read_artifact_metadata(rel) or {}
            target_p = self.resolve_artifact_path(rel)
            size = meta.get("size_bytes")
            if size is None and target_p.exists():
                try:
                    size = target_p.stat().st_size
                except Exception:
                    size = 0
            created = meta.get("created_at")
            if not created and target_p.exists():
                try:
                    created = datetime.datetime.fromtimestamp(target_p.stat().st_mtime).isoformat()
                except Exception:
                    created = ""
            author = meta.get("author") or "unknown"
            custom_data = meta.get("custom")
            job_id = meta.get("job_id") or (custom_data.get("job_id") if isinstance(custom_data, dict) else None)

            time_display = ""
            if created:
                try:
                    dt = datetime.datetime.fromisoformat(created)
                    time_display = dt.strftime("%H:%M:%S")
                except Exception:
                    time_display = str(created)[:19]

            detailed.append({
                "path": rel,
                "name": rel,
                "created_at": created or "",
                "time_str": time_display,
                "author": author,
                "job_id": job_id,
                "size_bytes": size or 0,
            })

        if newest_first:
            detailed.sort(key=lambda x: x["created_at"] or "", reverse=True)
        else:
            detailed.sort(key=lambda x: x["created_at"] or "")
        return detailed

    def read_artifact(self, relative_path: str) -> str:
        """Read artifact file content as a string."""
        target_path = self.resolve_artifact_path(relative_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Artifact not found: {relative_path} (resolved: {target_path})")
        with open(target_path, "r", encoding="utf-8-sig") as f:
            return f.read()

    def read_artifact_metadata(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Read companion metadata for an artifact."""
        try:
            target_path = self.resolve_artifact_path(relative_path)
            meta_file = target_path.with_name(f".{target_path.name}.meta.json")
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            if not self.project:
                clean_path = self._clean_relative_path(relative_path)
                for sub in self._get_subproject_dirs():
                    sub_meta = sub / "artifacts" / Path(clean_path).parent / f".{Path(clean_path).name}.meta.json"
                    if sub_meta.exists():
                        with open(sub_meta, "r", encoding="utf-8-sig") as f:
                            return json.load(f)
        except Exception:
            return None
        return None

    def has_artifact(self, relative_path: str) -> bool:
        """Check if an artifact exists."""
        clean_path = self._clean_relative_path(relative_path)
        if (self.artifacts_dir / clean_path).exists():
            return True
        if self.project:
            if self.root_dir != self.base_root_dir:
                base_art = self.base_root_dir / "artifacts" / clean_path
                if base_art.exists():
                    meta_file = base_art.with_name(f".{base_art.name}.meta.json")
                    if meta_file.exists():
                        try:
                            with open(meta_file, "r", encoding="utf-8-sig") as f:
                                m = json.load(f)
                            proj_meta = (
                                m.get("custom", {}).get("project")
                                if isinstance(m.get("custom"), dict)
                                else m.get("project")
                            )
                            if proj_meta == self.project:
                                return True
                        except Exception:
                            pass
        else:
            for sub_dir in self._get_subproject_dirs():
                if (sub_dir / "artifacts" / clean_path).exists():
                    return True
        return False

    def list_artifacts(self) -> List[str]:
        """List all artifact paths relative to artifacts/ (excluding meta files)."""
        artifacts = set()
        if self.artifacts_dir.exists():
            try:
                for p in sorted(self.artifacts_dir.rglob("*")):
                    if p.is_file() and not p.name.startswith("."):
                        artifacts.add(p.relative_to(self.artifacts_dir).as_posix())
            except Exception:
                pass
        if self.project and self.root_dir != self.base_root_dir:
            base_art_dir = self.base_root_dir / "artifacts"
            if base_art_dir.exists():
                try:
                    for p in sorted(base_art_dir.rglob("*")):
                        if p.is_file() and not p.name.startswith("."):
                            rel = p.relative_to(base_art_dir).as_posix()
                            meta_file = p.with_name(f".{p.name}.meta.json")
                            if meta_file.exists():
                                try:
                                    with open(meta_file, "r", encoding="utf-8-sig") as f:
                                        m = json.load(f)
                                    proj_meta = (
                                        m.get("custom", {}).get("project")
                                        if isinstance(m.get("custom"), dict)
                                        else m.get("project")
                                    )
                                    if proj_meta == self.project:
                                        artifacts.add(rel)
                                except Exception:
                                    pass
                except Exception:
                    pass
        elif not self.project:
            for sub_dir in self._get_subproject_dirs():
                sub_art_dir = sub_dir / "artifacts"
                if sub_art_dir.exists():
                    try:
                        for p in sorted(sub_art_dir.rglob("*")):
                            if p.is_file() and not p.name.startswith("."):
                                artifacts.add(p.relative_to(sub_art_dir).as_posix())
                    except Exception:
                        pass
        return sorted(list(artifacts))

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

    # ---------------- Jobs Management ---------------- #

    def save_job(self, job_dict: Dict[str, Any]) -> Path:
        """Save job state to blackboard jobs directory."""
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        job_id = job_dict.get("id", "job_unknown")
        file_path = self.jobs_dir / f"{job_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(job_dict, f, indent=2, ensure_ascii=False)
        return file_path

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all saved jobs for this blackboard, sorted by started_at descending."""
        if not self.jobs_dir.exists():
            return []
        jobs = []
        for p in self.jobs_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        jobs.append(data)
            except Exception:
                pass
        return sorted(jobs, key=lambda x: x.get("started_at", 0), reverse=True)

    def load_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load a specific job by ID from blackboard jobs directory."""
        file_path = self.jobs_dir / f"{job_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # ---------------- Usage & Limit Tracking ---------------- #

    def record_usage(
        self,
        agent: str,
        stdout: str,
        stderr: str,
        duration_sec: float,
        job_id: Optional[str] = None,
        model: Optional[str] = None,
        prompt_length: int = 0,
        is_success: bool = True,
        override_usage: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Record usage and check limits via the usage tracker."""
        return self.usage_tracker.record_turn(
            agent=agent,
            stdout=stdout,
            stderr=stderr,
            duration_sec=duration_sec,
            job_id=job_id,
            model=model,
            prompt_length=prompt_length,
            is_success=is_success,
            override_usage=override_usage,
        )

    def get_agent_usage(self, agent: str) -> Dict[str, Any]:
        """Return 5-hour and weekly usage metrics and status for an agent."""
        return self.usage_tracker.get_agent_status(agent)

    def get_usage_summary(self, agent_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Return usage summary for all requested or recorded agents."""
        return self.usage_tracker.get_all_agents_summary(agent_names)

