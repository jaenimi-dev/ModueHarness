"""Standard stream encoding helpers for cross-platform UTF-8 output.

On Korean Windows the standard streams fall back to the system locale codec
(cp949) whenever they are not attached to a real console: piping the output,
running under Git Bash/MinTTY, or capturing it from another process is enough
to trigger it. ModueHarness prints status glyphs and Korean messages from its
very first line, so that fallback aborts the run with UnicodeEncodeError.
Forcing UTF-8 on the standard streams (and on spawned AI CLI processes) keeps
behaviour identical on every platform without requiring PYTHONUTF8=1.
"""

import io
import os
import sys
from typing import Dict, Optional

UTF8 = "utf-8"

# Environment variables handed to child CLI processes so their output matches
# the encoding="utf-8" decoding already used when reading their pipes.
_CHILD_ENV = {"PYTHONIOENCODING": UTF8, "PYTHONUTF8": "1"}


def _is_utf8(stream: object) -> bool:
    """Return True if the stream already encodes/decodes as UTF-8."""
    encoding = (getattr(stream, "encoding", "") or "").lower().replace("_", "-")
    return encoding in (UTF8, "utf8")


def _has_locale_encoding(stream: object) -> bool:
    """Return True only for real text streams bound to a named codec.

    Streams that report no encoding at all (pytest's pseudo stdin, custom
    capture objects) are not locale-bound and must be left alone.
    """
    return bool(getattr(stream, "encoding", None))


def _reconfigure_stream(stream: object, errors: str) -> Optional[io.TextIOWrapper]:
    """Switch a single text stream to UTF-8, returning a replacement if needed.

    Returns a new wrapper when the stream could not be reconfigured in place
    (the caller then rebinds sys.stdout/stderr/stdin), or None when nothing
    needs to change.
    """
    if stream is None or not _has_locale_encoding(stream) or _is_utf8(stream):
        return None

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding=UTF8, errors=errors)
            return None
        except (ValueError, OSError, AttributeError):
            pass

    # Older or wrapped streams (e.g. custom capture objects): rebuild the text
    # layer on top of the raw buffer when one is exposed.
    buffer = getattr(stream, "buffer", None)
    if not isinstance(buffer, (io.RawIOBase, io.BufferedIOBase)):
        return None
    try:
        return io.TextIOWrapper(
            buffer,
            encoding=UTF8,
            errors=errors,
            line_buffering=True,
        )
    except (ValueError, OSError):
        return None


def ensure_utf8_io() -> None:
    """Force sys.stdout/stderr/stdin to UTF-8. Safe to call more than once."""
    replacement = _reconfigure_stream(sys.stdout, "replace")
    if replacement is not None:
        sys.stdout = replacement

    replacement = _reconfigure_stream(sys.stderr, "replace")
    if replacement is not None:
        sys.stderr = replacement

    replacement = _reconfigure_stream(sys.stdin, "replace")
    if replacement is not None:
        sys.stdin = replacement


def apply_utf8_env(env: Dict[str, str]) -> Dict[str, str]:
    """Add UTF-8 hints to a child process environment, preserving user values."""
    for key, value in _CHILD_ENV.items():
        env.setdefault(key, os.environ.get(key, value))
    return env
