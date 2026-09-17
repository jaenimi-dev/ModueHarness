"""Tests for split AI and Task specification loading."""

from pathlib import Path
import pytest
import yaml

from modue_harness.engine.workflow import WorkflowConfig


def test_load_workflow_with_external_agents_file(tmp_path: Path):
    """Verify loading workflow that references an external agents_file."""
    agents_file = tmp_path / "team.yaml"
    agents_data = {
        "name": "core-team",
        "agents": {
            "planner": {"adapter": "claude", "role": "Architect"},
            "coder": {"adapter": "agy", "role": "Engineer"},
        },
    }
    agents_file.write_text(yaml.dump(agents_data), encoding="utf-8")

    workflow_file = tmp_path / "tasks.yaml"
    workflow_data = {
        "name": "split-test",
        "agents_file": "team.yaml",
        "workflow": {
            "steps": [
                {"id": "step_1", "agent": "planner", "instruction": "Plan"},
                {"id": "step_2", "agent": "coder", "instruction": "Code"},
            ]
        },
    }
    workflow_file.write_text(yaml.dump(workflow_data), encoding="utf-8")

    config = WorkflowConfig.load(workflow_file)
    assert len(config.agents) == 2
    assert "planner" in config.agents
    assert config.agents["planner"].adapter == "claude"
    assert "coder" in config.agents
    assert config.agents["coder"].adapter == "agy"
    assert len(config.steps) == 2


def test_load_workflow_with_cli_agents_override(tmp_path: Path):
    """Verify CLI agents_file_override takes precedence over agents_file in workflow."""
    default_team_file = tmp_path / "default_team.yaml"
    default_team_data = {
        "agents": {"worker": {"adapter": "generic", "role": "Default Worker"}}
    }
    default_team_file.write_text(yaml.dump(default_team_data), encoding="utf-8")

    override_team_file = tmp_path / "override_team.yaml"
    override_team_data = {
        "agents": {"worker": {"adapter": "claude", "role": "Elite Worker"}}
    }
    override_team_file.write_text(yaml.dump(override_team_data), encoding="utf-8")

    workflow_file = tmp_path / "mission.yaml"
    workflow_data = {
        "name": "override-test",
        "agents_file": "default_team.yaml",
        "workflow": {
            "steps": [{"id": "s1", "agent": "worker", "instruction": "Do work"}]
        },
    }
    workflow_file.write_text(yaml.dump(workflow_data), encoding="utf-8")

    config = WorkflowConfig.load(workflow_file, agents_file_override=override_team_file)
    assert config.agents["worker"].adapter == "claude"
    assert config.agents["worker"].role == "Elite Worker"
