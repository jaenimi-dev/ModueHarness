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
    assert "0.3.0" in captured.out


def test_cli_default_run(capsys):
    """Test modue-harness default execution without args."""
    exit_code = main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "ModueHarness v0.3.0" in captured.out


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
