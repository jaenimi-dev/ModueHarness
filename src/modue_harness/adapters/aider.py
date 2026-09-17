"""Aider CLI adapter."""

from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


class AiderCLIAdapter(BaseCLIAdapter):
    """Adapter for Aider AI coding assistant CLI (`aider`)."""

    def __init__(
        self,
        name: str = "aider",
        command: str = "aider",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        yes_always: bool = True,
        no_git: bool = False,
        system_instruction: Optional[str] = None,
    ) -> None:
        args = list(default_args or [])
        if yes_always and "--yes-always" not in args:
            args.append("--yes-always")
        if no_git and "--no-git" not in args:
            args.append("--no-git")
        if model and "--model" not in args:
            args.extend(["--model", model])

        super().__init__(
            name=name,
            command=command,
            default_args=args,
            prompt_delivery="flag",
            prompt_flag="--message",
            system_instruction=system_instruction,
        )
