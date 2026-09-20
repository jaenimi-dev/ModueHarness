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

    @property
    def duration_sec(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)


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
        project_name: str = "default",
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
        self.project_name = project_name
        self.project_dir = self.projects_root / self.project_name

        self.blackboard_dir = (blackboard_dir or (Path.cwd() / "blackboard")).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = Blackboard(root_dir=self.blackboard_dir, event_bus=self.event_bus)

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
            "version": "0.7.0",
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
        """Switch current target project to a new or existing project folder."""
        clean_name = project_name.strip()
        if not clean_name:
            raise ValueError("Project name cannot be empty.")

        self.project_name = clean_name
        self.project_dir = self.projects_root / self.project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

        if self.blackboard.is_initialized():
            self.blackboard.update_state({
                "current_project": self.project_name,
                "project_dir": str(self.project_dir),
            })
        return self.project_dir

    def list_projects(self) -> List[str]:
        """List all existing project names under projects_root."""
        if not self.projects_root.exists():
            return []
        return sorted([
            p.name for p in self.projects_root.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ])

    def list_project_files(self) -> List[str]:
        """List all implementation files inside the active project folder."""
        if not self.project_dir.exists():
            return []
        files = []
        for p in self.project_dir.rglob("*"):
            if p.is_file() and not any(part.startswith(".") for part in p.parts):
                try:
                    files.append(str(p.relative_to(self.project_dir)))
                except Exception:
                    pass
        return sorted(files)

    def execute_command(
        self,
        command: str,
        live_progress: bool = True,
    ) -> Dict[str, Any]:
        """Execute a user natural-language command synchronously.

        Live progress updates are printed to stdout if live_progress is True.
        """
        command = command.strip()
        if not command:
            return {"success": False, "error": "Empty command"}

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

        def _console_progress(event: str, data: Dict[str, Any]) -> None:
            if not live_progress:
                return
            if event == "planning_start":
                print(f"  [1/3] 🧠 Conductor({data.get('conductor')}) 작업 목표 분석 및 계획 수립 중...")
                if data.get("command"):
                    print(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": "기획 (Planning)",
                        "agent": data.get("conductor"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "planning_end":
                if data.get("is_success"):
                    tasks = data.get("tasks", [])
                    print(f"  ✓ 기획 완료: {len(tasks)}개 서브태스크 생성 (blackboard/tasks)")
                    for t in tasks:
                        desc = (t.get("instruction") or "")[:50]
                        print(f"    • [{t.get('id')}] {t.get('assigned_agent')}: {desc}")
                else:
                    err_msg = data.get("error") or "계획 수립 실패"
                    print(f"  ✗ 기획 실패: {err_msg}")
            elif event == "task_start":
                idx = data.get("index", 1)
                tot = data.get("total", 1)
                desc = (data.get("instruction") or "")[:60]
                print(f"  [2/3] 🛠️ [{idx}/{tot}] {data.get('agent')} 실행 중 ({data.get('task_id')})...")
                print(f"        지시: {desc}")
                if data.get("command"):
                    print(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": f"태스크 [{idx}/{tot}] {data.get('task_id')}",
                        "agent": data.get("agent"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "task_end":
                dur = data.get("duration_sec", 0.0)
                if data.get("is_success"):
                    print(f"  ✓ [{data.get('task_id')}] 실행 완료 ({dur:.1f}s)")
                else:
                    err_str = data.get("error") or "서브태스크 실행 실패"
                    print(f"  ✗ [{data.get('task_id')}] 실행 실패 ({dur:.1f}s)")
                    print(f"        ❌ 서브태스크 실패 원인: {err_str}")
            elif event == "synthesis_start":
                print(f"  [3/3] 📝 Conductor({data.get('conductor')}) 최종 검토 및 종합 보고서 작성 중...")
                if data.get("command"):
                    print(f"        💻 CLI 실행: {data.get('command')}")
                if data.get("full_command_str") or data.get("command"):
                    self.last_commands.append({
                        "phase": "종합 검토 (Synthesis)",
                        "agent": data.get("conductor"),
                        "command": data.get("full_command_str") or data.get("command"),
                    })
            elif event == "synthesis_end":
                if data.get("is_success"):
                    print(f"  ✓ 최종 종합 보고서 저장: blackboard/artifacts/synthesis_report.md")
                else:
                    err_str = data.get("error") or "종합 보고서 작성 실패"
                    print(f"  ✗ 최종 종합 보고서 작성 실패: {err_str}")

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

        try:
            result = runner.run()
        finally:
            self._active_foreground_runner = None

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
        self._job_counter += 1
        job_id = f"job_{self._job_counter}"

        job = BackgroundJob(
            id=job_id,
            command=command,
            project=self.project_name,
            project_dir=self.project_dir,
            status="running",
            stage="planning",
        )
        self.jobs[job_id] = job

        # Ensure project and blackboard directories exist
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.blackboard.initialize()

        def _bg_worker():
            def _bg_progress(event: str, data: Dict[str, Any]):
                if event == "planning_start":
                    job.stage = "기획 중 (planning)"
                elif event == "task_start":
                    idx = data.get("index", 1)
                    tot = data.get("total", 1)
                    job.stage = f"태스크 [{idx}/{tot}] {data.get('agent')} ({data.get('task_id')})"
                elif event == "synthesis_start":
                    job.stage = "최종 종합 보고서 작성 중 (synthesis)"

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
                res = runner.run()
                job.result = res
                job.status = res.get("status", "completed")
                if not res.get("success", False) and not job.error:
                    job.error = res.get("error_message") or res.get("error")
                job.stage = "done"
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.stage = "error"
            finally:
                job.ended_at = time.time()
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
            if job and job.status == "running" and job.runner:
                job.runner.cancel()
                job.status = "cancelled"
                job.stage = "cancelled"
                job.ended_at = time.time()
                return True
            return False

        # Cancel any active running job
        cancelled_any = False
        if self._active_foreground_runner:
            self._active_foreground_runner.cancel()
            cancelled_any = True

        for j in self.jobs.values():
            if j.status == "running" and j.runner:
                j.runner.cancel()
                j.status = "cancelled"
                j.stage = "cancelled"
                j.ended_at = time.time()
                cancelled_any = True

        return cancelled_any

    def list_jobs(self) -> List[BackgroundJob]:
        """Return list of all submitted background jobs."""
        return list(self.jobs.values())

    def start_repl(self) -> None:
        """Start an interactive CLI REPL session with live status feedback and background jobs."""
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
