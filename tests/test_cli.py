"""Tests for CLI functionality and subcommands."""

import json
from pathlib import Path
import pytest
from modue_harness.cli import main


def test_cli_version_flag(capsys):
    """Test modue-harness --version flag."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "0.8.0" in captured.out


def test_cli_default_run(capsys):
    """Test modue-harness default execution without args."""
    exit_code = main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "ModueHarness v0.8.0" in captured.out


def test_cli_init_and_status(tmp_path: Path, capsys):
    """Test modue-harness init and status commands."""
    board_dir = tmp_path / "blackboard"

    # Status before init should report uninitialized
    exit_code = main(["status", "--dir", str(board_dir)])
    assert exit_code == 1

    # Run init
    exit_code = main(["init", "--dir", str(board_dir)])
    assert exit_code == 0
    assert board_dir.exists()
    assert (board_dir / "state.json").exists()

    # Status after init
    exit_code = main(["status", "--dir", str(board_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Workflow Status: initialized" in captured.out


def test_cli_run_workflow(tmp_path: Path, capsys):
    """Test modue-harness run with a valid JSON config."""
    config_file = tmp_path / "workflow.json"
    board_dir = tmp_path / "blackboard"

    config_data = {
        "name": "cli-test-workflow",
        "agents": {
            "tester": {
                "adapter": "generic",
                "command": "echo",
                "args": ["-n"],
            }
        },
        "workflow": {
            "topology": "pipeline",
            "steps": [
                {
                    "id": "echo_step",
                    "agent": "tester",
                    "instruction": "Hello from CLI test",
                }
            ],
        },
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    exit_code = main(["run", "--config", str(config_file), "--dir", str(board_dir)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Workflow finished with status: completed" in captured.out


def test_cli_run_with_report(tmp_path: Path, capsys):
    """Test modue-harness run with --report flag."""
    config_file = tmp_path / "workflow_rep.json"
    report_file = tmp_path / "exec_report.md"
    board_dir = tmp_path / "blackboard"

    config_data = {
        "name": "report-workflow",
        "agents": {"tester": {"adapter": "generic", "command": "echo", "args": ["-n"]}},
        "workflow": {"topology": "pipeline", "steps": [{"id": "s1", "agent": "tester", "instruction": "Hi"}]},
    }
    config_file.write_text(json.dumps(config_data), encoding="utf-8")

    exit_code = main(["run", "--config", str(config_file), "--dir", str(board_dir), "--report", str(report_file)])
    assert exit_code == 0
    assert report_file.exists()
    assert "# ModueHarness Execution Report" in report_file.read_text(encoding="utf-8")


def test_cli_debate_command(tmp_path: Path, capsys):
    """Test modue-harness debate subcommand."""
    board_dir = tmp_path / "blackboard"
    exit_code = main([
        "debate",
        "--topic", "Tabs vs Spaces",
        "--proposer", "generic",
        "--challenger", "generic",
        "--judge", "generic",
        "--rounds", "1",
        "--dir", str(board_dir),
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Starting Multi-AI Debate" in captured.out
    assert "Debate concluded successfully" in captured.out
    assert (board_dir / "artifacts" / "consensus.md").exists()


def test_cli_timeout_option():
    """Verify --timeout flag is parsed in cli arguments."""
    from modue_harness.cli import parse_cli_args
    args = parse_cli_args(["--timeout", "120.5"])
    assert args.timeout == 120.5

    args_default = parse_cli_args([])
    assert args_default.timeout is None


def test_cli_status_project_isolated_blackboard(tmp_path: Path, capsys):
    """Test modue-harness status -P <project> with project-isolated blackboard."""
    from modue_harness.core.blackboard import Blackboard

    board_dir = tmp_path / "blackboard"
    proj_a_board = Blackboard(root_dir=board_dir, project="alpha_corp")
    proj_a_board.initialize()
    proj_a_board.write_artifact("report.md", "# Alpha Report")

    # Run status with -P alpha_corp
    exit_code = main(["status", "--dir", str(board_dir), "-P", "alpha_corp"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Active Project: alpha_corp" in captured.out
    assert "report.md" in captured.out
    assert "alpha_corp" in captured.out



def test_cli_status_excludes_reserved_blackboard_dirs(tmp_path: Path, capsys):
    """Reserved blackboard folders (jobs/, usage/, ...) are not projects."""
    from modue_harness.core.blackboard import RESERVED_DIR_NAMES, Blackboard

    board_dir = tmp_path / "blackboard"
    projects_dir = tmp_path / "projects"
    Blackboard(root_dir=board_dir).initialize()
    projects_dir.mkdir(parents=True, exist_ok=True)
    Blackboard(root_dir=board_dir, project="alpha_corp").initialize()

    exit_code = main([
        "status", "--dir", str(board_dir), "--projects-dir", str(projects_dir),
    ])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "--- Projects (1) ---" in captured.out
    assert "alpha_corp" in captured.out
    for reserved in RESERVED_DIR_NAMES:
        assert f"• {reserved}" not in captured.out


def test_cli_projects_excludes_reserved_blackboard_dirs(tmp_path: Path, capsys):
    """The 'projects' subcommand applies the same reserved-name filter."""
    from modue_harness.core.blackboard import RESERVED_DIR_NAMES, Blackboard

    board_dir = tmp_path / "blackboard"
    projects_dir = tmp_path / "projects"
    Blackboard(root_dir=board_dir).initialize()
    projects_dir.mkdir(parents=True, exist_ok=True)
    Blackboard(root_dir=board_dir, project="alpha_corp").initialize()

    exit_code = main([
        "projects", "--dir", str(board_dir), "--projects-dir", str(projects_dir),
    ])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "=== ModueHarness Projects (1) ===" in captured.out
    assert "alpha_corp" in captured.out
    for reserved in RESERVED_DIR_NAMES:
        assert f"• {reserved}" not in captured.out


def test_find_project_dirs_ignores_unrelated_folders(tmp_path: Path):
    """A stray folder without project markers is not reported as a project."""
    from modue_harness.core.blackboard import Blackboard

    board_dir = tmp_path / "blackboard"
    Blackboard(root_dir=board_dir).initialize()
    Blackboard(root_dir=board_dir, project="alpha_corp").initialize()
    (board_dir / "scratch_notes").mkdir(parents=True, exist_ok=True)

    found = {d.name for d in Blackboard.find_project_dirs(board_dir)}
    assert found == {"alpha_corp"}
