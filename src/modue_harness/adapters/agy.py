"""Antigravity (AGY) CLI adapter."""

import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


DEFAULT_AGY_MODELS: List[Dict[str, str]] = [
    {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)"},
    {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)"},
    {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low)"},
    {"id": "gemini-3.7-flash-high", "name": "Gemini 3.7 Flash (High)"},
    {"id": "gemini-3.1-pro-high", "name": "Gemini 3.1 Pro (High)"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)"},
    {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)"},
    {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B (Medium)"},
]

_AGY_MODELS_CACHE: Dict[str, Any] = {
    "timestamp": 0.0,
    "models": [],
}

CACHE_TTL_SECONDS = 300.0


def get_available_agy_models(force_refresh: bool = False, timeout: float = 3.0) -> List[Dict[str, str]]:
    """Query available models from `agy models` CLI command or return cached/default models."""
    global _AGY_MODELS_CACHE
    now = time.time()

    if not force_refresh and _AGY_MODELS_CACHE["models"] and (now - _AGY_MODELS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return list(_AGY_MODELS_CACHE["models"])

    resolved_bin = resolve_agy_binary("agy")
    try:
        res = subprocess.run(
            [resolved_bin, "models"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if res.returncode == 0 and res.stdout.strip():
            parsed_models: List[Dict[str, str]] = []
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if not line or "Fetching available models" in line:
                    continue
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                if not parts:
                    parts = [p.strip() for p in line.split("  ") if p.strip()]
                if parts:
                    m_id = parts[0]
                    if m_id.lower() in ("model", "id", "name"):
                        continue
                    m_desc = parts[1] if len(parts) > 1 else m_id
                    parsed_models.append({"id": m_id, "name": m_desc})

            if parsed_models:
                _AGY_MODELS_CACHE["timestamp"] = now
                _AGY_MODELS_CACHE["models"] = parsed_models
                return list(parsed_models)
    except Exception:
        pass

    if _AGY_MODELS_CACHE["models"]:
        return list(_AGY_MODELS_CACHE["models"])
    return list(DEFAULT_AGY_MODELS)


def get_agy_model_ids(force_refresh: bool = False) -> List[str]:
    """Return list of model IDs available in Antigravity."""
    return [m["id"] for m in get_available_agy_models(force_refresh=force_refresh)]


def resolve_agy_binary(command: str = "agy") -> str:
    """Resolve full path to the Antigravity CLI binary if available on system."""
    # 1. If explicit executable path passed
    if Path(command).is_file() and os.access(command, os.X_OK):
        return command

    # 2. Check system PATH
    which_p = shutil.which(command)
    if which_p:
        return which_p

    # 3. Check known local installation directories (Linux, macOS, Windows)
    candidate_paths = [
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / ".gemini" / "antigravity-cli" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate_paths.append(Path(local_app_data) / "agy" / "bin" / "agy.exe")
        candidate_paths.append(Path(local_app_data) / "agy" / "bin" / "agy")
    candidate_paths.append(Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.exe")
    candidate_paths.append(Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy")

    for p in candidate_paths:
        if p.is_file():
            return str(p)

    return command


class AGYCLIAdapter(BaseCLIAdapter):
    """Adapter for Google Antigravity CLI (`agy`)."""

    VALID_EFFORT_LEVELS = {"low", "medium", "high"}

    def __init__(
        self,
        name: str = "agy",
        command: str = "agy",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        skip_permissions: bool = True,
        system_instruction: Optional[str] = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.skip_permissions = skip_permissions

        resolved_command = resolve_agy_binary(command)

        args = list(default_args or [])
        if skip_permissions and "--dangerously-skip-permissions" not in args:
            args.append("--dangerously-skip-permissions")
        if model and "--model" not in args:
            args.extend(["--model", str(model)])
        if effort and "--effort" not in args:
            args.extend(["--effort", str(effort)])

        super().__init__(
            name=name,
            command=resolved_command,
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
