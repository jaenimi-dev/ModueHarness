"""Antigravity (AGY) CLI adapter."""

from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


class AGYCLIAdapter(BaseCLIAdapter):
    """Adapter for Google Antigravity CLI (`agy`)."""

    def __init__(
        self,
        name: str = "agy",
        command: str = "agy",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
    ) -> None:
        args = list(default_args or [])
        if model:
            args.extend(["--model", model])

        super().__init__(
            name=name,
            command=command,
            default_args=args,
            prompt_delivery="stdin",
            system_instruction=system_instruction,
        )
