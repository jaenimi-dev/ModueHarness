"""Base CLI Adapter interface and subprocess runner."""

from abc import ABC, abstractmethod
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from modue_harness.core.types import TaskStatus, TurnContext, TurnResult

# Regex to strip ANSI escape codes (colors, cursor movements, etc.)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from terminal output."""
    return ANSI_ESCAPE_PATTERN.sub("", text)


class BaseCLIAdapter(ABC):
    """Abstract base class for wrapping and executing AI CLI tools."""

    def __init__(
        self,
        name: str,
        command: str,
        default_args: Optional[List[str]] = None,
        prompt_delivery: str = "stdin",  # "stdin", "flag", or "positional"
        prompt_flag: Optional[str] = None,
    ) -> None:
        self.name = name
        self.command = command
        self.default_args = default_args or []
        self.prompt_delivery = prompt_delivery
        self.prompt_flag = prompt_flag

    def build_command(self, prompt: str, extra_args: Optional[List[str]] = None) -> List[str]:
        """Construct the CLI command argument list."""
        cmd = [self.command] + list(self.default_args)
        if extra_args:
            cmd.extend(extra_args)

        if self.prompt_delivery == "flag" and self.prompt_flag:
            cmd.extend([self.prompt_flag, prompt])
        elif self.prompt_delivery == "positional":
            cmd.append(prompt)

        return cmd

    def prepare_prompt(self, context: TurnContext) -> str:
        """Compose the full prompt incorporating instructions and input artifacts."""
        prompt_parts = []

        if context.input_artifacts:
            prompt_parts.append("### Input Artifacts / Context:")
            for artifact_rel_path in context.input_artifacts:
                artifact_file = context.blackboard_dir / "artifacts" / artifact_rel_path.replace("blackboard/artifacts/", "")
                if artifact_file.exists():
                    try:
                        content = artifact_file.read_text(encoding="utf-8")
                        prompt_parts.append(f"--- [Artifact: {artifact_rel_path}] ---\n{content}\n")
                    except Exception as e:
                        prompt_parts.append(f"--- [Artifact: {artifact_rel_path}] (Failed to read: {e}) ---\n")
                else:
                    prompt_parts.append(f"--- [Artifact: {artifact_rel_path}] (File not found) ---\n")

        prompt_parts.append("### Task Instruction:")
        prompt_parts.append(context.instruction)

        return "\n\n".join(prompt_parts)

    def execute(
        self,
        context: TurnContext,
        timeout: Optional[float] = 300.0,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> TurnResult:
        """Execute a single turn using the wrapped CLI tool."""
        full_prompt = self.prepare_prompt(context)
        cmd = self.build_command(full_prompt, extra_args=extra_args)

        env = os.environ.copy()
        if context.env:
            env.update(context.env)
        if custom_env:
            env.update(custom_env)

        stdin_input = full_prompt if self.prompt_delivery == "stdin" else None

        start_time = time.time()
        try:
            process = subprocess.run(
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                cwd=str(context.workspace_dir),
                env=env,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            duration = time.time() - start_time
            stdout_clean = strip_ansi(process.stdout or "")
            stderr_clean = strip_ansi(process.stderr or "")

            status = TaskStatus.COMPLETED if process.returncode == 0 else TaskStatus.FAILED
            error_msg = None if process.returncode == 0 else f"CLI exited with status {process.returncode}"

            return TurnResult(
                status=status,
                stdout=stdout_clean,
                stderr=stderr_clean,
                exit_code=process.returncode,
                duration_sec=duration,
                error_message=error_msg,
            )

        except FileNotFoundError:
            duration = time.time() - start_time
            return TurnResult(
                status=TaskStatus.FAILED,
                exit_code=127,
                duration_sec=duration,
                error_message=f"Command not found: '{self.command}'",
            )
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return TurnResult(
                status=TaskStatus.FAILED,
                exit_code=124,
                duration_sec=duration,
                stdout=strip_ansi(e.stdout or "") if isinstance(e.stdout, str) else "",
                stderr=strip_ansi(e.stderr or "") if isinstance(e.stderr, str) else "",
                error_message=f"Execution timed out after {timeout} seconds",
            )
        except Exception as e:
            duration = time.time() - start_time
            return TurnResult(
                status=TaskStatus.FAILED,
                exit_code=1,
                duration_sec=duration,
                error_message=f"Execution failed with exception: {str(e)}",
            )
