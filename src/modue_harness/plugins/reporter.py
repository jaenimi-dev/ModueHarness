"""Markdown execution report generator plugin."""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from modue_harness.core.types import TurnResult
from modue_harness.plugins.base import BasePlugin


class MarkdownReportPlugin(BasePlugin):
    """Generates a structured markdown report of workflow execution."""

    def __init__(
        self,
        output_path: Optional[Path] = None,
        name: str = "markdown_reporter",
    ) -> None:
        super().__init__(name=name)
        self.output_path = output_path
        self._step_records: List[Dict[str, Any]] = []
        self._workflow_name: str = "unknown"
        self._start_time: Optional[datetime.datetime] = None

    def on_workflow_start(self, workflow_name: str, total_steps: int) -> None:
        self._workflow_name = workflow_name
        self._start_time = datetime.datetime.now()
        self._step_records.clear()

    def on_step_finish(
        self,
        step_id: str,
        agent_name: str,
        is_success: bool,
        turn_result: Optional[TurnResult] = None,
    ) -> None:
        self._step_records.append({
            "step_id": step_id,
            "agent_name": agent_name,
            "is_success": is_success,
            "duration_sec": turn_result.duration_sec if turn_result else 0.0,
            "exit_code": turn_result.exit_code if turn_result else 0,
            "error_message": turn_result.error_message if turn_result else None,
        })

    def on_workflow_finish(self, summary: Dict[str, Any]) -> None:
        if not self.output_path:
            return

        end_time = datetime.datetime.now()
        duration_str = f"{summary.get('total_duration_sec', 0.0):.2f}s"
        status = summary.get("status", "unknown").upper()
        status_icon = "✅" if summary.get("success") else "❌"

        lines = [
            f"# ModueHarness Execution Report",
            "",
            f"**Workflow:** `{self._workflow_name}`  ",
            f"**Status:** {status_icon} `{status}`  ",
            f"**Total Duration:** `{duration_str}`  ",
            f"**Timestamp:** `{end_time.isoformat()}`  ",
            "",
            "## 📋 Step Execution Summary",
            "",
            "| Step ID | Agent | Status | Duration | Exit Code | Notes |",
            "|---|---|---|---|---|---|",
        ]

        for s in self._step_records:
            icon = "✅ Success" if s["is_success"] else "❌ Failed"
            notes = s["error_message"] or "-"
            lines.append(
                f"| `{s['step_id']}` | `{s['agent_name']}` | {icon} | {s['duration_sec']:.2f}s | {s['exit_code']} | {notes} |"
            )

        lines.append("")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("\n".join(lines), encoding="utf-8")
