"""Tests for ProcessSupervisor and safety watchdog."""

import time
from modue_harness.core.supervisor import ProcessSupervisor


def test_supervisor_activity_and_stall():
    """Verify stall detection when activity halts."""
    supervisor = ProcessSupervisor(timeout=10.0, stall_timeout=0.2)
    assert not supervisor.check_stall()

    # Wait to trigger stall
    time.sleep(0.3)
    assert supervisor.check_stall()
    assert "stalled" in (supervisor.termination_reason or "")


def test_supervisor_loop_detection():
    """Verify repeating output loop detection."""
    supervisor = ProcessSupervisor(max_repeated_lines=5)
    repeating_line = "Error: database connection timeout retry..."

    for i in range(4):
        ok = supervisor.record_output_line(repeating_line)
        assert ok

    # 5th occurrence triggers loop alarm
    ok = supervisor.record_output_line(repeating_line)
    assert not ok
    assert "loop detected" in (supervisor.termination_reason or "").lower()


def test_supervisor_approval_callback():
    """Verify human-in-the-loop approval mechanism."""
    # Denied case
    denying_supervisor = ProcessSupervisor(approval_callback=lambda step, p: False)
    assert not denying_supervisor.request_approval("step_deploy", "Deploy to production?")

    # Approved case
    approving_supervisor = ProcessSupervisor(approval_callback=lambda step, p: True)
    assert approving_supervisor.request_approval("step_build", "Build code?")
