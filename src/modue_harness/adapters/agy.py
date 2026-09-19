"""Antigravity (AGY) CLI adapter."""

import os
from pathlib import Path
import shutil
from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


def resolve_agy_binary(command: str = "agy") -> str:
    """Resolve full path to the Antigravity CLI binary if available on system."""
    # 1. If explicit executable path passed
    if Path(command).is_file() and os.access(command, os.X_OK):
        return command

    # 2. Check system PATH
    which_p = shutil.which(command)
    if which_p:
        return which_p

    # 3. Check known local installation directories
    candidate_paths = [
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / ".gemini" / "antigravity-cli" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]
    for p in candidate_paths:
        if p.is_file() and os.access(p, os.X_OK):
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
