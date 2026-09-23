"""Workspace-scoped tools for API-driven agent adapters (OpenAI-compatible tool calling).

CLI 어댑터는 파일 편집과 명령 실행을 외부 CLI 에 맡기지만, API 로 모델을 직접
호출하는 어댑터는 하네스가 그 도구들을 직접 제공해야 한다. 이 모듈은 도구 정의
(JSON 스키마)와 실행기를 담고, 모든 경로를 작업 폴더 안으로 가둔다.
"""

import os
import re
import shlex
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from modue_harness.core.encoding import apply_utf8_env

TOOL_LEVELS = ("none", "read", "full")

# 모델에 돌려주는 도구 결과의 최대 길이. 긴 출력이 대화 컨텍스트를 잠식하지 않게 자른다.
MAX_OUTPUT_CHARS = 20000
MAX_READ_BYTES = 2 * 1024 * 1024
MAX_LIST_ENTRIES = 500
MAX_SEARCH_RESULTS = 100
SKIP_DIRS = frozenset({".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"})

# run_command 는 허용 목록 방식이다. 명령을 토큰으로 나눈 뒤 아래 접두어 중 하나로
# 시작해야만 실행한다. 임의 코드를 실행할 수 있는 `python` 단독 실행은 기본에서 뺐다.
# 필요하면 agents.yaml 의 allowed_commands 로 추가한다.
DEFAULT_ALLOWED_COMMANDS: List[str] = [
    "pytest",
    "python -m pytest",
    "python3 -m pytest",
    "python -m unittest",
    "python3 -m unittest",
    "python -m py_compile",
    "python3 -m py_compile",
    "git status",
    "git diff",
    "git log",
    "git show",
    "ls",
    "pwd",
]


class ToolError(Exception):
    """A tool call that was rejected or failed; the message is returned to the model."""


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... ({len(text) - limit} chars truncated)"


def _schema(name: str, description: str, properties: Dict[str, Any], required: Sequence[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(required),
            },
        },
    }


_PATH = {"type": "string", "description": "Path relative to the workspace root."}

READ_TOOL_SPECS: List[Dict[str, Any]] = [
    _schema(
        "list_dir",
        "List files and directories under a workspace path.",
        {
            "path": {**_PATH, "default": "."},
            "depth": {"type": "integer", "description": "Recursion depth (1-4).", "default": 1},
        },
        [],
    ),
    _schema(
        "read_file",
        "Read a UTF-8 text file. Lines are 1-indexed; omit start/end to read the whole file.",
        {
            "path": _PATH,
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
        },
        ["path"],
    ),
    _schema(
        "search",
        "Search file contents with a Python regular expression. Returns path:line: text matches.",
        {
            "pattern": {"type": "string"},
            "path": {**_PATH, "default": "."},
        },
        ["pattern"],
    ),
]

