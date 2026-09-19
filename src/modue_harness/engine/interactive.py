"""Interactive CLI execution session and project-aware runner without workflow files."""

import datetime
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional

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


def load_or_detect_agents(
    agents_file: Optional[Path] = None,
    specific_agent: Optional[str] = None,
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
        elif specific_agent.lower() == "agy":
            kwargs = {"command": "agy"}
        elif specific_agent.lower() == "aider":
            kwargs = {"command": "aider"}
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
                    kwargs: Dict[str, Any] = {"name": name, "default_args": cfg.get("args", [])}
                    if cfg.get("command"):
                        kwargs["command"] = cfg["command"]
                    if cfg.get("model"):
                        kwargs["model"] = cfg["model"]
                    if cfg.get("system_instruction"):
                        kwargs["system_instruction"] = cfg["system_instruction"]
                    loaded[name] = create_adapter(adapter_type, **kwargs)
            if loaded:
                return loaded
        except Exception:
            pass

    # 3. Auto-detect installed AI CLI tools on system PATH
    claude_bin = shutil.which("claude")
    agy_bin = shutil.which("agy")
    aider_bin = shutil.which("aider")

    if claude_bin:
        return {
            "architect": ClaudeCLIAdapter(
                name="architect",
                command="claude",
                default_args=["--permission-mode", "auto"],
                system_instruction="You design modular software architecture and decompose tasks clearly.",
            ),
            "developer": ClaudeCLIAdapter(
                name="developer",
                command="claude",
                default_args=["--permission-mode", "auto"],
                system_instruction="You write clean, tested, production-ready code in the project directory.",
            ),
            "reviewer": ClaudeCLIAdapter(
                name="reviewer",
                command="claude",
                default_args=["--permission-mode", "auto"],
                system_instruction="You verify and review implementation code and write test validations.",
            ),
        }

    if agy_bin:
        return {
            "architect": AGYCLIAdapter(
                name="architect",
                command="agy",
                system_instruction="You design modular software architecture and decompose tasks clearly.",
            ),
            "developer": AGYCLIAdapter(
                name="developer",
                command="agy",
                system_instruction="You write clean, tested, production-ready code in the project directory.",
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
    """Manages an interactive session where commands are executed directly into a project folder

    while using the blackboard strictly for AI coordination and communication.
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
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.projects_root = (projects_root or (Path.cwd() / "projects")).resolve()
        self.project_name = project_name
        self.project_dir = self.projects_root / self.project_name

        self.blackboard_dir = (blackboard_dir or (Path.cwd() / "blackboard")).resolve()
        self.event_bus = event_bus or EventBus()
        self.blackboard = Blackboard(root_dir=self.blackboard_dir, event_bus=self.event_bus)

        self.agents = agents or load_or_detect_agents(
            agents_file=agents_file,
            specific_agent=specific_agent,
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

    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute a user natural-language command using AI agents.

        Implementation files are generated in `project_dir`.
        Information, tasks, and state are exchanged via `blackboard`.
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

        # Run Leader-Worker Conductor
        runner = ConductorRunner(
            goal=command,
            conductor_agent_name=self.conductor_name,
            worker_agents=self.agents,
            blackboard=self.blackboard,
            workspace_dir=self.project_dir,
            event_bus=self.event_bus,
        )

        result = runner.run()

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
        }

    def start_repl(self) -> None:
        """Start an interactive CLI REPL session for entering instructions."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.blackboard.initialize()

        agent_names = ", ".join(self.agents.keys())
        print("=" * 64)
        print("🤖 ModueHarness (모두의 하네스) - 대화형 CLI 모드")
        print("=" * 64)
        print(f"• 대상 프로젝트 (구현 위치): {self.project_dir}")
        print(f"• 공용 칠판 (AI 정보 교환):  {self.blackboard_dir}")
        print(f"• 참여 AI 팀:               {agent_names} (Leader: {self.conductor_name})")
        print("-" * 64)
        print("명령어를 입력하면 AI 팀이 프로젝트 디렉터리에 직접 구현합니다.")
        print("특수 명령어: /project <이름>, /projects, /files, /status, /help, exit")
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

                # Normal task execution
                print(f"\n🚀 작업 수신: '{user_input}'")
                print(f"📁 구현 디렉터리: {self.project_dir}")
                print(f"📋 공용 칠판:     {self.blackboard_dir}\n")

                summary = self.execute_command(user_input)

                print("\n" + "-" * 64)
                if summary["success"]:
                    print(f"✓ 작업 완료! (소요 시간: {summary['total_duration_sec']:.2f}s)")
                else:
                    print(f"✗ 작업 실패 또는 중단 (소요 시간: {summary['total_duration_sec']:.2f}s)")

                if summary.get("subtasks"):
                    print(f"\n[실행된 서브태스크: {len(summary['subtasks'])}개]")
                    for st in summary["subtasks"]:
                        mark = "✓" if st.get("is_success") else "✗"
                        print(f"  [{mark}] {st.get('task_id')} ({st.get('agent')})")

                if summary.get("project_files"):
                    print(f"\n[프로젝트 파일 ({self.project_dir.name})]")
                    for pf in summary["project_files"]:
                        print(f"  📄 {pf}")

                if summary.get("artifacts"):
                    print(f"\n[블랙보드 교환 산출물]")
                    for af in summary["artifacts"]:
                        print(f"  📌 {af}")

                print("-" * 64 + "\n")

            except (KeyboardInterrupt, EOFError):
                print("\n👋 세션을 종료합니다.")
                break
            except Exception as e:
                print(f"\n⚠️ 오류 발생: {e}\n")

    def _handle_special_command(self, cmd_str: str) -> None:
        """Handle REPL slash commands."""
        parts = cmd_str.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ["/project", "/p"]:
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

        elif cmd == "/status":
            state = self.blackboard.load_state()
            tasks = self.blackboard.list_tasks()
            artifacts = self.blackboard.list_artifacts()
            print(f"\n=== ModueHarness 상태 요약 ===")
            print(f"• 활성 프로젝트: {self.project_name} ({self.project_dir})")
            print(f"• 공용 칠판:     {self.blackboard_dir}")
            print(f"• 세션 ID:       {state.get('session_id', 'N/A')}")
            print(f"• 진행 상태:     {state.get('status', 'unknown')}")
            print(f"• 등록된 태스크: {len(tasks)}개")
            print(f"• 칠판 아티팩트: {len(artifacts)}개\n")

        elif cmd in ["/help", "/?"]:
            print("\n=== 사용 가능한 명령어 ===")
            print("  자연어 명령 입력      : AI 팀에게 코드 생성/수정/테스트 작업 요청")
            print("  /project <이름>        : 대상 프로젝트 전환 (폴더 자동 생성)")
            print("  /projects             : 전체 프로젝트 목록 조회")
            print("  /files (또는 /ls)     : 현재 프로젝트 내 구현 파일 목록")
            print("  /status               : 칠판 상태 및 태스크 현황 조회")
            print("  /help                 : 도움말 출력")
            print("  exit, quit, q         : 종료\n")

        else:
            print(f"알 수 없는 특수 명령: '{cmd}'. /help 를 입력하여 사용법을 확인하세요.")
