"""Claude Code CLI adapter."""

from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


class ClaudeCLIAdapter(BaseCLIAdapter):
    """Adapter for Anthropic's Claude Code CLI (`claude`)."""

    def __init__(
        self,
        name: str = "claude",
        command: str = "claude",
        default_args: Optional[List[str]] = None,
        permission_mode: str = "auto",
    ) -> None:
        args = list(default_args or [])
        if permission_mode:
            args.extend(["--permission-mode", permission_mode])

        # Claude Code supports non-interactive execution via -p
        super().__init__(
            name=name,
            command=command,
            default_args=args,
            prompt_delivery="flag",
            prompt_flag="-p",
        )
