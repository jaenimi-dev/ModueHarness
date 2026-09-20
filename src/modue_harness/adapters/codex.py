import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional
import urllib.request

from modue_harness.adapters.base import BaseCLIAdapter


DEFAULT_CODEX_MODELS: List[Dict[str, str]] = [
    {"id": "gpt-5.6-terra", "name": "GPT-5.6 Terra (Thinking / 추천)"},
    {"id": "gpt-5.6-luna", "name": "GPT-5.6 Luna"},
    {"id": "gpt-5.5", "name": "GPT-5.5 (Fast)"},
    {"id": "o3-mini", "name": "OpenAI o3-mini (Reasoning)"},
    {"id": "gpt-4o", "name": "GPT-4o (Omni)"},
]

_CODEX_MODELS_CACHE: Dict[str, Any] = {
    "timestamp": 0.0,
    "models": [],
}

CACHE_TTL_SECONDS = 300.0


def _read_local_codex_config() -> Optional[str]:
    """Read configured default model from ~/.codex/config.toml if present."""
    config_paths = [
        Path.home() / ".codex" / "config.toml",
    ]
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        config_paths.insert(0, Path(codex_home) / "config.toml")

    for p in config_paths:
        if p.is_file():
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    clean = line.strip()
                    if clean.startswith("model") and "=" in clean:
                        val = clean.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return None


def get_available_codex_models(force_refresh: bool = False, timeout: float = 3.0) -> List[Dict[str, str]]:
    """Query available Codex models from config/API or return default models."""
    global _CODEX_MODELS_CACHE
    now = time.time()

    if not force_refresh and _CODEX_MODELS_CACHE["models"] and (now - _CODEX_MODELS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return list(_CODEX_MODELS_CACHE["models"])

    models: List[Dict[str, str]] = list(DEFAULT_CODEX_MODELS)
    seen_ids = {m["id"] for m in models}

    # 1. Check local config.toml
    local_cfg_model = _read_local_codex_config()
    if local_cfg_model and local_cfg_model not in seen_ids:
        models.insert(0, {"id": local_cfg_model, "name": f"{local_cfg_model} (로컬 config.toml)"})
        seen_ids.add(local_cfg_model)

    # 2. Check OpenAI API if OPENAI_API_KEY is available
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        for env_path in [Path.cwd() / ".env", Path.home() / ".env"]:
            if env_path.is_file():
                try:
                    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                except Exception:
                    pass
            if api_key:
                break

    if api_key:
        try:
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "ModueHarness/0.8.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    raw_models = data.get("data", [])
                    for item in raw_models:
                        m_id = item.get("id", "")
                        if any(m_id.startswith(p) for p in ("gpt-5", "o3", "o4", "o1", "gpt-4o")):
                            if m_id not in seen_ids:
                                seen_ids.add(m_id)
                                models.append({"id": m_id, "name": m_id})
        except Exception:
            pass

    _CODEX_MODELS_CACHE["timestamp"] = now
    _CODEX_MODELS_CACHE["models"] = models
    return list(models)


def get_codex_model_ids(force_refresh: bool = False) -> List[str]:
    """Return list of model IDs available for Codex."""
    return [m["id"] for m in get_available_codex_models(force_refresh=force_refresh)]


def resolve_codex_binary(command: str = "codex") -> str:
    """Resolve full path to the Codex CLI binary if available on system."""
    # 1. If explicit executable path passed
    if Path(command).is_file() and os.access(command, os.X_OK):
        return command

    # 2. Check system PATH
    which_p = shutil.which(command)
    if which_p:
        return which_p

    # 3. Check known local installation directories (Linux, macOS, Windows)
    candidate_paths = [
        Path.home() / ".local" / "bin" / "codex",
        Path.home() / ".codex" / "bin" / "codex",
        Path("/usr/local/bin/codex"),
        Path("/usr/bin/codex"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate_paths.append(Path(local_app_data) / "codex" / "bin" / "codex.exe")
        candidate_paths.append(Path(local_app_data) / "codex" / "bin" / "codex")
    candidate_paths.append(Path.home() / "AppData" / "Local" / "codex" / "bin" / "codex.exe")
    candidate_paths.append(Path.home() / "AppData" / "Local" / "codex" / "bin" / "codex")

    for p in candidate_paths:
        if p.is_file():
            return str(p)

    return command


class CodexCLIAdapter(BaseCLIAdapter):
    """Adapter for OpenAI ChatGPT Codex CLI (`codex`)."""

    VALID_EFFORT_LEVELS = {"low", "medium", "high"}

    def __init__(
        self,
        name: str = "codex",
        command: str = "codex",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        sandbox: str = "workspace-write",
        system_instruction: Optional[str] = None,
    ) -> None:
        self.model = model
        self.effort = effort
        self.sandbox = sandbox

        resolved_cmd = resolve_codex_binary(command)

        args = list(default_args or [])
        # Ensure 'exec' subcommand is present for non-interactive execution
        if "exec" not in args:
            args.insert(0, "exec")

        if sandbox and "--sandbox" not in args:
            exec_idx = args.index("exec")
            args[exec_idx + 1:exec_idx + 1] = ["--sandbox", sandbox]

        if model and "-m" not in args and "--model" not in args:
            args.extend(["-m", model])

        super().__init__(
            name=name,
            command=resolved_cmd,
            default_args=args,
            prompt_delivery="positional",
            system_instruction=system_instruction,
        )

    def set_model(self, model: Optional[str]) -> None:
        """Dynamically update model and rebuild CLI args."""
        self.model = model
        new_args = list(self.default_args)
        if "-m" in new_args:
            new_args = self._update_arg_pair(new_args, "-m", model)
        elif "--model" in new_args:
            new_args = self._update_arg_pair(new_args, "--model", model)
        elif model:
            new_args.extend(["-m", model])
        self.default_args = new_args

    def set_effort(self, effort: Optional[str]) -> None:
        """Dynamically update reasoning effort level."""
        self.effort = effort

    @staticmethod
    def _update_arg_pair(args: List[str], flag: str, val: Optional[str]) -> List[str]:
        new_args = []
        i = 0
        while i < len(args):
            if args[i] == flag:
                i += 2
            else:
                new_args.append(args[i])
                i += 1
        if val:
            new_args.extend([flag, val])
        return new_args
