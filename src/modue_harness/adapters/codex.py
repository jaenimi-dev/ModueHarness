"""OpenAI ChatGPT Codex CLI adapter."""

import os
from pathlib import Path
import shutil
from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


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
