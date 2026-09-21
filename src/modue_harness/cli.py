"""Command Line Interface for ModueHarness with direct CLI command execution,

interactive REPL, project workspace separation, Pipeline, Debate, and Report support.
"""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from modue_harness import __version__
from modue_harness.adapters import create_adapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.config import load_dotenv
from modue_harness.core.encoding import ensure_utf8_io
from modue_harness.engine.debate import DebateRunner
from modue_harness.engine.interactive import InteractiveSession
from modue_harness.engine.pipeline import PipelineRunner
from modue_harness.engine.workflow import WorkflowConfig
from modue_harness.plugins.reporter import MarkdownReportPlugin

KNOWN_SUBCOMMANDS = {"init", "status", "projects", "run", "debate", "ui", "tui"}


def create_parser() -> argparse.ArgumentParser:
    """Build and configure the CLI argument parser with subcommands and root command options."""
    parser = argparse.ArgumentParser(
        prog="modue-harness",
        description="ModueHarness - Multi-AI CLI Collaboration Harness (Interactive & Direct Command Execution)",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show program's version number and exit",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )

    # Root command flags for direct/interactive execution
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        default=None,
        help="Task instruction or command to execute directly in the target project",
    )
    parser.add_argument(
        "-P", "--project",
        type=str,
        default=None,
        help="Target project name (saved in projects/<project_name>, default: None / auto-detect)",
    )
    parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects base directory (default: projects)",
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to shared blackboard directory for AI coordination (default: blackboard)",
    )
    parser.add_argument(
        "--agents", "-a",
        type=str,
        default=None,
        help="Path to AI team specification file (default: config/agents.yaml or auto-detect)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Override with a specific single AI agent adapter (e.g. claude, agy, aider, generic)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model to use for Claude/AI agents (e.g. sonnet, opus, haiku, claude-3-7-sonnet-latest)",
    )
    parser.add_argument(
        "--effort", "-e",
        type=str,
        default=None,
        help="Reasoning/thinking effort level for Claude (choices: low, medium, high, xhigh, max)",
    )
    parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=None,
        help="Execution timeout in seconds per AI CLI turn (default: None / unlimited)",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Start interactive CLI REPL session",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch NiceGUI Web dashboard in browser",
    )
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Launch Textual Terminal UI dashboard",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for Web UI (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for Web UI (default: 8080)",
    )
    parser.add_argument(
        "--lang", "-L",
        type=str,
        choices=["ko", "en"],
        default="ko",
        help="Display language ('ko' or 'en', default: 'ko')",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize blackboard and projects directory")
    init_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    init_parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects directory (default: projects)",
    )

    # Command: status
    status_parser = subparsers.add_parser("status", help="Display current blackboard status, projects, and tasks")
    status_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    status_parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects directory (default: projects)",
    )
    status_parser.add_argument(
        "-P", "--project",
        type=str,
        default=None,
        help="Specific project to inspect in blackboard",
    )

    # Command: projects
    projects_parser = subparsers.add_parser("projects", help="List existing projects in projects directory")
    projects_parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects directory (default: projects)",
    )
    projects_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    projects_parser.add_argument(
        "--delete",
        type=str,
        metavar="PROJECT_NAME",
        help="Delete a specific project directory and its blackboard data",
    )

    # Command: run (legacy workflow support)
    run_parser = subparsers.add_parser("run", help="Run a multi-AI collaboration workflow specification file")
    run_parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to workflow YAML or JSON configuration file",
    )
    run_parser.add_argument(
        "--agents", "-a",
        type=str,
        default=None,
        help="Optional path to AI team specification file (overrides agents_file in workflow)",
    )
    run_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    run_parser.add_argument(
        "--report", "-r",
        type=str,
        default=None,
        help="Path to generate markdown execution report (e.g. report.md)",
    )

    # Command: debate
    debate_parser = subparsers.add_parser("debate", help="Launch a multi-AI debate and consensus workflow")
    debate_parser.add_argument(
        "--topic", "-t",
        type=str,
        required=True,
        help="Debate topic or problem statement",
    )
    debate_parser.add_argument(
        "--proposer",
        type=str,
        default="claude",
        help="Adapter for Proposer (default: claude)",
    )
    debate_parser.add_argument(
        "--challenger",
        type=str,
        default="agy",
        help="Adapter for Challenger (default: agy)",
    )
    debate_parser.add_argument(
        "--judge",
        type=str,
        default="claude",
        help="Adapter for Judge/Arbiter (default: claude)",
    )
    debate_parser.add_argument(
        "--rounds",
        type=int,
        default=2,
        help="Number of debate rounds (default: 2)",
    )
    debate_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )

    # Command: ui
    ui_parser = subparsers.add_parser("ui", help="Launch NiceGUI Web dashboard in browser")
    ui_parser.add_argument(
        "-P", "--project",
        type=str,
        default=None,
        help="Initial target project name (default: None / auto-detect)",
    )
    ui_parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects directory (default: projects)",
    )
    ui_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    ui_parser.add_argument(
        "--agents", "-a",
        type=str,
        default=None,
        help="Path to AI team specification file (default: config/agents.yaml or auto-detect)",
    )
    ui_parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Override with a specific single AI agent adapter",
    )
    ui_parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model to use for Claude/AI agents",
    )
    ui_parser.add_argument(
        "--effort", "-e",
        type=str,
        default=None,
        help="Reasoning/thinking effort level for Claude (choices: low, medium, high, xhigh, max)",
    )
    ui_parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=None,
        help="Execution timeout in seconds per AI CLI turn",
    )
    ui_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for Web UI (default: 127.0.0.1)",
    )
    ui_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for Web UI (default: 8080)",
    )
    ui_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open web browser on startup",
    )
    ui_parser.add_argument(
        "--lang", "-L",
        type=str,
        choices=["ko", "en"],
        default="ko",
        help="Web UI display language ('ko' or 'en', default: 'ko')",
    )

    # Command: tui
    tui_parser = subparsers.add_parser("tui", help="Launch Textual Terminal UI dashboard")
    tui_parser.add_argument(
        "-P", "--project",
        type=str,
        default=None,
        help="Initial target project name (default: None / auto-detect)",
    )
    tui_parser.add_argument(
        "--projects-dir",
        type=str,
        default="projects",
        help="Path to projects directory (default: projects)",
    )
    tui_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )
    tui_parser.add_argument(
        "--agents", "-a",
        type=str,
        default=None,
        help="Path to AI team specification file",
    )
    tui_parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Override with a specific single AI agent adapter",
    )
    tui_parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model to use for Claude/AI agents",
    )
    tui_parser.add_argument(
        "--effort", "-e",
        type=str,
        default=None,
        help="Reasoning/thinking effort level",
    )
    tui_parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=None,
        help="Execution timeout in seconds per AI CLI turn",
    )
    tui_parser.add_argument(
        "--lang", "-L",
        type=str,
        choices=["ko", "en"],
        default="ko",
        help="TUI display language ('ko' or 'en', default: 'ko')",
    )

    return parser


