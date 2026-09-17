"""Process Supervisor and Safety Watchdog."""

from collections import Counter
import os
import signal
import subprocess
import threading
import time
from typing import Callable, List, Optional


class ProcessSupervisor:
    """Monitors subprocess execution for timeouts, activity stalls, and infinite loops."""

    def __init__(
        self,
        timeout: float = 300.0,
        stall_timeout: Optional[float] = None,
        max_repeated_lines: int = 20,
        approval_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self.timeout = timeout
        self.stall_timeout = stall_timeout
        self.max_repeated_lines = max_repeated_lines
        self.approval_callback = approval_callback

        self._last_activity_time: float = time.time()
        self._is_terminated: bool = False
        self._termination_reason: Optional[str] = None
        self._line_counter: Counter = Counter()

    def touch_activity(self) -> None:
        """Update the last activity timestamp when new output is received."""
        self._last_activity_time = time.time()

    def record_output_line(self, line: str) -> bool:
        """Track output lines to detect repeating loop patterns. Returns False if loop detected."""
        self.touch_activity()
        stripped = line.strip()
        if stripped and len(stripped) > 5:
            self._line_counter[stripped] += 1
            if self._line_counter[stripped] >= self.max_repeated_lines:
                self._termination_reason = f"Infinite loop detected: repeating line pattern ('{stripped[:40]}...')"
                return False
        return True

    def check_stall(self) -> bool:
        """Return True if execution has stalled without output beyond stall_timeout."""
        if self.stall_timeout is not None:
            elapsed_since_activity = time.time() - self._last_activity_time
            if elapsed_since_activity > self.stall_timeout:
                self._termination_reason = f"Execution stalled: no output for {elapsed_since_activity:.1f}s"
                return True
        return False

    def terminate_process(self, process: subprocess.Popen, grace_period_sec: float = 1.0) -> None:
        """Safely terminate a subprocess tree with SIGTERM, then SIGKILL if needed."""
        if process.poll() is not None:
            return

        self._is_terminated = True
        try:
            # Send SIGTERM
            process.terminate()
            time.sleep(grace_period_sec)
            if process.poll() is None:
                # Force kill
                process.kill()
        except Exception:
            pass

    def request_approval(self, step_id: str, prompt: str) -> bool:
        """Prompt user or handler for permission to execute a critical step."""
        if self.approval_callback:
            return self.approval_callback(step_id, prompt)
        # Default auto-accept if no interactive approval handler registered
        return True

    @property
    def termination_reason(self) -> Optional[str]:
        """Reason why execution was terminated early, if any."""
        return self._termination_reason
