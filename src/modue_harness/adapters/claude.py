"""Claude Code CLI adapter."""

from typing import List, Optional

from modue_harness.adapters.base import BaseCLIAdapter


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