def parse_cli_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments supporting positional task prompts and root execution."""
    parser = create_parser()
    raw_args = list(sys.argv[1:] if argv is None else argv)

    # Fast path for version
    if "-v" in raw_args or "--version" in raw_args:
        return parser.parse_args(raw_args)

    # Check if a known subcommand is present at the front
    is_subcmd = False
    for a in raw_args:
        if a in KNOWN_SUBCOMMANDS:
            is_subcmd = True
            break
        if not a.startswith("-"):
            break

    if not is_subcmd:
        cleaned_args = []
        positional_prompt: Optional[str] = None
        i = 0
        valued_flags = {
            "-P", "--project",
            "--projects-dir",
            "--dir", "-d",
            "--agents", "-a",
            "--agent",
            "-m", "--model",
            "-e", "--effort",
            "-t", "--timeout",
            "-p", "--prompt",
            "--host",
            "--port",
            "-L", "--lang",
        }

        while i < len(raw_args):
            arg = raw_args[i]
            if arg in valued_flags:
                cleaned_args.append(arg)
                if i + 1 < len(raw_args):
                    cleaned_args.append(raw_args[i + 1])
                    i += 2
                    continue
            elif arg.startswith("-"):
                cleaned_args.append(arg)
            else:
                if positional_prompt is None:
                    positional_prompt = arg
                else:
                    positional_prompt += " " + arg
            i += 1

        parsed = parser.parse_args(cleaned_args)
        if positional_prompt and not parsed.prompt:
            parsed.prompt = positional_prompt
        return parsed

    return parser.parse_args(raw_args)


def handle_init(args: argparse.Namespace) -> int:
    """Handle 'init' command: Initialize blackboard and projects directory."""
    board_dir = Path(getattr(args, "dir", "blackboard")).resolve()
    board = Blackboard(root_dir=board_dir)
    board.initialize()

    projects_dir = Path(getattr(args, "projects_dir", "projects")).resolve()
    projects_dir.mkdir(parents=True, exist_ok=True)

    print(f"✓ Initialized ModueHarness blackboard at: {board.root_dir}")
    print(f"✓ Initialized projects directory at:       {projects_dir}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    """Handle 'status' command: Display blackboard status, projects, tasks, and artifacts."""
    board_dir = Path(getattr(args, "dir", "blackboard")).resolve()
    target_project = getattr(args, "project", None)
    board = Blackboard(root_dir=board_dir, project=target_project)
    if not board.is_initialized():
        print(f"Blackboard at '{board_dir}' is not initialized. Run 'modue-harness init' first.")
        return 1

    state = board.load_state()
    projects_dir = Path(getattr(args, "projects_dir", "projects")).resolve()
    projects_set = set()
    if projects_dir.exists():
        for p in projects_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                projects_set.add(p.name)
    if board_dir.exists():
        for p in board_dir.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name not in {"tasks", "artifacts", "logs"}:
                projects_set.add(p.name)
    existing_projects = sorted(list(projects_set))

    active_p = target_project or state.get("current_project")
    print(f"=== ModueHarness Blackboard Status ===")
    print(f"Location: {board.root_dir}")
    print(f"Projects Directory: {projects_dir}")
    print(f"Session ID: {state.get('session_id', 'N/A')}")
    print(f"Workflow Status: {state.get('status', 'unknown')}")
    print(f"Current Step: {state.get('current_step', 'None')}")
    if active_p:
        print(f"Active Project: {active_p}")

    print(f"\n--- Projects ({len(existing_projects)}) ---")
    if not existing_projects:
        print("  (No project directories yet)")
    for p in existing_projects:
        active = " [ACTIVE]" if p == active_p else ""
        print(f"  • {p}{active}")

    tasks = board.list_tasks()
    print(f"\n--- Tasks ({len(tasks)}) ---")
    if not tasks:
        print("  (No tasks created yet)")
    for task in tasks:
        status_marker = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "▶",
            "pending": "○",
        }.get(task.status.value, "?")
        print(f"  [{status_marker}] {task.id} ({task.assigned_agent}): {task.status.value}")

    artifacts = board.list_artifacts()
    print(f"\n--- Artifacts ({len(artifacts)}) ---")
    if not artifacts:
        print("  (No artifacts stored)")
    for art in artifacts:
        print(f"  • {art}")

    return 0


def handle_projects(args: argparse.Namespace) -> int:
    """Handle 'projects' command: List projects or delete a project."""
    projects_dir = Path(getattr(args, "projects_dir", "projects")).resolve()
    board_dir = Path(getattr(args, "dir", "blackboard")).resolve()

    delete_target = getattr(args, "delete", None)
    if delete_target:
        import shutil
        deleted_any = False
        target_proj = projects_dir / delete_target
        if target_proj.exists():
            shutil.rmtree(target_proj)
            deleted_any = True
            print(f"✓ Removed project directory:    {target_proj}")
        target_bb = board_dir / delete_target
        if target_bb.exists():
            shutil.rmtree(target_bb)
            deleted_any = True
            print(f"✓ Removed blackboard directory: {target_bb}")
        if not deleted_any:
            print(f"⚠️ Project '{delete_target}' not found in {projects_dir} or {board_dir}.")
            return 1
        print(f"✓ Successfully deleted project '{delete_target}'.")
        return 0

    projects = set()
    if projects_dir.exists():
        for p in projects_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                projects.add(p.name)
    if board_dir.exists():
        for p in board_dir.iterdir():
            if p.is_dir() and not p.name.startswith(".") and p.name not in {"tasks", "artifacts", "logs"}:
                projects.add(p.name)

    sorted_projects = sorted(list(projects))
    print(f"=== ModueHarness Projects ({len(sorted_projects)}) ===")
    print(f"Base Directory: {projects_dir}")
    if not sorted_projects:
        print("  (No projects created yet. Run with '-P <project_name>' to create one.)")
    for p in sorted_projects:
        print(f"  • {p}")
    return 0


def handle_ui(args: argparse.Namespace) -> int:
    """Handle 'ui' command or '--ui' flag: Launch NiceGUI web dashboard."""
    try:
        from modue_harness.ui.controller import UIController
        from modue_harness.ui.web.app import run_app
    except ImportError as e:
        print(f"❌ Error loading UI module: {e}")
        print("Tip: Install UI dependencies using: pip install 'modue-harness[ui]' or pip install nicegui")
        return 1

    lang = getattr(args, "lang", "ko") or "ko"
    ctrl = UIController(
        project_name=getattr(args, "project", None),
        projects_root=Path(getattr(args, "projects_dir", "projects")).resolve(),
        blackboard_dir=Path(getattr(args, "dir", "blackboard")).resolve(),
        agents_file=Path(args.agents).resolve() if getattr(args, "agents", None) else None,
        specific_agent=getattr(args, "agent", None),
        model=getattr(args, "model", None),
        effort=getattr(args, "effort", None),
        timeout=getattr(args, "timeout", None),
        lang=lang,
    )
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8080)
    open_browser = not getattr(args, "no_browser", False)

    print(f"🌐 Starting ModueHarness Web UI at http://{host}:{port} ...")
    try:
        run_app(controller=ctrl, host=host, port=port, open_browser=open_browser, lang=lang)
        return 0
    except KeyboardInterrupt:
        print("\n👋 ModueHarness Web UI 서버가 정상 종료되었습니다.")
        return 0
    except ImportError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:
        print(f"❌ Failed to run Web UI: {e}")
        return 1


def handle_tui(args: argparse.Namespace) -> int:
    """Handle 'tui' command or '--tui' flag: Launch Textual terminal dashboard."""
    try:
        from modue_harness.ui.controller import UIController
        from modue_harness.ui.tui.app import run_tui_app
    except ImportError as e:
        print(f"❌ Error loading TUI module: {e}")
        print("Tip: Install UI dependencies using: pip install 'modue-harness[ui]' or pip install textual")
        return 1

    ctrl = UIController(
        project_name=getattr(args, "project", None),
        projects_root=Path(getattr(args, "projects_dir", "projects")).resolve(),
        blackboard_dir=Path(getattr(args, "dir", "blackboard")).resolve(),
        agents_file=Path(args.agents).resolve() if getattr(args, "agents", None) else None,
        specific_agent=getattr(args, "agent", None),
        model=getattr(args, "model", None),
        effort=getattr(args, "effort", None),
        timeout=getattr(args, "timeout", None),
        lang=getattr(args, "lang", "ko") or "ko",
    )

    try:
        run_tui_app(controller=ctrl)
        return 0
    except KeyboardInterrupt:
        print("\n👋 ModueHarness TUI가 정상 종료되었습니다.")
        return 0
    except ImportError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:
        print(f"❌ Failed to run TUI: {e}")
        return 1


def handle_interactive_or_prompt(args: argparse.Namespace) -> int:
    """Handle direct CLI command execution or interactive REPL session."""
    if getattr(args, "ui", False):
        return handle_ui(args)
    if getattr(args, "tui", False):
        return handle_tui(args)

    project_name = getattr(args, "project", None)
    projects_dir = Path(getattr(args, "projects_dir", "projects")).resolve()
    board_dir = Path(getattr(args, "dir", "blackboard")).resolve()
    agents_file = Path(args.agents).resolve() if getattr(args, "agents", None) else None
    specific_agent = getattr(args, "agent", None)

    session = InteractiveSession(
        project_name=project_name,
        projects_root=projects_dir,
        blackboard_dir=board_dir,
        agents_file=agents_file,
        specific_agent=specific_agent,
        model=getattr(args, "model", None),
        effort=getattr(args, "effort", None),
        timeout=getattr(args, "timeout", None),
    )

    # 1. User requested interactive session explicitly or running in a TTY terminal without args
    if getattr(args, "interactive", False) or (not getattr(args, "prompt", None) and sys.stdin.isatty()):
        session.start_repl()
        return 0

    # 2. User supplied a prompt/command
    if getattr(args, "prompt", None):
        prompt = args.prompt.strip()
        active_p = session.project_name or "project_1"
        print(f"🚀 [ModueHarness] 작업 실행 (프로젝트: '{active_p}')")
        print(f"   구현 디렉터리: {session.project_dir or (projects_dir / active_p)}")
        print(f"   공용 칠판:     {session.blackboard_dir or (board_dir / active_p)}")
        print(f"   작업 명령:     {prompt}\n")

        summary = session.execute_command(prompt)

        print("\n" + "=" * 64)
        status_text = "SUCCESS" if summary["success"] else "FAILED"
        print(f"상태: {status_text} (소요 시간: {summary['total_duration_sec']:.2f}s)")
        print(f"프로젝트 구현 폴더: {summary['project_dir']}")
        if not summary["success"] and summary.get("error"):
            print(f"❌ [실패 상세 원인]: {summary.get('error')}")

        if summary.get("subtasks"):
            print(f"\n[실행된 서브태스크 ({len(summary['subtasks'])})]")
            for st in summary["subtasks"]:
                mark = "✓" if st.get("is_success") else "✗"
                cmd_line = f"\n      💻 CLI: {st.get('command')}" if st.get("command") else ""
                print(f"  [{mark}] {st.get('task_id')} ({st.get('agent')}){cmd_line}")
                if not st.get("is_success") and st.get("error"):
                    print(f"      ❌ 오류 상세: {st.get('error')}")

        if summary.get("project_files"):
            print(f"\n[프로젝트 내 생성/수정된 파일 ({len(summary['project_files'])})]")
            for pf in summary["project_files"]:
                print(f"  📄 {pf}")

        if summary.get("artifacts"):
            print(f"\n[블랙보드 정보교환 산출물 ({len(summary['artifacts'])})]")
            for af in summary["artifacts"]:
                print(f"  📌 {af}")
        print("=" * 64)

        return 0 if summary["success"] else 1

    # 3. Non-interactive without prompt (e.g. headless script or default run in test)
    print(f"ModueHarness v{__version__}")
    print("Multi-AI CLI Collaboration Framework (Interactive CLI & Project-Isolated)")
    print("\n사용법:")
    print("  modue-harness \"<작업 명령>\" [-P <프로젝트명>]   # 프로젝트에 코드 직접 구현")
    print("  modue-harness -i                                # 대화형 CLI 프롬프트 실행")
    print("  modue-harness --ui / modue-harness ui           # 웹 대시보드 실행 (NiceGUI)")
    print("  modue-harness --tui / modue-harness tui         # 터미널 대시보드 실행 (Textual)")
    print("  modue-harness projects                          # 생성된 프로젝트 목록")
    print("  modue-harness status                            # 상태 및 태스크 현황")
    print("  modue-harness --help                            # 전체 옵션 도움말")
    return 0


def handle_run(args: argparse.Namespace) -> int:
    """Handle 'run' command (legacy workflow runner)."""
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        return 1

    board_dir = Path(args.dir).resolve()
    board = Blackboard(root_dir=board_dir)

    agents_path = Path(args.agents).resolve() if getattr(args, "agents", None) else None

    try:
        config = WorkflowConfig.load(config_path, agents_file_override=agents_path)
    except Exception as e:
        print(f"Error loading workflow config: {e}")
        return 1

    print(f"🚀 Starting workflow '{config.name}' (topology: {config.topology})...")
    print(f"   Blackboard: {board.root_dir}")
    print(f"   Total steps: {len(config.steps)}")

    report_plugin = None
    if getattr(args, "report", None):
        report_plugin = MarkdownReportPlugin(output_path=Path(args.report).resolve())

    runner = PipelineRunner(config=config, blackboard=board)
    if report_plugin:
        report_plugin.on_workflow_start(config.name, len(config.steps))

    summary = runner.run()

    if report_plugin:
        for s in summary["steps"]:
            report_plugin.on_step_finish(
                step_id=s["step_id"],
                agent_name=s["agent"],
                is_success=s["is_success"],
            )
        report_plugin.on_workflow_finish(summary)
        print(f"📄 Markdown execution report generated at: {report_plugin.output_path}")

    print(f"\nWorkflow finished with status: {summary['status']} (took {summary['total_duration_sec']:.2f}s)")
    for step in summary["steps"]:
        mark = "✓" if step["is_success"] else "✗"
        print(f"  [{mark}] Step '{step['step_id']}' by {step['agent']}: exit={step['exit_code']} ({step['duration_sec']:.2f}s)")
        if step.get("error_message"):
            print(f"      Error: {step['error_message']}")

    return 0 if summary["success"] else 1


def handle_debate(args: argparse.Namespace) -> int:
    """Handle 'debate' command."""
    board_dir = Path(args.dir).resolve()
    board = Blackboard(root_dir=board_dir)

    proposer_adapter = create_adapter(args.proposer, name="proposer")
    challenger_adapter = create_adapter(args.challenger, name="challenger")
    judge_adapter = create_adapter(args.judge, name="judge")

    runner = DebateRunner(
        topic=args.topic,
        proposer_adapter=proposer_adapter,
        challenger_adapter=challenger_adapter,
        judge_adapter=judge_adapter,
        blackboard=board,
        rounds=args.rounds,
    )

    print(f"⚖️ Starting Multi-AI Debate on topic: '{args.topic}'...")
    print(f"   Proposer: {args.proposer} | Challenger: {args.challenger} | Judge: {args.judge}")
    print(f"   Rounds: {args.rounds}")

    result = runner.run()
    print(f"\n✓ Debate concluded successfully ({result['total_duration_sec']:.2f}s)!")
    print(f"   Consensus saved to: {board.root_dir / 'artifacts' / 'consensus.md'}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    try:
        # Must run before the first print: Windows consoles default to the
        # system locale codec (cp949) and would abort on status glyphs.
        ensure_utf8_io()
        load_dotenv()
        args = parse_cli_args(argv)

        if args.command == "init":
            return handle_init(args)
        elif args.command == "status":
            return handle_status(args)
        elif args.command == "projects":
            return handle_projects(args)
        elif args.command == "ui":
            return handle_ui(args)
        elif args.command == "tui":
            return handle_tui(args)
        elif args.command == "run":
            return handle_run(args)
        elif args.command == "debate":
            return handle_debate(args)

        # If no subcommand, handle direct CLI prompt or interactive session
        return handle_interactive_or_prompt(args)
    except KeyboardInterrupt:
        print("\n👋 작업을 종료했습니다 (Ctrl+C).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
