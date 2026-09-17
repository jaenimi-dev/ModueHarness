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
    ) -> None:
        args = list(default_args or [])
        super().__init__(
            name=name,
            command=command,
            default_args=args,
            prompt_delivery="stdin",
        )
