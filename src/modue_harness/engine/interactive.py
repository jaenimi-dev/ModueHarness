"""Interactive CLI execution session, background job management, and live progress streaming."""

from dataclasses import dataclass, field
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from modue_harness.adapters import (
    BaseCLIAdapter,
    ClaudeCLIAdapter,
    AGYCLIAdapter,
    AiderCLIAdapter,
    CodexCLIAdapter,
    GenericCLIAdapter,
    create_adapter,
)
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.events import EventBus
from modue_harness.engine.conductor import ConductorRunner
from modue_harness.engine.workflow import _parse_file


@dataclass
class BackgroundJob:
    """Represents an asynchronous background job executed by the harness."""

    id: str
    command: str
    project: str
    project_dir: Path
    status: str = "running"  # "running", "completed", "failed", "cancelled"
    stage: str = "planning"  # "planning", "task: ...", "synthesis", "done"
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    runner: Optional[ConductorRunner] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    thread: Optional[threading.Thread] = None
    logs: List[str] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "project": self.project,
            "project_dir": str(self.project_dir),
            "status": self.status,
            "stage": self.stage,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_sec": self.duration_sec,
            "error": self.error,
            "logs": list(self.logs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackgroundJob":
        return cls(
            id=data.get("id", "job_unknown"),
            command=data.get("command", ""),
            project=data.get("project", ""),
            project_dir=Path(data.get("project_dir", ".")),
            status=data.get("status", "completed"),
            stage=data.get("stage", "done"),
            started_at=data.get("started_at", time.time()),
            ended_at=data.get("ended_at"),
            error=data.get("error"),
            logs=list(data.get("logs", [])),
        )


def load_or_detect_agents(
    agents_file: Optional[Path] = None,
    specific_agent: Optional[str] = None,
    model: Optional[str] = None,
    effort: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, BaseCLIAdapter]:
    """Load agents from YAML file or auto-detect available AI CLI tools on the system."""
    base_dir = cwd or Path.cwd()

    # 1. User specified a single agent adapter directly
    if specific_agent:
        kwargs: Dict[str, Any] = {}
        if specific_agent.lower() in ["generic", "echo"]:
            kwargs = {"command": sys.executable, "default_args": ["-c", "import sys; print('[]')"]}
        elif specific_agent.lower() in ["claude", "claude-code"]:
            kwargs = {"command": "claude", "default_args": ["--permission-mode", "auto"]}
            if model:
                kwargs["model"] = model
            if effort:
                kwargs["effort"] = effort
        elif specific_agent.lower() in ["agy", "antigravity"]:
            kwargs = {"command": "agy"}
            if model:
                kwargs["model"] = model
            if effort:
                kwargs["effort"] = effort
        elif specific_agent.lower() == "aider":
            kwargs = {"command": "aider"}
            if model:
                kwargs["model"] = model
        elif specific_agent.lower() in ["codex", "chatgpt"]:
            kwargs = {"command": "codex"}
            if model:
                kwargs["model"] = model
            if effort:
                kwargs["effort"] = effort
        return {specific_agent: create_adapter(specific_agent, name=specific_agent, **kwargs)}

    # 2. User specified agents file
    target_file: Optional[Path] = None
    if agents_file and agents_file.exists():
        target_file = agents_file
    elif (base_dir / "config" / "agents.yaml").exists():
        target_file = base_dir / "config" / "agents.yaml"
    elif (base_dir / "agents.yaml").exists():
        target_file = base_dir / "agents.yaml"

    if target_file:
        try:
            data = _parse_file(target_file)
            agents_dict = data.get("agents", data)
            loaded = {}
            for name, cfg in agents_dict.items():
                if isinstance(cfg, dict):
                    adapter_type = cfg.get("adapter", "generic")
                    kwargs = {"name": name, "default_args": cfg.get("args", [])}
                    if cfg.get("command"):
                        kwargs["command"] = cfg["command"]
                    agent_model = model or cfg.get("model")
                    if agent_model:
                        kwargs["model"] = agent_model
                    agent_effort = effort or cfg.get("effort")
                    if agent_effort:
                        kwargs["effort"] = agent_effort
                    if cfg.get("system_instruction"):
                        kwargs["system_instruction"] = cfg["system_instruction"]
                    loaded[name] = create_adapter(adapter_type, **kwargs)
            if loaded:
                return loaded
        except Exception:
            pass

    # 3. Auto-detect installed AI CLI tools on system PATH or local installation directories
    def _find_bin(cmd_name: str) -> Optional[str]:
        p = shutil.which(cmd_name)
        if p:
            return p
        candidate_local = Path.home() / ".local" / "bin" / cmd_name
        if candidate_local.is_file() and os.access(candidate_local, os.X_OK):
            return str(candidate_local)
        candidate_gemini = Path.home() / ".gemini" / "antigravity-cli" / "bin" / cmd_name
        if candidate_gemini.is_file() and os.access(candidate_gemini, os.X_OK):
            return str(candidate_gemini)
        return None

    claude_bin = _find_bin("claude")
    agy_bin = _find_bin("agy")
    codex_bin = _find_bin("codex")
    aider_bin = _find_bin("aider")

    if claude_bin:
        return {
            "architect": ClaudeCLIAdapter(
                name="architect",
                command=claude_bin,
                model=model,
                effort=effort,
                default_args=["--permission-mode", "auto"],
                system_instruction="You design modular software architecture and decompose tasks clearly.",
            ),
            "developer": ClaudeCLIAdapter(
                name="developer",
                command=claude_bin,
                model=model,
                effort=effort,
                default_args=["--permission-mode", "auto"],
                system_instruction="You write clean, tested, production-ready code in the project directory.",
            ),
            "reviewer": ClaudeCLIAdapter(
                name="reviewer",
                command=claude_bin,
                model=model,
                effort=effort,
                default_args=["--permission-mode", "auto"],
                system_instruction="You verify and review implementation code and write test validations.",
            ),
        }

    if agy_bin:
        return {
            "architect": AGYCLIAdapter(
                name="architect",
                command=agy_bin,
                model=model,
                effort=effort,
                system_instruction="You design modular software architecture and decompose tasks clearly.",
            ),
            "developer": AGYCLIAdapter(
                name="developer",
                command=agy_bin,
                model=model,
                effort=effort,
                system_instruction="You write clean, tested, production-ready code in the project directory.",
            ),
            "reviewer": AGYCLIAdapter(
                name="reviewer",
                command=agy_bin,
                model=model,
                effort=effort,
                system_instruction="You verify and review implementation code and write test validations.",
            ),
        }

    if codex_bin:
        return {
            "architect": CodexCLIAdapter(
                name="architect",
                command=codex_bin,
                model=model,
                effort=effort,
                system_instruction="You design modular software architecture and decompose tasks clearly.",
            ),
            "developer": CodexCLIAdapter(
                name="developer",
                command=codex_bin,
                model=model,
                effort=effort,
                system_instruction="You write clean, tested, production-ready code in the project directory.",
            ),
            "reviewer": CodexCLIAdapter(
                name="reviewer",
                command=codex_bin,
                model=model,
                effort=effort,
                system_instruction="You verify and review implementation code and write test validations.",
            ),
        }

    if aider_bin:
        return {
            "developer": AiderCLIAdapter(
                name="developer",
                command="aider",
            )
        }

    # 4. Fallback generic agent
    return {
        "conductor": GenericCLIAdapter(
            name="conductor",
            command=sys.executable,
            default_args=["-c", "import sys; print('[]')"],
        ),
        "developer": GenericCLIAdapter(
            name="developer",
            command=sys.executable,
            default_args=["-c", "import sys; print('Executed task.')"],
        ),
    }


class InteractiveSession:
    """Manages an interactive session where commands are executed directly into a project folder,

    using the blackboard strictly for AI coordination, with support for live progress and background jobs.
    """

    def __init__(
        self,
        project_name: Optional[str] = None,
        projects_root: Optional[Path] = None,
        blackboard_dir: Optional[Path] = None,
        agents: Optional[Dict[str, BaseCLIAdapter]] = None,
        agents_file: Optional[Path] = None,
        specific_agent: Optional[str] = None,
        conductor_name: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.projects_root = (projects_root or (Path.cwd() / "projects")).resolve()
        raw_board_dir = (blackboard_dir or (Path.cwd() / "blackboard")).resolve()
        self.blackboard_root = raw_board_dir if raw_board_dir.name != project_name else raw_board_dir.parent

        if project_name:
            self.project_name = project_name.strip()
        else:
            existing = self.list_projects()
            non_default = [p for p in existing if p != "default"]
            if non_default:
                self.project_name = non_default[0]
            elif existing:
                self.project_name = existing[0]
            else:
                self.project_name = None

        if self.project_name:
            self.project_dir = self.projects_root / self.project_name
            self.blackboard_dir = self.blackboard_root / self.project_name
        else:
            self.project_dir = None
            self.blackboard_dir = None

        self.event_bus = event_bus or EventBus()
        self.blackboard = Blackboard(
            root_dir=self.blackboard_root,
            event_bus=self.event_bus,
            project=self.project_name,
        )

        self.model = model
        self.effort = effort
        self.timeout = timeout
        if agents_file:
            self.agents_file = Path(agents_file).resolve()
        else:
            base_dir = (projects_root.parent if projects_root else Path.cwd()).resolve()
            if (base_dir / "config" / "agents.yaml").exists():
                self.agents_file = (base_dir / "config" / "agents.yaml").resolve()
            elif (base_dir / "agents.yaml").exists():
                self.agents_file = (base_dir / "agents.yaml").resolve()
            else:
                self.agents_file = (base_dir / "config" / "agents.yaml").resolve()

        self.agents = agents or load_or_detect_agents(
            agents_file=self.agents_file,
            specific_agent=specific_agent,
            model=model,
            effort=effort,
            cwd=Path.cwd(),
        )

        if conductor_name and conductor_name in self.agents:
            self.conductor_name = conductor_name
        elif "architect" in self.agents:
            self.conductor_name = "architect"
        elif "conductor" in self.agents:
            self.conductor_name = "conductor"
        else:
            self.conductor_name = next(iter(self.agents.keys()))

        # Background Job Management
        self.jobs: Dict[str, BackgroundJob] = {}
        self._job_counter: int = 0
        self._active_foreground_runner: Optional[ConductorRunner] = None
        self.last_commands: List[Dict[str, Any]] = []

    def set_model(self, model: Optional[str], agent_name: Optional[str] = None) -> List[str]:
        """Update model dynamically for specified agent or all supporting Claude/AI agents."""
        updated = []
        targets = [agent_name] if agent_name else list(self.agents.keys())
        for name in targets:
            agent = self.agents.get(name)
            if agent:
                if hasattr(agent, "set_model"):
                    agent.set_model(model)
                    updated.append(name)
                elif hasattr(agent, "model"):
                    setattr(agent, "model", model)
                    updated.append(name)
        return updated

    def set_effort(self, effort: Optional[str], agent_name: Optional[str] = None) -> List[str]:
        """Update reasoning effort level dynamically (low, medium, high, xhigh, max)."""
        updated = []
        targets = [agent_name] if agent_name else list(self.agents.keys())
        for name in targets:
            agent = self.agents.get(name)
            if agent:
                if hasattr(agent, "set_effort"):
                    agent.set_effort(effort)
                    updated.append(name)
                elif hasattr(agent, "effort"):
                    setattr(agent, "effort", effort)
                    updated.append(name)
        return updated

    def set_timeout(self, timeout: Optional[float]) -> Optional[float]:
        """Update session execution timeout in seconds (None for unlimited)."""
        self.timeout = timeout
        return self.timeout

    def save_agents_config(self, filepath: Optional[Path] = None) -> Path:
        """Persist current AI team configuration to YAML config file."""
        import yaml

        target = filepath or self.agents_file or (Path.cwd() / "config" / "agents.yaml")
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

        agents_data: Dict[str, Any] = {}
        for name, agent in self.agents.items():
            adapter_type = "generic"
            cls_name = agent.__class__.__name__.lower()
            if "claude" in cls_name:
                adapter_type = "claude"
            elif "agy" in cls_name or "antigravity" in cls_name:
                adapter_type = "agy"
            elif "aider" in cls_name:
                adapter_type = "aider"

            entry: Dict[str, Any] = {
                "adapter": adapter_type,
            }
            cmd = getattr(agent, "command", None)
            if cmd and cmd != "generic" and not ("python" in str(cmd).lower()):
                entry["command"] = cmd
            args = getattr(agent, "default_args", None)
            if args:
                entry["args"] = args
            mod = getattr(agent, "model", None)
            if mod:
                entry["model"] = mod
            eff = getattr(agent, "effort", None)
            if eff:
                entry["effort"] = eff
            ins = getattr(agent, "system_instruction", None)
            if ins:
                entry["system_instruction"] = ins

            agents_data[name] = entry

        doc = {
            "version": "0.8.0",
            "name": "modue-harness-team",
            "conductor": self.conductor_name,
            "agents": agents_data,
        }

        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)

        self.agents_file = target
        return target

    def set_conductor(self, agent_name: str) -> bool:
        """Set an existing agent as the team leader/conductor."""
        if agent_name in self.agents:
            self.conductor_name = agent_name
            try:
                self.save_agents_config()
            except Exception:
                pass
            return True
        return False

    def add_agent(
        self,
        name: str,
        adapter_type: str = "claude",
        model: Optional[str] = None,
        effort: Optional[str] = None,
        is_conductor: bool = False,
        system_instruction: Optional[str] = None,
    ) -> BaseCLIAdapter:
        """Dynamically add or replace an agent in the active session."""
        kwargs: Dict[str, Any] = {"name": name}
        if model:
            kwargs["model"] = model
        if effort:
            kwargs["effort"] = effort
        if system_instruction:
            kwargs["system_instruction"] = system_instruction

        adapter = create_adapter(adapter_type, **kwargs)
        self.agents[name] = adapter
        if is_conductor:
            self.conductor_name = name
        try:
            self.save_agents_config()
        except Exception:
            pass
        return adapter

    def remove_agent(self, name: str) -> bool:
        """Remove an agent from the session (keeps at least one)."""
        if len(self.agents) <= 1:
            return False
        if name in self.agents:
            del self.agents[name]
            if self.conductor_name == name:
                self.conductor_name = next(iter(self.agents.keys()))
            try:
                self.save_agents_config()
            except Exception:
                pass
            return True
        return False

    def update_agent(
        self,
        name: str,
        adapter_type: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        is_conductor: Optional[bool] = None,
        system_instruction: Optional[str] = None,
    ) -> bool:
        """Update an existing agent's configuration or recreate with a new adapter type."""
        agent = self.agents.get(name)
        if not agent:
            return False

        current_adapter = "generic"
        cls_name = agent.__class__.__name__.lower()
        if "claude" in cls_name:
            current_adapter = "claude"
        elif "agy" in cls_name or "antigravity" in cls_name:
            current_adapter = "agy"
        elif "aider" in cls_name:
            current_adapter = "aider"
        elif "codex" in cls_name or "chatgpt" in cls_name:
            current_adapter = "codex"

        target_adapter = (adapter_type or current_adapter).lower()
        if target_adapter != current_adapter:
            kwargs: Dict[str, Any] = {
                "name": name,
                "model": model if model is not None else getattr(agent, "model", None),
                "effort": effort if effort is not None else getattr(agent, "effort", None),
                "system_instruction": system_instruction if system_instruction is not None else getattr(agent, "system_instruction", None),
            }
            self.agents[name] = create_adapter(target_adapter, **kwargs)
        else:
            if model is not None:
                if hasattr(agent, "set_model"):
                    agent.set_model(model)
                elif hasattr(agent, "model"):
                    setattr(agent, "model", model)
            if effort is not None:
                if hasattr(agent, "set_effort"):
                    agent.set_effort(effort)
                elif hasattr(agent, "effort"):
                    setattr(agent, "effort", effort)
            if system_instruction is not None and hasattr(agent, "system_instruction"):
                setattr(agent, "system_instruction", system_instruction)

        if is_conductor:
            self.conductor_name = name

        try:
            self.save_agents_config()
        except Exception:
            pass
        return True

    def switch_project(self, project_name: str) -> Path:
        """Switch current target project to a new or existing project folder and isolated blackboard."""
        clean_name = project_name.strip()
        if not clean_name:
            raise ValueError("Project name cannot be empty.")

        self.project_name = clean_name
        self.project_dir = self.projects_root / self.project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.blackboard_dir = self.blackboard_root / self.project_name
        self.blackboard = Blackboard(
            root_dir=self.blackboard_root,
            event_bus=self.event_bus,
            project=self.project_name,
        )
        self.blackboard.initialize()
        self.blackboard.update_state({
            "current_project": self.project_name,
            "project_dir": str(self.project_dir),
        })

        # Load any persisted jobs for this project from blackboard
        if hasattr(self.blackboard, "list_jobs"):
            try:
                for j_data in self.blackboard.list_jobs():
                    jid = j_data.get("id")
                    if jid and jid not in self.jobs:
                        self.jobs[jid] = BackgroundJob.from_dict(j_data)
            except Exception:
                pass

        return self.project_dir

    def list_projects(self) -> List[str]:
        """List all existing project names under projects_root and blackboard_root."""
        projects = set()
        if self.projects_root.exists():
            try:
                for p in self.projects_root.iterdir():
                    if p.is_dir() and not p.name.startswith("."):
                        projects.add(p.name)
            except Exception:
                pass
        if hasattr(self, "blackboard_root") and self.blackboard_root.exists():
            try:
                for p in self.blackboard_root.iterdir():
                    if (
                        p.is_dir()
                        and not p.name.startswith(".")
                        and p.name not in {"tasks", "artifacts", "logs", "jobs"}
                    ):
                        projects.add(p.name)
            except Exception:
                pass
        return sorted(list(projects))

    def delete_project(self, project_name: str) -> bool:
        """Delete project directory and its associated isolated blackboard."""
        clean_name = project_name.strip()
        if not clean_name:
            return False

        import shutil
        # 1. Remove from projects_root
        proj_dir = self.projects_root / clean_name
        if proj_dir.exists():
            try:
                shutil.rmtree(proj_dir)
            except Exception:
                pass

        # 2. Remove from blackboard_root
        if hasattr(self, "blackboard_root") and self.blackboard_root.exists():
            bb_proj_dir = self.blackboard_root / clean_name
            if bb_proj_dir.exists():
                try:
                    shutil.rmtree(bb_proj_dir)
                except Exception:
                    pass

        # 3. If currently active project was deleted, switch to another project or clear
        if self.project_name == clean_name:
            remaining = [p for p in self.list_projects() if p != clean_name]
            if remaining:
                self.switch_project(remaining[0])
            else:
                self.project_name = None
                self.project_dir = None
                self.blackboard_dir = self.blackboard_root
                self.blackboard = Blackboard(root_dir=self.blackboard_root, event_bus=self.event_bus)

        return True

    def list_project_files(self) -> List[str]:
        """List all implementation files inside the active project folder."""
        if not self.project_dir or not self.project_dir.exists():
            return []
        files = []
        try:
            for p in self.project_dir.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    try:
                        files.append(p.relative_to(self.project_dir).as_posix())
                    except Exception:
                        pass
        except Exception:
            pass
        return sorted(files)

    def execute_command(
        self,
        command: str,
        live_progress: bool = True,
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Execute a user natural-language command synchronously.

        Live progress updates are printed to stdout if live_progress is True,
        and forwarded to on_progress callback if supplied.
        """
        command = command.strip()
        if not command:
            return {"success": False, "error": "Empty command"}

        if not self.project_name:
            existing = self.list_projects()
            non_default = [p for p in existing if p != "default"]
            if non_default:
                self.switch_project(non_default[0])
            elif existing:
                self.switch_project(existing[0])
            else:
                self.switch_project("project_1")

        # Ensure project and blackboard directories exist
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.blackboard.initialize()

        self.blackboard.update_state({
            "current_project": self.project_name,
            "project_dir": str(self.project_dir),
            "last_command": command,
            "status": "executing",
            "last_command_at": datetime.datetime.now().isoformat(),
        })

        self.last_commands = []

        self._job_counter += 1
        job_id = f"job_{self._job_counter}"

        job = BackgroundJob(
            id=job_id,
            command=command,
            project=self.project_name,
            project_dir=self.project_dir,
            status="running",
            stage="기획 중 (planning)",
        )
        self.jobs[job_id] = job
        if hasattr(self.blackboard, "save_job"):
            try:
                self.blackboard.save_job(job.to_dict())
            except Exception:
                pass

        def _console_progress(event: str, data: Dict[str, Any]) -> None:
            lines = []
            if event == "planning_start":
                job.stage = "기획 중 (planning)"
                lines.append(f"  [1/3] 🧠 Conductor({data.get('conductor')}) 작업 목표 분석 및 계획 수립 중...")
                if data.get("command"):
                    lines.append(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": "기획 (Planning)",
                        "agent": data.get("conductor"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "planning_end":
                if data.get("is_success"):
                    job.stage = "서브태스크 준비"
                    tasks = data.get("tasks", [])
                    lines.append(f"  ✓ 기획 완료: {len(tasks)}개 서브태스크 생성 (blackboard/tasks)")
                    for t in tasks:
                        desc = (t.get("instruction") or "")[:200]
                        lines.append(f"    • [{t.get('id')}] {t.get('assigned_agent')}: {desc}")
                else:
                    job.stage = "기획 실패"
                    err_msg = data.get("error") or "계획 수립 실패"
                    lines.append(f"  ✗ 기획 실패: {err_msg}")
            elif event == "task_start":
                idx = data.get("index", 1)
                tot = data.get("total", 1)
                desc = (data.get("instruction") or "")[:200]
                job.stage = f"태스크 [{idx}/{tot}] {data.get('agent')} ({data.get('task_id')})"
                lines.append(f"  [2/3] 🛠️ [{idx}/{tot}] {data.get('agent')} 실행 중 ({data.get('task_id')})...")
                lines.append(f"        지시: {desc}")
                if data.get("command"):
                    lines.append(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": f"태스크 [{idx}/{tot}] {data.get('task_id')}",
                        "agent": data.get("agent"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "task_end":
                dur = data.get("duration_sec", 0.0)
                if data.get("is_success"):
                    lines.append(f"  ✓ [{data.get('task_id')}] 실행 완료 ({dur:.1f}s)")
                else:
                    err_str = data.get("error") or "서브태스크 실행 실패"
                    lines.append(f"  ✗ [{data.get('task_id')}] 실행 실패 ({dur:.1f}s)")
                    lines.append(f"        ❌ 서브태스크 실패 원인: {err_str}")
            elif event == "synthesis_start":
                job.stage = "최종 종합 보고서 작성 중 (synthesis)"
                lines.append(f"  [3/3] 📝 Conductor({data.get('conductor')}) 최종 검토 및 종합 보고서 작성 중...")
                if data.get("command"):
                    lines.append(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": "종합 검토 (Synthesis)",
                        "agent": data.get("conductor"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "synthesis_end":
                if data.get("is_success"):
                    job.stage = "완료 (done)"
                    lines.append("  ✓ 최종 종합 보고서 저장: blackboard/artifacts/synthesis_report.md")
                else:
                    job.stage = "보고서 작성 실패"
                    err_str = data.get("error") or "종합 보고서 작성 실패"
                    lines.append(f"  ✗ 최종 종합 보고서 작성 실패: {err_str}")

            job.logs.extend(lines)
            if hasattr(self.blackboard, "save_job"):
                try:
                    self.blackboard.save_job(job.to_dict())
                except Exception:
                    pass

            if live_progress:
                for l in lines:
                    print(l)

            if on_progress:
                payload = dict(data)
                payload["lines"] = lines
                try:
                    on_progress(event, payload)
                except Exception:
                    pass

        # Run Leader-Worker Conductor
        runner = ConductorRunner(
            goal=command,
            conductor_agent_name=self.conductor_name,
            worker_agents=self.agents,
            blackboard=self.blackboard,
            workspace_dir=self.project_dir,
            event_bus=self.event_bus,
            progress_callback=_console_progress,
            timeout=self.timeout,
        )
        self._active_foreground_runner = runner
        job.runner = runner

        try:
            result = runner.run()
        finally:
            self._active_foreground_runner = None
            job.ended_at = time.time()
            job.result = result
            job.status = result.get("status", "completed" if result.get("success") else "failed")
            job.error = result.get("error_message") or result.get("error")
            job.stage = "취소됨 (cancelled)" if job.status == "cancelled" else ("완료 (done)" if job.status == "completed" else "실패 (failed)")
            if hasattr(self.blackboard, "save_job"):
                try:
                    self.blackboard.save_job(job.to_dict())
                except Exception:
                    pass

        # Gather created files and artifacts
        project_files = self.list_project_files()
        artifacts = self.blackboard.list_artifacts()

        self.blackboard.update_state({
            "status": "idle",
            "last_result_status": result.get("status"),
        })

        return {
            "success": result.get("success", False),
            "status": result.get("status", "unknown"),
            "project": self.project_name,
            "project_dir": str(self.project_dir),
            "goal": command,
            "subtasks": result.get("subtasks", []),
            "total_duration_sec": result.get("total_duration_sec", 0.0),
            "project_files": project_files,
            "artifacts": artifacts,
            "error": result.get("error_message") or result.get("error"),
        }

    def execute_command_async(self, command: str) -> BackgroundJob:
        """Submit a command to run asynchronously in a background thread."""
        command = command.strip()
        if not self.project_name:
            existing = self.list_projects()
            non_default = [p for p in existing if p != "default"]
            if non_default:
                self.switch_project(non_default[0])
            elif existing:
                self.switch_project(existing[0])
            else:
                self.switch_project("project_1")

        self._job_counter += 1
        job_id = f"job_{self._job_counter}"

        job = BackgroundJob(
            id=job_id,
            command=command,
            project=self.project_name,
            project_dir=self.project_dir,
            status="running",
            stage="기획 중 (planning)",
        )
        self.jobs[job_id] = job

        # Ensure project and blackboard directories exist
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.blackboard.initialize()
        if hasattr(self.blackboard, "save_job"):
            try:
                self.blackboard.save_job(job.to_dict())
            except Exception:
                pass

        def _bg_worker():
            if job.status == "cancelled":
                return

            def _bg_progress(event: str, data: Dict[str, Any]):
                if job.status == "cancelled":
                    return
                lines = []
                if event == "planning_start":
                    job.stage = "기획 중 (planning)"
                    lines.append(f"  [1/3] 🧠 Conductor({data.get('conductor')}) 작업 목표 분석 및 계획 수립 중...")
                    if data.get("command"):
                        lines.append(f"        💻 CLI 실행: {data.get('command')}")
                elif event == "planning_end":
                    if data.get("is_success"):
                        job.stage = "서브태스크 준비"
                        tasks = data.get("tasks", [])
                        lines.append(f"  ✓ 기획 완료: {len(tasks)}개 서브태스크 생성 (blackboard/tasks)")
                        for t in tasks:
                            desc = (t.get("instruction") or "")[:200]
                            lines.append(f"    • [{t.get('id')}] {t.get('assigned_agent')}: {desc}")
                    else:
                        job.stage = "기획 실패"
                        lines.append(f"  ✗ 기획 실패: {data.get('error') or '실패'}")
                elif event == "task_start":
                    idx = data.get("index", 1)
                    tot = data.get("total", 1)
                    desc = (data.get("instruction") or "")[:200]
                    job.stage = f"태스크 [{idx}/{tot}] {data.get('agent')} ({data.get('task_id')})"
                    lines.append(f"  [2/3] 🛠️ [{idx}/{tot}] {data.get('agent')} 실행 중 ({data.get('task_id')})...")
                    lines.append(f"        지시: {desc}")
                    if data.get("command"):
                        lines.append(f"        💻 CLI 실행: {data.get('command')}")
                elif event == "task_end":
                    dur = data.get("duration_sec", 0.0)
                    if data.get("is_success"):
                        lines.append(f"  ✓ [{data.get('task_id')}] 실행 완료 ({dur:.1f}s)")
                    else:
                        lines.append(f"  ✗ [{data.get('task_id')}] 실행 실패 ({dur:.1f}s): {data.get('error')}")
                elif event == "synthesis_start":
                    job.stage = "최종 종합 보고서 작성 중 (synthesis)"
                    lines.append(f"  [3/3] 📝 Conductor({data.get('conductor')}) 최종 검토 및 종합 보고서 작성 중...")
                    if data.get("command"):
                        lines.append(f"        💻 CLI 실행: {data.get('command')}")
                elif event == "synthesis_end":
                    if data.get("is_success"):
                        job.stage = "완료 (done)"
                        lines.append("  ✓ 최종 종합 보고서 저장: blackboard/artifacts/synthesis_report.md")
                    else:
                        job.stage = "보고서 작성 실패"
                        lines.append(f"  ✗ 최종 종합 보고서 작성 실패: {data.get('error')}")

                for l in lines:
                    job.logs.append(l)

                if hasattr(self.blackboard, "save_job"):
                    try:
                        self.blackboard.save_job(job.to_dict())
                    except Exception:
                        pass

            runner = ConductorRunner(
                goal=command,
                conductor_agent_name=self.conductor_name,
                worker_agents=self.agents,
                blackboard=self.blackboard,
                workspace_dir=self.project_dir,
                event_bus=self.event_bus,
                progress_callback=_bg_progress,
                timeout=self.timeout,
            )
            job.runner = runner

            try:
                if job.status == "cancelled":
                    return
                res = runner.run()
                if job.status != "cancelled":
                    job.result = res
                    job.status = res.get("status", "completed")
                    if not res.get("success", False) and not job.error:
                        job.error = res.get("error_message") or res.get("error")
                    job.stage = "취소됨 (cancelled)" if job.status == "cancelled" else ("완료 (done)" if job.status == "completed" else "실패 (failed)")

                status_text = "SUCCESS" if res.get("success") else "FAILED"
                job.logs.append(f"\n<<< [{job.id}] 작업 완료 (상태: {status_text}, 소요 시간: {job.duration_sec:.1f}s)")
                if res.get("subtasks"):
                    job.logs.append(f"[실행된 서브태스크 ({len(res['subtasks'])})]")
                    for st in res["subtasks"]:
                        mark = "✓" if st.get("is_success") else "✗"
                        job.logs.append(f"  [{mark}] {st.get('task_id')} ({st.get('agent')})")
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.stage = "error"
                job.logs.append(f"\n❌ [{job.id}] 작업 오류: {e}")
            finally:
                job.ended_at = time.time()
                if hasattr(self.blackboard, "save_job"):
                    try:
                        self.blackboard.save_job(job.to_dict())
                    except Exception:
                        pass
                # Print async completion toast to terminal
                print(
                    f"\n🔔 [알림] 백그라운드 작업 '{job.id}' 종료 ({job.status}, {job.duration_sec:.1f}s)\n"
                    f"   결과 확인: /jobs 또는 /status\n"
                    f"[{self.project_name}] > ",
                    end="",
                    flush=True,
                )

        t = threading.Thread(target=_bg_worker, name=f"HarnessJob-{job_id}", daemon=True)
        job.thread = t
        t.start()
        return job

    def cancel_job(self, job_id: Optional[str] = None) -> bool:
        """Cancel a running background job or active foreground runner."""
        if job_id:
            job = self.jobs.get(job_id)
            if job and job.status == "running":
                if job.runner:
                    job.runner.cancel()
                job.status = "cancelled"
                job.stage = "취소됨 (cancelled)"
                job.ended_at = time.time()
                if hasattr(self.blackboard, "save_job"):
                    try:
                        self.blackboard.save_job(job.to_dict())
                    except Exception:
                        pass
                return True
            return False

        # Cancel any active running job
        cancelled_any = False
        if self._active_foreground_runner:
            self._active_foreground_runner.cancel()
            cancelled_any = True

        for j in self.jobs.values():
            if j.status == "running":
                if j.runner:
                    j.runner.cancel()
                j.status = "cancelled"
                j.stage = "취소됨 (cancelled)"
                j.ended_at = time.time()
                if hasattr(self.blackboard, "save_job"):
                    try:
                        self.blackboard.save_job(j.to_dict())
                    except Exception:
                        pass
                cancelled_any = True

        return cancelled_any

    def list_jobs(self) -> List[BackgroundJob]:
        """Return list of all submitted background jobs."""
        return list(self.jobs.values())

    def start_repl(self) -> None:
        """Start an interactive CLI REPL session with live status feedback and background jobs."""
        if not self.project_name:
            existing = self.list_projects()
            non_default = [p for p in existing if p != "default"]
            if non_default:
                self.switch_project(non_default[0])
            elif existing:
                self.switch_project(existing[0])
            else:
                print("현재 생성된 프로젝트가 없습니다.")
                try:
                    p_name = input("작업을 진행할 새 프로젝트 이름을 입력하세요: ").strip()
                except (EOFError, KeyboardInterrupt):
                    p_name = ""
                if p_name:
                    self.switch_project(p_name)
                else:
                    self.switch_project("project_1")

        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.blackboard.initialize()

        agent_desc = []
        for aname, a in self.agents.items():
            extra = []
            if getattr(a, "model", None):
                extra.append(f"model={a.model}")
            if getattr(a, "effort", None):
                extra.append(f"effort={a.effort}")
            if extra:
                agent_desc.append(f"{aname} ({', '.join(extra)})")
            else:
                agent_desc.append(aname)
        agent_names = ", ".join(agent_desc)
        print("=" * 64)
        print("🤖 ModueHarness (모두의 하네스) - 대화형 CLI 모드")
        print("=" * 64)
        print(f"• 대상 프로젝트 (구현 위치): {self.project_dir}")
        print(f"• 공용 칠판 (AI 정보 교환):  {self.blackboard_dir}")
        print(f"• 참여 AI 팀:               {agent_names} (Leader: {self.conductor_name})")
        print("-" * 64)
        print("명령어를 입력하면 AI 팀이 프로젝트 디렉터리에 직접 구현합니다.")
        print("💡 팁: 명령 끝에 '&'를 붙이면 백그라운드로 실행되어 논블로킹으로 다른 작업을 계속할 수 있습니다!")
        print("특수 명령어: /model, /effort, /jobs, /cancel, /project <이름>, /projects, /files, /status, /help, exit")
        print("=" * 64 + "\n")

        while True:
            try:
                prompt_text = f"[{self.project_name}] > "
                user_input = input(prompt_text).strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "q"]:
                    print("👋 대화형 세션을 종료합니다.")
                    break

                if user_input.startswith("/"):
                    self._handle_special_command(user_input)
                    continue

                # Check if user requested background execution via '&' or '/bg '
                is_bg = user_input.endswith("&")
                if is_bg:
                    cmd_to_run = user_input[:-1].strip()
                    job = self.execute_command_async(cmd_to_run)
                    print(f"\n🚀 백그라운드 작업 '{job.id}' 실행이 시작되었습니다!")
                    print(f"• 작업: '{cmd_to_run}'")
                    print(f"• 프로젝트: {self.project_dir}")
                    print(f"• 진행 상태 확인: /jobs 또는 /status")
                    print(f"• 작업 취소:     /cancel {job.id}\n")
                    continue

                # Normal task execution (with live progress callbacks)
                print(f"\n🚀 작업 수신: '{user_input}'")
                print(f"📁 구현 디렉터리: {self.project_dir}")
                print(f"📋 공용 칠판:     {self.blackboard_dir}\n")

                summary = self.execute_command(user_input, live_progress=True)

                print("\n" + "-" * 64)
                if summary["success"]:
                    print(f"✓ 작업 완료! (소요 시간: {summary['total_duration_sec']:.2f}s)")
                else:
                    status_desc = summary.get("status", "failed")
                    print(f"✗ 작업 종료 ({status_desc}, 소요 시간: {summary['total_duration_sec']:.2f}s)")
                    if summary.get("error"):
                        print(f"❌ [실패 상세 원인]: {summary.get('error')}")

                if summary.get("subtasks"):
                    print(f"\n[실행된 서브태스크: {len(summary['subtasks'])}개]")
                    for st in summary["subtasks"]:
                        mark = "✓" if st.get("is_success") else "✗"
                        cmd_line = f"\n      💻 CLI: {st.get('command')}" if st.get("command") else ""
                        print(f"  [{mark}] {st.get('task_id')} ({st.get('agent')}){cmd_line}")
                        if not st.get("is_success") and st.get("error"):
                            print(f"      ❌ 오류 상세: {st.get('error')}")

                if summary.get("project_files"):
                    print(f"\n[프로젝트 파일 ({self.project_dir.name})]")
                    for pf in summary["project_files"]:
                        print(f"  📄 {pf}")

                if summary.get("artifacts"):
                    print(f"\n[블랙보드 교환 산출물]")
                    for af in summary["artifacts"]:
                        print(f"  📌 {af}")

                print("-" * 64 + "\n")

            except KeyboardInterrupt:
                if self._active_foreground_runner:
                    print("\n⚠️ 실행 중인 작업을 취소하는 중...")
                    self.cancel_job()
                else:
                    print("\n👋 세션을 종료합니다.")
                    break
            except EOFError:
                print("\n👋 세션을 종료합니다.")
                break
            except Exception as e:
                print(f"\n⚠️ 오류 발생: {e}\n")

    def _handle_special_command(self, cmd_str: str) -> None:
        """Handle REPL slash commands."""
        parts = cmd_str.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ["/bg", "/async"]:
            if not arg:
                print("사용법: /bg <명령어> (백그라운드 비동기 작업 실행)")
            else:
                job = self.execute_command_async(arg)
                print(f"\n🚀 백그라운드 작업 '{job.id}' 실행이 시작되었습니다!")
                print(f"• 작업: '{arg}'")
                print(f"• 상태 확인: /jobs 또는 /status")
                print(f"• 작업 취소: /cancel {job.id}\n")

        elif cmd == "/jobs":
            jobs = self.list_jobs()
            print(f"\n📋 백그라운드 작업 목록 ({len(jobs)}개):")
            if not jobs:
                print("  (등록된 백그라운드 작업이 없습니다)")
            for j in jobs:
                marker = {"running": "▶", "completed": "✓", "failed": "✗", "cancelled": "⊘"}.get(j.status, "?")
                print(f"  [{marker}] {j.id} ({j.status}, {j.duration_sec:.1f}s) - {j.project}: '{j.command[:35]}'")
                if j.status == "running":
                    print(f"      현재 단계: {j.stage}")
                elif j.status == "failed" and j.error:
                    print(f"      ❌ 실패 사유: {j.error}")
            print()

        elif cmd in ["/cancel", "/stop"]:
            target_id = arg if arg else None
            ok = self.cancel_job(target_id)
            if ok:
                target_msg = f"'{target_id}'" if target_id else "활성 작업"
                print(f"✓ {target_msg} 취소 신호를 전달했습니다.")
            else:
                print(f"⚠️ 취소할 수 있는 실행 중인 작업을 찾을 수 없습니다: {arg or 'N/A'}")

        elif cmd in ["/project", "/p"]:
            if not arg:
                print(f"현재 프로젝트: {self.project_name} ({self.project_dir})")
            else:
                old_name = self.project_name
                self.switch_project(arg)
                print(f"✓ 대상 프로젝트를 '{old_name}'에서 '{self.project_name}'(으)로 변경했습니다.")
                print(f"  새 경로: {self.project_dir}")

        elif cmd == "/projects":
            projects = self.list_projects()
            print(f"\n📁 생성된 프로젝트 목록 ({len(projects)}개):")
            if not projects:
                print("  (아직 생성된 프로젝트가 없습니다)")
            for p in projects:
                current_mark = " (현재 선택됨)" if p == self.project_name else ""
                print(f"  • {p}{current_mark}")
            print()

        elif cmd in ["/files", "/ls"]:
            files = self.list_project_files()
            print(f"\n📄 '{self.project_name}' 프로젝트 파일 ({len(files)}개):")
            if not files:
                print("  (프로젝트 내 파일이 아직 없습니다)")
            for f in files:
                print(f"  • {f}")
            print()

        elif cmd in ["/model", "/m"]:
            if not arg:
                print("\n📋 현재 AI 에이전트 모델 설정:")
                for name, agent in self.agents.items():
                    m = getattr(agent, "model", None) or "(기본값)"
                    print(f"  • {name}: {m}")
                print("\n사용법: /model <모델명> (예: /model sonnet, /model claude-3-7-sonnet-latest)")
                print("       /model <에이전트명> <모델명> (예: /model developer haiku)\n")
            else:
                arg_parts = arg.split(maxsplit=1)
                if len(arg_parts) == 2 and arg_parts[0] in self.agents:
                    target_agent, new_model = arg_parts[0], arg_parts[1]
                    updated = self.set_model(new_model, target_agent)
                    print(f"✓ '{target_agent}' 에이전트의 모델을 '{new_model}'(으)로 변경했습니다.")
                else:
                    new_model = arg
                    updated = self.set_model(new_model)
                    if updated:
                        print(f"✓ AI 에이전트({', '.join(updated)})의 모델을 '{new_model}'(으)로 변경했습니다.")
                    else:
                        print("⚠️ 모델을 적용할 수 있는 에이전트를 찾을 수 없습니다.")

        elif cmd in ["/effort", "/e"]:
            valid_levels = {"low", "medium", "high", "xhigh", "max", "off", "none", "default"}
            if not arg:
                print("\n📋 현재 AI 에이전트(Claude / Antigravity) 추론 노력(Effort) 설정:")
                for name, agent in self.agents.items():
                    eff = getattr(agent, "effort", None) or "(기본값)"
                    print(f"  • {name}: {eff}")
                print("\n선택 가능 레벨: low, medium, high (Claude의 경우 xhigh, max 추가 지원, off/none으로 해제)")
                print("사용법: /effort <레벨> (예: /effort high, /effort max)")
                print("       /effort <에이전트명> <레벨> (예: /effort architect high)\n")
            else:
                arg_parts = arg.split(maxsplit=1)
                if len(arg_parts) == 2 and arg_parts[0] in self.agents:
                    target_agent, level = arg_parts[0], arg_parts[1].lower()
                    eff_val = None if level in ["off", "none", "default"] else level
                    updated = self.set_effort(eff_val, target_agent)
                    print(f"✓ '{target_agent}' 에이전트의 추론 노력(effort)을 '{eff_val or 'default'}'(으)로 변경했습니다.")
                else:
                    level = arg.lower()
                    eff_val = None if level in ["off", "none", "default"] else level
                    updated = self.set_effort(eff_val)
                    if updated:
                        print(f"✓ AI 에이전트({', '.join(updated)})의 추론 노력(effort)을 '{eff_val or 'default'}'(으)로 변경했습니다.")
                    else:
                        print("⚠️ 추론 노력을 적용할 수 있는 AI 에이전트를 찾을 수 없습니다.")

        elif cmd in ["/timeout", "/t"]:
            if not arg:
                if self.timeout is None:
                    print("\n⏱️ 현재 AI 실행 타임아웃: 해제됨 (무제한 대기)")
                else:
                    print(f"\n⏱️ 현재 AI 실행 타임아웃: {self.timeout}초")
                print("사용법: /timeout <초> (예: /timeout 600)")
                print("       /timeout off (또는 none, 0: 타임아웃 해제/무제한 대기)\n")
            elif arg.lower() in ["off", "none", "0", "disable", "unlimited"]:
                self.set_timeout(None)
                print("✓ 세션 타임아웃이 해제되었습니다 (무제한 대기).")
            else:
                try:
                    t_val = float(arg)
                    if t_val <= 0:
                        self.set_timeout(None)
                        print("✓ 세션 타임아웃이 해제되었습니다 (무제한 대기).")
                    else:
                        self.set_timeout(t_val)
                        print(f"✓ 세션 타임아웃이 {t_val}초로 설정되었습니다.")
                except ValueError:
                    print("❌ 올바른 숫자를 입력하세요. 예: /timeout 600 또는 /timeout off")

        elif cmd == "/status":
            state = self.blackboard.load_state()
            tasks = self.blackboard.list_tasks()
            artifacts = self.blackboard.list_artifacts()
            running_jobs = [j for j in self.jobs.values() if j.status == "running"]
            timeout_str = f"{self.timeout}초" if self.timeout is not None else "해제됨 (무제한)"

            print(f"\n=== ModueHarness 상태 요약 ===")
            print(f"• 활성 프로젝트: {self.project_name} ({self.project_dir})")
            print(f"• 공용 칠판:     {self.blackboard_dir}")
            print(f"• 세션 타임아웃: {timeout_str}")
            print(f"• 참여 AI 팀:")
            for aname, a in self.agents.items():
                m_str = f", model={a.model}" if getattr(a, "model", None) else ""
                e_str = f", effort={a.effort}" if getattr(a, "effort", None) else ""
                print(f"    - {aname} ({getattr(a, 'name', a.__class__.__name__)}{m_str}{e_str})")
            print(f"• 세션 ID:       {state.get('session_id', 'N/A')}")
            print(f"• 진행 상태:     {state.get('status', 'unknown')}")
            if running_jobs:
                print(f"• 백그라운드 실행 중: {len(running_jobs)}개 작업")
                for rj in running_jobs:
                    print(f"    - [{rj.id}] {rj.stage} ({rj.duration_sec:.1f}s 경과)")
            print(f"• 등록된 태스크: {len(tasks)}개")
            print(f"• 칠판 아티팩트: {len(artifacts)}개\n")

        elif cmd in ["/cmd", "/command", "/last-cmd"]:
            if not self.last_commands:
                print("\n📋 직전에 실행된 CLI 명령어가 없습니다.\n")
            else:
                print(f"\n📋 최근 실행된 실제 AI CLI 명령어 목록 ({len(self.last_commands)}개):")
                for i, item in enumerate(self.last_commands, 1):
                    print(f"\n  [{i}] {item.get('phase')} - 에이전트: {item.get('agent')}")
                    print(f"      {item.get('command')}")
                print()

        elif cmd in ["/help", "/?"]:
            print("\n=== 사용 가능한 명령어 ===")
            print("  자연어 명령 입력        : 동기 방식으로 즉시 실행 (실시간 단계 및 CLI 명령 표시)")
            print("  자연어 명령 &          : 백그라운드 비동기 실행 (프롬프트 즉시 반환)")
            print("  /model [이름] [모델]    : AI 모델 확인 및 변경 (예: /model sonnet)")
            print("  /effort [이름] [수준]   : Claude 추론 노력 수준 설정 (low, medium, high, max)")
            print("  /timeout [초|off]      : AI 실행 타임아웃 설정 또는 해제 (기본: 해제/무제한)")
            print("  /cmd (또는 /last-cmd)   : 직전 실행된 실제 AI CLI 명령어 전체 보기")
            print("  /bg <명령어>           : 백그라운드 비동기 실행")
            print("  /jobs                 : 백그라운드 작업 진행 현황 및 목록")
            print("  /cancel [job_id]      : 실행 중인 작업 취소 및 중단")
            print("  /project <이름>        : 대상 프로젝트 전환 (폴더 자동 생성)")
            print("  /projects             : 전체 프로젝트 목록 조회")
            print("  /files (또는 /ls)     : 현재 프로젝트 내 구현 파일 목록")
            print("  /status               : 칠판 상태 및 백그라운드 작업 현황")
            print("  /help                 : 도움말 출력")
            print("  exit, quit, q         : 종료\n")

        else:
            print(f"알 수 없는 특수 명령: '{cmd}'. /help 를 입력하여 사용법을 확인하세요.")
