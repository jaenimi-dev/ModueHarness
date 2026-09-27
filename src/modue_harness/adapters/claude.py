import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, Generator, List, Optional, Tuple
import urllib.request

from modue_harness.adapters import agy_guard as _guard
from modue_harness.adapters.base import BaseCLIAdapter
from modue_harness.core.types import TurnContext, TurnResult


DEFAULT_CLAUDE_MODELS: List[Dict[str, str]] = [
    {"id": "sonnet", "name": "Claude Sonnet (Latest / 기본 권장)"},
    {"id": "opus", "name": "Claude Opus (심층 사고 / 설계)"},
    {"id": "haiku", "name": "Claude Haiku (경량 / 고속)"},
    {"id": "claude-3-7-sonnet-latest", "name": "Claude 3.7 Sonnet (Latest)"},
    {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet (Latest)"},
    {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku (Latest)"},
]

_CLAUDE_MODELS_CACHE: Dict[str, Any] = {
    "timestamp": 0.0,
    "models": [],
}

CACHE_TTL_SECONDS = 300.0


def get_available_claude_models(force_refresh: bool = False, timeout: float = 3.0) -> List[Dict[str, str]]:
    """Query available Claude models via Anthropic API (if key available) or return cached/default models."""
    global _CLAUDE_MODELS_CACHE
    now = time.time()

    if not force_refresh and _CLAUDE_MODELS_CACHE["models"] and (now - _CLAUDE_MODELS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return list(_CLAUDE_MODELS_CACHE["models"])

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        for env_path in [Path.cwd() / ".env", Path.home() / ".env"]:
            if env_path.is_file():
                try:
                    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if line.startswith("ANTHROPIC_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                except Exception:
                    pass
            if api_key:
                break

    if api_key:
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "User-Agent": "ModueHarness/0.8.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_models = data.get("data", [])
                    parsed = [
                        {"id": "sonnet", "name": "Claude Sonnet (Latest / 권장)"},
                        {"id": "opus", "name": "Claude Opus (심층 사고)"},
                        {"id": "haiku", "name": "Claude Haiku (초고속)"},
                    ]
                    existing_ids = {"sonnet", "opus", "haiku"}
                    for item in raw_models:
                        m_id = item.get("id")
                        d_name = item.get("display_name", m_id)
                        if m_id and m_id not in existing_ids:
                            existing_ids.add(m_id)
                            parsed.append({"id": m_id, "name": d_name})

                    if len(parsed) > 3:
                        _CLAUDE_MODELS_CACHE["timestamp"] = now
                        _CLAUDE_MODELS_CACHE["models"] = parsed
                        return list(parsed)
        except Exception:
            pass

    if _CLAUDE_MODELS_CACHE["models"]:
        return list(_CLAUDE_MODELS_CACHE["models"])
    return list(DEFAULT_CLAUDE_MODELS)


def get_claude_model_ids(force_refresh: bool = False) -> List[str]:
    """Return list of model IDs available for Claude Code."""
    return [m["id"] for m in get_available_claude_models(force_refresh=force_refresh)]


class ClaudeCLIAdapter(BaseCLIAdapter):
    """Adapter for Anthropic's Claude Code CLI (`claude`)."""

    VALID_EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}

    def __init__(
        self,
        name: str = "claude",
        command: str = "claude",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        permission_mode: str = "auto",
        write_guard: bool = True,
        system_instruction: Optional[str] = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.permission_mode = permission_mode
        # 실행마다 --settings 로 하네스 저장소·민감 경로에 대한 Edit deny 규칙을 주입한다.
        self.write_guard = bool(write_guard)

        args = list(default_args or [])
        if permission_mode and "--permission-mode" not in args:
            args.extend(["--permission-mode", permission_mode])
        if model and "--model" not in args:
            args.extend(["--model", model])
        if effort and "--effort" not in args:
            args.extend(["--effort", str(effort)])

        super().__init__(
            name=name,
            command=command,
            default_args=args,
            prompt_delivery="flag",
            prompt_flag="-p",
            system_instruction=system_instruction,
        )

    def set_model(self, model: Optional[str]) -> None:
        """Dynamically update model and rebuild CLI args."""
        self.model = model
        self.default_args = self._update_arg_pair(self.default_args, "--model", model)

    def set_effort(self, effort: Optional[str]) -> None:
        """Dynamically update reasoning effort level and rebuild CLI args."""
        self.effort = effort
        self.default_args = self._update_arg_pair(self.default_args, "--effort", effort)

    def config_extras(self) -> Dict[str, Any]:
        """Adapter-specific settings to persist back into agents.yaml."""
        return {} if self.write_guard else {"write_guard": False}

    def _guard_settings(self, context: TurnContext, extra_args: Optional[List[str]]) -> Tuple[List[str], Optional[Path]]:
        """Build `--settings <tmpfile>` carrying Edit deny rules. Returns (extra_args, tmpfile to delete).

        --settings 는 사용자의 전역 설정을 건드리지 않고 이번 실행에만 규칙을 더한다.
        파일 도구(Write/Edit)만 확실히 막힌다. Bash 는 Claude Code 샌드박스(bubblewrap)가 있어야
        OS 수준으로 막을 수 있어 여기서는 다루지 않는다.
        """
        args = list(extra_args or [])
        if (
            not self.write_guard
            or sys.platform == "win32"  # 윈도우 경로의 절대 경로 규칙 표기는 검증되지 않았다.
            or "--settings" in self.default_args
            or "--settings" in args
            or not _guard.is_safe_guard_root(Path.cwd(), context.workspace_dir)
        ):
            return args, None
        rules = _guard.build_claude_deny_rules(
            Path.cwd(), allowed_dirs=[context.workspace_dir, context.blackboard_dir]
        )
        fd, name = tempfile.mkstemp(prefix="modue-claude-guard-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"permissions": {"deny": rules}}, fh)
        return args + ["--settings", name], Path(name)

    def execute(
        self,
        context: TurnContext,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> TurnResult:
        """Run claude with per-run deny rules that block file-tool writes into the harness repo."""
        args, settings_file = self._guard_settings(context, extra_args)
        try:
            return super().execute(context, extra_args=args, custom_env=custom_env, timeout=timeout)
        finally:
            if settings_file:
                settings_file.unlink(missing_ok=True)

    def execute_stream(
        self,
        context: TurnContext,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> Generator[str, None, TurnResult]:
        """Stream claude output with the same per-run deny rules as execute()."""
        args, settings_file = self._guard_settings(context, extra_args)
        try:
            return (yield from super().execute_stream(context, extra_args=args, custom_env=custom_env))
        finally:
            if settings_file:
                settings_file.unlink(missing_ok=True)

    @staticmethod
    def _update_arg_pair(args: List[str], flag: str, val: Optional[str]) -> List[str]:
        new_args = []
        i = 0
        while i < len(args):
            if args[i] == flag:
                i += 2  # skip flag and its parameter value
            else:
                new_args.append(args[i])
                i += 1
        if val is not None and str(val).strip():
            new_args.extend([flag, str(val).strip()])
        return new_args

