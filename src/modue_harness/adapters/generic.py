"""Generic CLI Adapter for executing any command-line AI tool or script."""

from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


class GenericCLIAdapter(BaseCLIAdapter):
    """General-purpose CLI adapter configurable for arbitrary shell commands."""

    def __init__(
        self,
        name: str = "generic",
        command: str = "echo",
        default_args: Optional[List[str]] = None,
        prompt_delivery: str = "stdin",
        prompt_flag: Optional[str] = None,
    ) -> None:
        super().__init__(
            name=name,
            command=command,
            default_args=default_args,
            prompt_delivery=prompt_delivery,
            prompt_flag=prompt_flag,
        )
