"""Tests for UTF-8 standard stream and child process encoding enforcement."""

import io
import os
import subprocess
import sys
from pathlib import Path

from modue_harness.core.encoding import apply_utf8_env, ensure_utf8_io


class _LegacyStream:
    """Stream without reconfigure(), mimicking a cp949 pipe wrapper."""

    encoding = "cp949"

    def __init__(self) -> None:
        self.buffer = io.BytesIO()


def test_ensure_utf8_io_reconfigures_locale_stream(monkeypatch):
    """A non-UTF-8 stream is replaced by a UTF-8 text layer over its buffer."""
    legacy = _LegacyStream()
    monkeypatch.setattr(sys, "stdout", legacy)

    ensure_utf8_io()

    assert sys.stdout is not legacy
    assert sys.stdout.encoding.lower().replace("_", "-") == "utf-8"
    sys.stdout.write("✓ 한글 출력")
    sys.stdout.flush()
    assert legacy.buffer.getvalue().decode("utf-8") == "✓ 한글 출력"


def test_ensure_utf8_io_leaves_utf8_stream_untouched(monkeypatch):
    """Already-UTF-8 streams (Linux/macOS, pytest capture) are not rewrapped."""
    original = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    monkeypatch.setattr(sys, "stdout", original)

    ensure_utf8_io()

    assert sys.stdout is original


class _PseudoStream:
    """Capture object with no declared encoding (e.g. pytest's stdin)."""

    encoding = None
    buffer = None


def test_ensure_utf8_io_ignores_streams_without_encoding(monkeypatch):
    """Non locale-bound pseudo streams must be left exactly as they are."""
    pseudo = _PseudoStream()
    monkeypatch.setattr(sys, "stdin", pseudo)

    ensure_utf8_io()

    assert sys.stdin is pseudo


def test_ensure_utf8_io_survives_missing_streams(monkeypatch):
    """Detached streams (pythonw, service hosts) must not break startup."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdin", None)

    ensure_utf8_io()  # must not raise


def test_apply_utf8_env_sets_child_encoding():
    """Child CLI processes inherit UTF-8 hints matching our pipe decoding."""
    env = apply_utf8_env({})
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUTF8"] == "1"


def test_apply_utf8_env_preserves_existing_values():
    """An explicit user setting wins over the default."""
    env = apply_utf8_env({"PYTHONIOENCODING": "cp949"})
    assert env["PYTHONIOENCODING"] == "cp949"


def test_cli_prints_non_ascii_through_locale_pipe(tmp_path: Path):
    """End-to-end: `init` succeeds with output piped under a legacy codepage."""
    repo_root = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.pop("PYTHONUTF8", None)
    env.pop("PYTHONIOENCODING", None)
    env["PYTHONPATH"] = str(repo_root / "src")

    result = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-m", "modue_harness.cli",
         "init", "--dir", str(tmp_path / "bb"), "--projects-dir", str(tmp_path / "pj")],
        capture_output=True,
        env=env,
        cwd=str(repo_root),
    )

    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert "UnicodeEncodeError" not in result.stderr.decode("utf-8", "replace")
    assert "✓" in result.stdout.decode("utf-8", "replace")
