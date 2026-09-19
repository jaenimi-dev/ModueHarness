"""UI Controller and Session Bridge for ModueHarness.

Provides a unified programmatic interface for both Web (NiceGUI) and Terminal (Textual)
interfaces to interact with the underlying InteractiveSession, Blackboard, and AI agents.
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from modue_harness.engine.interactive import BackgroundJob, InteractiveSession


class UIController:
    """Bridges UI frontend frameworks to the ModueHarness core engine."""

    def __init__(
        self,
        project_name: str = "default",
        projects_root: Optional[Path] = None,
        blackboard_dir: Optional[Path] = None,
        agents_file: Optional[Path] = None,
        specific_agent: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.session = InteractiveSession(
            project_name=project_name,
            projects_root=projects_root,
            blackboard_dir=blackboard_dir,
            agents_file=agents_file,
            specific_agent=specific_agent,
            model=model,
            effort=effort,
            timeout=timeout,
        )

    @property
    def project_name(self) -> str:
        return self.session.project_name

    @property
    def project_dir(self) -> Path:
        return self.session.project_dir

    @property
    def blackboard_dir(self) -> Path:
        return self.session.blackboard_dir

    @property
    def timeout(self) -> Optional[float]:
        return self.session.timeout

    def get_projects(self) -> List[str]:
        """List all existing projects under the projects root."""
        return self.session.list_projects()

    def switch_project(self, project_name: str) -> Path:
        """Switch active target project folder."""
        return self.session.switch_project(project_name)

    def get_agents_info(self) -> List[Dict[str, Any]]:
        """Return information about configured AI agents."""
        info = []
        for name, agent in self.session.agents.items():
            adapter_type = "generic"
            cls_name = agent.__class__.__name__.lower()
            if "claude" in cls_name:
                adapter_type = "claude"
            elif "agy" in cls_name or "antigravity" in cls_name:
                adapter_type = "agy"
            elif "aider" in cls_name:
                adapter_type = "aider"

            info.append({
                "name": name,
                "adapter": adapter_type,
                "adapter_cls": agent.__class__.__name__,
                "model": getattr(agent, "model", None),
                "effort": getattr(agent, "effort", None),
                "command": getattr(agent, "command", "N/A"),
                "system_instruction": getattr(agent, "system_instruction", ""),
                "is_leader": name == self.session.conductor_name,
            })
        return info

    def set_model(self, model: Optional[str], agent_name: Optional[str] = None) -> List[str]:
        """Dynamically update model for an agent or all agents."""
        return self.session.set_model(model, agent_name=agent_name)

    def set_effort(self, effort: Optional[str], agent_name: Optional[str] = None) -> List[str]:
        """Dynamically update reasoning effort level."""
        return self.session.set_effort(effort, agent_name=agent_name)

    def set_timeout(self, timeout: Optional[float]) -> Optional[float]:
        """Update session execution timeout in seconds (None for unlimited)."""
        return self.session.set_timeout(timeout)

    def set_conductor(self, agent_name: str) -> bool:
        """Set an existing agent as the team leader/conductor."""
        return self.session.set_conductor(agent_name)

    def add_agent(
        self,
        name: str,
        adapter_type: str = "claude",
        model: Optional[str] = None,
        effort: Optional[str] = None,
        is_conductor: bool = False,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a new agent or replace an existing one."""
        self.session.add_agent(
            name=name,
            adapter_type=adapter_type,
            model=model,
            effort=effort,
            is_conductor=is_conductor,
            system_instruction=system_instruction,
        )
        return {"name": name, "success": True}

    def remove_agent(self, name: str) -> bool:
        """Remove an agent from the active session."""
        return self.session.remove_agent(name)

    def update_agent(
        self,
        name: str,
        adapter_type: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        is_conductor: Optional[bool] = None,
        system_instruction: Optional[str] = None,
    ) -> bool:
        """Update an agent's configuration."""
        return self.session.update_agent(
            name=name,
            adapter_type=adapter_type,
            model=model,
            effort=effort,
            is_conductor=is_conductor,
            system_instruction=system_instruction,
        )

    def get_status(self) -> Dict[str, Any]:
        """Return current status summary of session and blackboard."""
        state = self.session.blackboard.load_state() if self.session.blackboard.is_initialized() else {}
        running_jobs = [j for j in self.session.jobs.values() if j.status == "running"]
        return {
            "project_name": self.session.project_name,
            "project_dir": str(self.session.project_dir),
            "blackboard_dir": str(self.session.blackboard_dir),
            "timeout": self.session.timeout,
            "session_id": state.get("session_id", "N/A"),
            "status": state.get("status", "idle"),
            "running_jobs_count": len(running_jobs),
            "tasks_count": len(self.session.blackboard.list_tasks()) if self.session.blackboard.is_initialized() else 0,
            "artifacts_count": len(self.session.blackboard.list_artifacts()) if self.session.blackboard.is_initialized() else 0,
        }

    def get_artifacts(self) -> List[Dict[str, Any]]:
        """List artifacts available on the blackboard."""
        if not self.session.blackboard.is_initialized():
            return []
        results = []
        for name in self.session.blackboard.list_artifacts():
            p = self.session.blackboard.artifacts_dir / name
            size = p.stat().st_size if p.exists() else 0
            mtime = p.stat().st_mtime if p.exists() else 0
            results.append({
                "name": name,
                "size_bytes": size,
                "modified_at": mtime,
                "path": str(p),
            })
        return results

    def get_artifact_content(self, name: str) -> str:
        """Read artifact content as string."""
        content = self.session.blackboard.read_artifact(name)
        return content if content is not None else ""

    def get_tasks(self) -> List[Dict[str, Any]]:
        """List task objects from the blackboard."""
        if not self.session.blackboard.is_initialized():
            return []
        tasks = []
        for t in self.session.blackboard.list_tasks():
            tasks.append({
                "id": t.id,
                "title": t.title,
                "assigned_agent": t.assigned_agent,
                "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                "instruction": t.description,
                "output_artifact": t.output_artifact,
            })
        return tasks

    def get_project_files(self) -> List[str]:
        """List implementation files inside current project directory."""
        return self.session.list_project_files()

    def get_project_file_content(self, rel_path: str) -> str:
        """Read content of a file within the current project directory."""
        target = (self.session.project_dir / rel_path).resolve()
        if not target.is_relative_to(self.session.project_dir) or not target.is_file():
            return ""
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def get_jobs(self) -> List[Dict[str, Any]]:
        """List background jobs and statuses."""
        jobs_list = []
        for j in self.session.jobs.values():
            jobs_list.append({
                "id": j.id,
                "command": j.command,
                "status": j.status,
                "stage": j.stage,
                "duration_sec": j.duration_sec,
                "error": j.error,
                "started_at": j.started_at,
            })
        return sorted(jobs_list, key=lambda x: x["started_at"], reverse=True)

    def cancel_job(self, job_id: Optional[str] = None) -> bool:
        """Cancel a running background job or active foreground job."""
        if job_id:
            job = self.session.jobs.get(job_id)
            if job and job.status == "running" and job.runner:
                job.runner.cancel()
                job.status = "cancelled"
                job.stage = "cancelled by user"
                return True
            return False
        # If no job_id specified, cancel active foreground runner if any
        if self.session._active_foreground_runner:
            self.session._active_foreground_runner.cancel()
            return True
        return False

    def execute_command(
        self,
        command: str,
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute a natural-language task synchronously."""
        return self.session.execute_command(command, live_progress=True)

    def execute_command_async(self, command: str) -> BackgroundJob:
        """Execute a natural-language task asynchronously in background."""
        return self.session.execute_command_async(command)