WRITE_TOOL_SPECS: List[Dict[str, Any]] = [
    _schema(
        "write_file",
        "Create a file or overwrite it entirely with the given content.",
        {"path": _PATH, "content": {"type": "string"}},
        ["path", "content"],
    ),
    _schema(
        "edit_file",
        "Replace one exact occurrence of old_string with new_string. old_string must match exactly once.",
        {
            "path": _PATH,
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        ["path", "old_string", "new_string"],
    ),
]

RUN_COMMAND_SPEC: Dict[str, Any] = _schema(
    "run_command",
    "Run an allow-listed command in the workspace root (no shell: pipes, redirects and && are not supported).",
    {"command": {"type": "string"}},
    ["command"],
)


def _parse_allowed(entries: Sequence[str]) -> List[List[str]]:
    parsed = []
    for entry in entries:
        tokens = shlex.split(entry) if isinstance(entry, str) else list(entry)
        if tokens:
            parsed.append(tokens)
    return parsed


class WorkspaceTools:
    """Executes tool calls against a single workspace directory."""

    def __init__(
        self,
        workspace_dir: Path,
        level: str = "read",
        allowed_commands: Optional[Sequence[str]] = None,
        command_timeout: float = 120.0,
    ) -> None:
        if level not in TOOL_LEVELS:
            raise ValueError(f"tools must be one of {TOOL_LEVELS}, got {level!r}")
        self.root = Path(workspace_dir).resolve()
        self.level = level
        self.allowed_commands = _parse_allowed(
            DEFAULT_ALLOWED_COMMANDS if allowed_commands is None else allowed_commands
        )
        self.command_timeout = command_timeout
        self._current_process: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------ specs
    def specs(self) -> List[Dict[str, Any]]:
        """Tool definitions exposed to the model for the configured level."""
        if self.level == "none":
            return []
        specs = list(READ_TOOL_SPECS)
        if self.level == "full":
            specs.extend(WRITE_TOOL_SPECS)
            if self.allowed_commands:
                allowed = ", ".join(" ".join(t) for t in self.allowed_commands)
                spec = {**RUN_COMMAND_SPEC, "function": dict(RUN_COMMAND_SPEC["function"])}
                spec["function"]["description"] += f" Allowed command prefixes: {allowed}."
                specs.append(spec)
        return specs

    def tool_names(self) -> List[str]:
        return [s["function"]["name"] for s in self.specs()]

    # ---------------------------------------------------------------- dispatch
    def run(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool call. Rejections and failures become an error string for the model."""
        if name not in self.tool_names():
            return f"Error: tool '{name}' is not available (tools level: {self.level})."
        handler = getattr(self, f"_tool_{name}")
        try:
            return _truncate(handler(**args))
        except ToolError as exc:
            return f"Error: {exc}"
        except TypeError as exc:
            return f"Error: invalid arguments for {name}: {exc}"
        except Exception as exc:  # 도구 실패는 루프를 멈추지 않고 모델이 고칠 수 있게 돌려준다.
            return f"Error: {name} failed: {type(exc).__name__}: {exc}"

    def cancel(self) -> None:
        """Kill a running run_command process group."""
        _kill_process(self._current_process)

    # ------------------------------------------------------------ path safety
    def resolve(self, path: str, for_write: bool = False) -> Path:
        """Resolve a path and reject anything that escapes the workspace root."""
        if not isinstance(path, str):
            raise ToolError("path must be a string")
        # 모델이 작업 폴더 루트를 빈 문자열로 가리키는 경우가 많아 "." 으로 취급한다.
        target = (self.root / (path.strip() or ".")).resolve()
        try:
            rel = target.relative_to(self.root)
        except ValueError:
            raise ToolError(f"path '{path}' is outside the workspace") from None
        if for_write and rel.parts and rel.parts[0] == ".git":
            raise ToolError("writing inside .git is not allowed")
        return target

    def _display(self, path: Path) -> str:
        rel = path.relative_to(self.root).as_posix()
        return rel or "."

    # ------------------------------------------------------------ read tools
    def _tool_list_dir(self, path: str = ".", depth: int = 1) -> str:
        base = self.resolve(path)
        if not base.is_dir():
            raise ToolError(f"'{path}' is not a directory")
        depth = max(1, min(int(depth), 4))
        lines: List[str] = []

        def walk(d: Path, level: int) -> None:
            for entry in sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if len(lines) >= MAX_LIST_ENTRIES:
                    return
                if entry.is_dir() and not entry.is_symlink():
                    lines.append(self._display(entry) + "/")
                    if level < depth and entry.name not in SKIP_DIRS:
                        walk(entry, level + 1)
                else:
                    lines.append(self._display(entry))

        walk(base, 1)
        if len(lines) >= MAX_LIST_ENTRIES:
            lines.append(f"... (stopped at {MAX_LIST_ENTRIES} entries)")
        return "\n".join(lines) or "(empty directory)"

    def _tool_read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError(f"'{path}' is not a file")
        if target.stat().st_size > MAX_READ_BYTES:
            raise ToolError(f"'{path}' is larger than {MAX_READ_BYTES} bytes; use search or a line range")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line or 1))
        end = min(len(lines), int(end_line or len(lines)))
        numbered = [f"{i}\t{lines[i - 1]}" for i in range(start, end + 1)]
        return "\n".join(numbered) if numbered else "(no lines in range)"

    def _tool_search(self, pattern: str, path: str = ".") -> str:
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from None
        base = self.resolve(path)
        files = [base] if base.is_file() else self._iter_files(base)
        results: List[str] = []
        for f in files:
            try:
                if f.stat().st_size > MAX_READ_BYTES:
                    continue
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    results.append(f"{self._display(f)}:{lineno}: {line.strip()[:300]}")
                    if len(results) >= MAX_SEARCH_RESULTS:
                        results.append(f"... (stopped at {MAX_SEARCH_RESULTS} matches)")
                        return "\n".join(results)
        return "\n".join(results) or "No matches."

    def _iter_files(self, base: Path):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fn in sorted(filenames):
                p = Path(dirpath) / fn
                # 심볼릭 링크가 작업 폴더 밖을 가리키면 건너뛴다.
                try:
                    p.resolve().relative_to(self.root)
                except ValueError:
                    continue
                yield p

    # ----------------------------------------------------------- write tools
    def _tool_write_file(self, path: str, content: str) -> str:
        target = self.resolve(path, for_write=True)
        if target.is_dir():
            raise ToolError(f"'{path}' is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {self._display(target)}"

    def _tool_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        target = self.resolve(path, for_write=True)
        if not target.is_file():
            raise ToolError(f"'{path}' is not a file")
        if not old_string:
            raise ToolError("old_string must not be empty")
        text = target.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            raise ToolError("old_string not found")
        if count > 1:
            raise ToolError(f"old_string matches {count} places; include more surrounding context")
        target.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
        return f"Edited {self._display(target)}"

    def _tool_run_command(self, command: str) -> str:
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise ToolError(f"cannot parse command: {exc}") from None
        if not tokens:
            raise ToolError("empty command")
        if not any(tokens[: len(p)] == p for p in self.allowed_commands):
            allowed = ", ".join(" ".join(t) for t in self.allowed_commands)
            raise ToolError(f"command not in allow list. Allowed prefixes: {allowed}")
        for tok in tokens[1:]:
            self._check_arg(tok)

        env = os.environ.copy()
        apply_utf8_env(env)
        kwargs: Dict[str, Any] = {}
        if sys.platform != "win32":
            kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(
                tokens,
                cwd=str(self.root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                **kwargs,
            )
        except FileNotFoundError:
            raise ToolError(f"command not found: {tokens[0]}") from None
        self._current_process = proc
        try:
            out, _ = proc.communicate(timeout=self.command_timeout)
        except subprocess.TimeoutExpired:
            _kill_process(proc)
            out, _ = proc.communicate()
            return _truncate(f"[timed out after {self.command_timeout}s]\n{out or ''}")
        finally:
            self._current_process = None
        return f"[exit code {proc.returncode}]\n{out or ''}"

    def _check_arg(self, token: str) -> None:
        """Reject arguments that point outside the workspace (absolute paths, `..`, `--opt=/path`)."""
        value = token.split("=", 1)[1] if token.startswith("-") and "=" in token else token
        if not value or value.startswith("-"):
            return
        looks_like_path = os.path.isabs(value) or value.startswith("~") or ".." in Path(value).parts
        if looks_like_path:
            target = Path(os.path.expanduser(value))
            target = (target if target.is_absolute() else self.root / target).resolve()
            try:
                target.relative_to(self.root)
            except ValueError:
                raise ToolError(f"argument '{token}' points outside the workspace") from None


def _kill_process(proc: Optional[subprocess.Popen]) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        if sys.platform != "win32":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
