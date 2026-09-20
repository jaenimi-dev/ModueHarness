import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import urllib.request

from modue_harness.adapters.base import BaseCLIAdapter


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
        system_instruction: Optional[str] = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.permission_mode = permission_mode

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

