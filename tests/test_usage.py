"""Unit tests for UsageTracker, rate limit detection, and sliding window quota tracking."""

import json
from pathlib import Path
import time
import pytest

from modue_harness.core.blackboard import Blackboard
from modue_harness.core.usage import (
    UsageTracker,
    detect_limit_signal,
    extract_or_estimate_usage,
)
from modue_harness.ui.controller import UIController


def test_detect_limit_signal():
    """Verify regex detection of 5-hour, weekly, and quota exhausted limits."""
    # Claude 5-hour limit
    claude_5h = "Error: You have reached your 5-hour limit. Resets at 3:30 PM."
    sig_5h = detect_limit_signal(claude_5h, "")
    assert sig_5h["is_rate_limited"] is True
    assert sig_5h["limit_type"] == "5h"
    assert sig_5h["resets_at"] == "3:30 PM"

    # Claude weekly limit
    claude_wk = "Weekly limit reached. Resets on Monday at 9:00 AM."
    sig_wk = detect_limit_signal("", claude_wk)
    assert sig_wk["is_rate_limited"] is True
    assert sig_wk["limit_type"] == "weekly"

    # OpenAI / Codex quota
    openai_err = "APIError: Rate limit reached for model gpt-4o. Please try again later."
    sig_oa = detect_limit_signal(openai_err, "")
    assert sig_oa["is_rate_limited"] is True
    assert sig_oa["limit_type"] == "quota"

    # Antigravity / Gemini quota
    gemini_err = "google.api_core.exceptions.ResourceExhausted: 429 Resource has been exhausted (e.g. check quota)."
    sig_gem = detect_limit_signal("", gemini_err)
    assert sig_gem["is_rate_limited"] is True
    assert sig_gem["limit_type"] == "quota"

    # Normal successful execution
    normal_out = "Everything compiled and tested successfully."
    sig_norm = detect_limit_signal(normal_out, "")
    assert sig_norm["is_rate_limited"] is False
    assert sig_norm["limit_type"] is None
    assert sig_norm["resets_at"] is None


def test_extract_or_estimate_usage():
    """Verify parsing of structured JSON usage, text metrics, and heuristic fallback."""
    # 1. Structured JSON output (Claude --output-format json)
    json_out = json.dumps({
        "type": "result",
        "cost_usd": 0.0125,
        "usage": {
            "input_tokens": 1500,
            "output_tokens": 400,
        },
    })
    usage_json = extract_or_estimate_usage(json_out, "")
    assert usage_json["input_tokens"] == 1500
    assert usage_json["output_tokens"] == 400
    assert usage_json["total_tokens"] == 1900
    assert usage_json["cost_usd"] == 0.0125
    assert usage_json["is_estimated"] is False

    # 2. Text tokens and cost
    text_out = "Execution finished. Tokens: 2,500. Cost: $0.035"
    usage_text = extract_or_estimate_usage(text_out, "")
    assert usage_text["total_tokens"] == 2500
    assert usage_text["cost_usd"] == 0.035
    assert usage_text["is_estimated"] is False

    # 3. Fallback character-based heuristic
    prompt = "Create a python script that calculates fibonacci numbers."  # ~58 chars -> ~14 tokens
    response = "def fib(n): return 1 if n <= 2 else fib(n-1) + fib(n-2)"  # ~56 chars -> ~14 tokens
    usage_est = extract_or_estimate_usage(response, "", prompt_length=len(prompt))
    assert usage_est["is_estimated"] is True
    assert usage_est["input_tokens"] > 0
    assert usage_est["output_tokens"] > 0
    assert usage_est["total_tokens"] > 0
    assert usage_est["cost_usd"] > 0.0


def test_usage_tracker_sliding_windows(tmp_path: Path):
    """Verify recording entries and 5-hour / weekly window aggregation."""
    tracker = UsageTracker(root_dir=tmp_path / "board")

    # Record two turns for claude
    e1 = tracker.record_turn(
        agent="claude",
        stdout="First output with 100 characters " * 4,
        stderr="",
        duration_sec=1.2,
        job_id="job_1",
        prompt_length=400,
    )
    assert e1.agent == "claude"
    assert e1.job_id == "job_1"

    time.sleep(0.05)
    e2 = tracker.record_turn(
        agent="claude",
        stdout="Second output with another 100 characters " * 4,
        stderr="",
        duration_sec=2.1,
        job_id="job_2",
        prompt_length=400,
    )

    # Status check
    status = tracker.get_agent_status("claude")
    assert status["agent"] == "claude"
    assert status["status"] == "normal"
    assert status["status_label"] == "정상"
    assert status["five_hour"]["calls"] == 2
    assert status["weekly"]["calls"] == 2
    assert status["five_hour"]["total_tokens"] > 0
    assert status["five_hour"]["limit_tokens"] > 0

    # Summary for all
    summary = tracker.get_all_agents_summary(["claude", "codex"])
    agent_names = [s["agent"] for s in summary]
    assert "claude" in agent_names
    assert "codex" in agent_names


def test_usage_tracker_rate_limit_detection(tmp_path: Path):
    """Verify rate limit signals transition agent status to rate_limited."""
    tracker = UsageTracker(root_dir=tmp_path / "board")

    tracker.record_turn(
        agent="claude",
        stdout="",
        stderr="Error: You have reached your 5-hour limit. Resets at 4:15 PM.",
        duration_sec=0.5,
        job_id="job_failed",
        is_success=False,
    )

    status = tracker.get_agent_status("claude")
    assert status["status"] == "rate_limited"
    assert status["status_label"] == "한도 초과"
    assert status["resets_at"] == "4:15 PM"


def test_blackboard_and_controller_usage_integration(tmp_path: Path):
    """Verify Blackboard delegation and UIController get_usage_summary."""
    board = Blackboard(root_dir=tmp_path / "blackboard")
    board.initialize()

    # Record turn through blackboard
    board.record_usage(
        agent="tester",
        stdout="Test passed successfully.",
        stderr="",
        duration_sec=0.8,
        job_id="job_10",
        prompt_length=50,
    )

    usage = board.get_agent_usage("tester")
    assert usage["five_hour"]["calls"] == 1
    assert usage["status"] == "normal"

    # Query via UIController
    ctrl = UIController(
        project_name="demo",
        projects_root=tmp_path / "projects",
        blackboard_dir=tmp_path / "blackboard",
    )
    ctrl.session.agents = {"tester": None, "conductor": None}
    summary = ctrl.get_usage_summary()
    assert len(summary) >= 1
    assert any(s["agent"] == "tester" for s in summary)
