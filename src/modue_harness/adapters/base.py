"""Base CLI Adapter interface, subprocess runner, and stream execution."""

from abc import ABC
import os
import re
import shlex
import subprocess
import time
from typing import Any, Dict, Generator, List, Optional

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
        system_instruction: Optional[str] = None,
    ) -> None:
        self.name = name
        self.command = command
        self.default_args = default_args or []
        self.prompt_delivery = prompt_delivery
        self.prompt_flag = prompt_flag
        self.system_instruction = system_instruction

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

    def format_command_display(self, cmd: List[str], max_prompt_len: Optional[int] = 100) -> str:
        """Format a CLI command argument list for display, optionally truncating long prompt argument."""
        display_parts = []
        for i, part in enumerate(cmd):
            if (
                max_prompt_len
                and len(part) > max_prompt_len
                and ((i > 0 and cmd[i - 1] in ["-p", "--prompt", "-c"]) or "\n" in part)
            ):
                first_line = part.strip().splitlines()[0] if part.strip().splitlines() else part.strip()
                if len(first_line) > max_prompt_len:
                    preview = first_line[:max_prompt_len] + "..."
                else:
                    preview = first_line + ("..." if len(part.strip().splitlines()) > 1 else "")
                display_parts.append(preview)
            else:
                display_parts.append(part)
        try:
            return shlex.join(display_parts)
        except Exception:
            return " ".join(display_parts)

    def prepare_prompt(self, context: TurnContext) -> str:
        """Compose the full prompt incorporating instructions and input artifacts."""
        prompt_parts = []

        if self.system_instruction:
            prompt_parts.append(f"### System / Role Directive:\n{self.system_instruction}\n")

        if context.input_artifacts:
            prompt_parts.append("### Input Artifacts / Context:")
            for artifact_rel_path in context.input_artifacts:
                clean_rel = artifact_rel_path.replace("blackboard/artifacts/", "")
                artifact_file = context.blackboard_dir / "artifacts" / clean_rel
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
        cmd_display = self.format_command_display(cmd, max_prompt_len=100)
        try:
            full_cmd_str = shlex.join(cmd)
        except Exception:
            full_cmd_str = " ".join(cmd)
        cmd_metadata = {
            "command": cmd,
            "command_display": cmd_display,
            "full_command_str": full_cmd_str,
        }

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
                metadata=cmd_metadata,
            )

        except FileNotFoundError:
            duration = time.time() - start_time
            return TurnResult(
                status=TaskStatus.FAILED,
                exit_code=127,
                duration_sec=duration,
                error_message=f"Command not found: '{self.command}'",
                metadata=cmd_metadata,
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
                metadata=cmd_metadata,
            )
        except Exception as e:
            duration = time.time() - start_time
            return TurnResult(
                status=TaskStatus.FAILED,
                exit_code=1,
                duration_sec=duration,
                error_message=f"Execution failed with exception: {str(e)}",
                metadata=cmd_metadata,
            )

    def execute_stream(
        self,
        context: TurnContext,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> Generator[str, None, TurnResult]:
        """Execute the CLI process and yield lines from stdout in real time."""
        full_prompt = self.prepare_prompt(context)
        cmd = self.build_command(full_prompt, extra_args=extra_args)

        env = os.environ.copy()
        if context.env:
            env.update(context.env)
        if custom_env:
            env.update(custom_env)

        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if self.prompt_delivery == "stdin" else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(context.workspace_dir),
            env=env,
            encoding="utf-8",
            errors="replace",
        )

        if self.prompt_delivery == "stdin" and process.stdin:
            try:
                process.stdin.write(full_prompt)
                process.stdin.flush()
                process.stdin.close()
            except Exception:
                pass

        accumulated_stdout: List[str] = []
        if process.stdout:
            for line in process.stdout:
                clean_line = strip_ansi(line)
                accumulated_stdout.append(clean_line)
                yield clean_line

        process.wait()
        stderr_text = process.stderr.read() if process.stderr else ""
        duration = time.time() - start_time

        stdout_all = "".join(accumulated_stdout)
        stderr_clean = strip_ansi(stderr_text or "")
        status = TaskStatus.COMPLETED if process.returncode == 0 else TaskStatus.FAILED

        return TurnResult(
            status=status,
            stdout=stdout_all,
            stderr=stderr_clean,
            exit_code=process.returncode or 0,
            duration_sec=duration,
            error_message=None if process.returncode == 0 else f"Process exited with {process.returncode}",
        )
