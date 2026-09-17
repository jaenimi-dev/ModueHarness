"""Command Line Interface for ModueHarness with Pipeline, Debate, and Report support."""

import argparse
from pathlib import Path
import sys
from typing import List, Optional

from modue_harness import __version__
from modue_harness.adapters import create_adapter
from modue_harness.core.blackboard import Blackboard
from modue_harness.engine.debate import DebateRunner
from modue_harness.engine.pipeline import PipelineRunner
from modue_harness.engine.workflow import WorkflowConfig
from modue_harness.plugins.reporter import MarkdownReportPlugin


def create_parser() -> argparse.ArgumentParser:
    """Build and configure the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="modue-harness",
        description="ModueHarness - Multi-AI CLI Collaboration Harness",
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

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Initialize blackboard workspace directory")
    init_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )

    # Command: status
    status_parser = subparsers.add_parser("status", help="Display current blackboard status and tasks")
    status_parser.add_argument(
        "--dir", "-d",
        type=str,
        default="blackboard",
        help="Path to blackboard directory (default: blackboard)",
    )

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run a multi-AI collaboration workflow")
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

    return parser


def handle_init(args: argparse.Namespace) -> int:
    """Handle 'init' command."""
    board_dir = Path(args.dir).resolve()
    board = Blackboard(root_dir=board_dir)
    board.initialize()
    print(f"✓ Initialized ModueHarness blackboard at: {board.root_dir}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    """Handle 'status' command."""
    board_dir = Path(args.dir).resolve()
    board = Blackboard(root_dir=board_dir)
    if not board.is_initialized():
        print(f"Blackboard at '{board_dir}' is not initialized. Run 'modue-harness init' first.")
        return 1

    state = board.load_state()
    print(f"=== ModueHarness Blackboard Status ===")
    print(f"Location: {board.root_dir}")
    print(f"Session ID: {state.get('session_id', 'N/A')}")
    print(f"Workflow Status: {state.get('status', 'unknown')}")
    print(f"Current Step: {state.get('current_step', 'None')}")

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


def handle_run(args: argparse.Namespace) -> int:
    """Handle 'run' command."""
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
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return handle_init(args)
    elif args.command == "status":
        return handle_status(args)
    elif args.command == "run":
        return handle_run(args)
    elif args.command == "debate":
        return handle_debate(args)

    if args.debug:
        print(f"[DEBUG] ModueHarness v{__version__} initialized in debug mode.")
    else:
        print(f"ModueHarness v{__version__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
