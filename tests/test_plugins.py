"""Tests for plugins and MarkdownReportPlugin."""

from pathlib import Path
from modue_harness.core.types import TurnResult
from modue_harness.plugins.base import BasePlugin, PluginManager
from modue_harness.plugins.reporter import MarkdownReportPlugin


def test_plugin_manager_dispatch():
    """Verify plugin manager triggers hooks on registered plugins."""
    events_received = []

    class DummyPlugin(BasePlugin):
        def on_workflow_start(self, workflow_name: str, total_steps: int) -> None:
            events_received.append(f"start:{workflow_name}")

        def on_step_start(self, step_id: str, agent_name: str, instruction: str) -> None:
            events_received.append(f"step:{step_id}")

        def on_artifact_created(self, artifact_path: str, size_bytes: int) -> None:
            events_received.append(f"artifact:{artifact_path}")

    pm = PluginManager([DummyPlugin()])
    pm.dispatch_workflow_start("test_wf", 2)
    pm.dispatch_step_start("s1", "agent1", "do work")
    pm.dispatch_artifact_created("doc.md", 100)

    assert events_received == ["start:test_wf", "step:s1", "artifact:doc.md"]


def test_markdown_report_plugin(tmp_path: Path):
    """Verify MarkdownReportPlugin writes formatted report file."""
    report_file = tmp_path / "execution_report.md"
    plugin = MarkdownReportPlugin(output_path=report_file)

    plugin.on_workflow_start("test-pipeline", 1)
    plugin.on_step_finish(
        step_id="step_alpha",
        agent_name="coder",
        is_success=True,
        turn_result=TurnResult(status="completed", duration_sec=1.23, exit_code=0),
    )
    plugin.on_workflow_finish({"status": "completed", "success": True, "total_duration_sec": 1.23})

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# ModueHarness Execution Report" in content
    assert "test-pipeline" in content
    assert "step_alpha" in content
    assert "1.23s" in content
