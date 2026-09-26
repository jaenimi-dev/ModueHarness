"""OpenRouter agent adapter: an in-harness tool-calling agent over the OpenAI-compatible API.

다른 어댑터는 외부 AI CLI 를 실행하지만, 이 어댑터는 OpenAI SDK 로 OpenRouter
(또는 base_url 을 바꾼 임의의 OpenAI 호환 API)를 직접 호출하고, 파일 읽기/쓰기와
명령 실행은 agent_tools.WorkspaceTools 가 작업 폴더 안에서만 수행한다.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Sequence
import urllib.request

from modue_harness.adapters.agent_tools import TOOL_LEVELS, WorkspaceTools
from modue_harness.adapters.base import BaseCLIAdapter
from modue_harness.core.types import TaskStatus, TurnContext, TurnResult

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_API_KEY_ENV = "OPENROUTER_API_KEY"
DEFAULT_MAX_TURNS = 40

# 대화에 쌓인 도구 결과의 총 길이가 이 값을 넘으면 오래된 결과부터 비운다.
HISTORY_CHAR_BUDGET = 400_000

TOOL_USE_GUIDE = (
    "You are working inside a project workspace. Use the provided tools to inspect and "
    "change files instead of guessing their contents. All paths are relative to the "
    "workspace root. When the task is done, reply with a concise summary of what you did "
    "and do not call any more tools."
)

MAX_EMPTY_REPLIES = 2
EMPTY_REPLY_NUDGE = (
    "Continue the task using the tools. If the task is fully complete, "
    "reply with a concise summary of what you did."
)

DEFAULT_OPENROUTER_MODELS: List[Dict[str, str]] = [
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5 (via OpenRouter)"},
    {"id": "openai/gpt-5", "name": "GPT-5 (via OpenRouter)"},
    {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro (via OpenRouter)"},
    {"id": "qwen/qwen3-coder", "name": "Qwen3 Coder (via OpenRouter)"},
]

_OPENROUTER_MODELS_CACHE: Dict[str, Any] = {
    "timestamp": 0.0,
    "models": [],
}

CACHE_TTL_SECONDS = 300.0


def _read_env_key(key_name: str) -> Optional[str]:
    """Read an API key from the environment, falling back to ./.env and ~/.env."""
    value = os.environ.get(key_name)
    if value:
        return value
    for env_path in [Path.cwd() / ".env", Path.home() / ".env"]:
        if env_path.is_file():
            try:
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith(f"{key_name}="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            return value
            except Exception:
                pass
    return None


def get_available_openrouter_models(force_refresh: bool = False, timeout: float = 3.0) -> List[Dict[str, str]]:
    """Query OpenRouter's public model list, keeping only models that support tool calling."""
    global _OPENROUTER_MODELS_CACHE
    now = time.time()

    if not force_refresh and _OPENROUTER_MODELS_CACHE["models"] and (now - _OPENROUTER_MODELS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
        return list(_OPENROUTER_MODELS_CACHE["models"])

    try:
        req = urllib.request.Request(
            f"{DEFAULT_BASE_URL}/models",
            headers={"User-Agent": "ModueHarness/0.8.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                parsed = [
                    {"id": item["id"], "name": item.get("name", item["id"])}
                    for item in data.get("data", [])
                    if item.get("id") and "tools" in (item.get("supported_parameters") or [])
                ]
                if parsed:
                    _OPENROUTER_MODELS_CACHE["timestamp"] = now
                    _OPENROUTER_MODELS_CACHE["models"] = parsed
                    return list(parsed)
    except Exception:
        pass

    if _OPENROUTER_MODELS_CACHE["models"]:
        return list(_OPENROUTER_MODELS_CACHE["models"])
    return list(DEFAULT_OPENROUTER_MODELS)


def get_openrouter_model_ids(force_refresh: bool = False) -> List[str]:
    """Return list of tool-capable model IDs available on OpenRouter."""
    return [m["id"] for m in get_available_openrouter_models(force_refresh=force_refresh)]


def _require_openai() -> Any:
    try:
        import openai  # type: ignore
    except ImportError:
        raise ImportError(
            "The 'openrouter' adapter requires the OpenAI SDK. "
            "Install it with: pip install 'modue-harness[openrouter]'"
        ) from None
    return openai


class OpenRouterAgentAdapter(BaseCLIAdapter):
    """Tool-calling agent that talks to OpenRouter (or any OpenAI-compatible API) directly."""

    def __init__(
        self,
        name: str = "openrouter",
        command: str = "openrouter",
        default_args: Optional[List[str]] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        system_instruction: Optional[str] = None,
        tools: str = "read",
        max_turns: int = DEFAULT_MAX_TURNS,
        base_url: str = DEFAULT_BASE_URL,
        api_key_env: str = DEFAULT_API_KEY_ENV,
        allowed_commands: Optional[Sequence[str]] = None,
        command_timeout: float = 120.0,
        client: Any = None,
    ) -> None:
        if tools not in TOOL_LEVELS:
            raise ValueError(f"tools must be one of {TOOL_LEVELS}, got {tools!r}")
        if client is None:
            _require_openai()
        if not model:
            raise ValueError("The 'openrouter' adapter requires a model (e.g. 'qwen/qwen3-coder').")

        self.model = model
        self.effort = effort
        self.tools = tools
        self.max_turns = int(max_turns)
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.allowed_commands = list(allowed_commands) if allowed_commands is not None else None
        self.command_timeout = float(command_timeout)
        self._client = client
        self._active_tools: Optional[WorkspaceTools] = None

        # command/default_args 는 CLI 어댑터와 인터페이스를 맞추기 위해서만 받는다 (실행에는 쓰지 않음).
        super().__init__(
            name=name,
            command=command,
            default_args=list(default_args or []),
            system_instruction=system_instruction,
        )

    def set_model(self, model: Optional[str]) -> None:
        """Dynamically update the model used for the next turn."""
        if model:
            self.model = model

    def set_effort(self, effort: Optional[str]) -> None:
        """Dynamically update the reasoning effort passed to OpenRouter."""
        self.effort = effort

    def config_extras(self) -> Dict[str, Any]:
        """Adapter-specific settings to persist back into agents.yaml."""
        extras: Dict[str, Any] = {"tools": self.tools}
        if self.max_turns != DEFAULT_MAX_TURNS:
            extras["max_turns"] = self.max_turns
        if self.base_url != DEFAULT_BASE_URL:
            extras["base_url"] = self.base_url
        if self.api_key_env != DEFAULT_API_KEY_ENV:
            extras["api_key_env"] = self.api_key_env
        if self.allowed_commands is not None:
            extras["allowed_commands"] = self.allowed_commands
        return extras

    # ------------------------------------------------------------------ client
    def _get_client(self) -> Any:
        if self._client is None:
            api_key = _read_env_key(self.api_key_env)
            if not api_key:
                raise RuntimeError(
                    f"API key not found: set {self.api_key_env} in the environment or .env file."
                )
            openai = _require_openai()
            self._client = openai.OpenAI(
                base_url=self.base_url,
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/jaenimi-dev/ModueHarness",
                    "X-Title": "ModueHarness",
                },
            )
        return self._client

    def _request_kwargs(self, messages: List[Dict[str, Any]], tool_specs: List[Dict[str, Any]], remaining: Optional[float]) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages}
        if tool_specs:
            kwargs["tools"] = tool_specs
        if remaining is not None:
            kwargs["timeout"] = max(1.0, remaining)
        extra_body: Dict[str, Any] = {}
        if self.base_url == DEFAULT_BASE_URL:
            # OpenRouter 전용: 응답에 실제 비용(cost)을 포함시킨다.
            extra_body["usage"] = {"include": True}
            eff = str(self.effort or "").strip().lower()
            # default, off, none 이거나 비어있으면 reasoning effort 파라미터를 전송하지 않는다.
            if eff and eff not in ("default", "off", "none"):
                # OpenRouter API는 low, medium, high 를 지원하므로 max/xhigh는 high로 정규화
                mapped_effort = "high" if eff in ("max", "xhigh") else eff
                extra_body["reasoning"] = {"effort": mapped_effort}
        if extra_body:
            kwargs["extra_body"] = extra_body
        return kwargs

    # --------------------------------------------------------------- lifecycle
    def cancel(self) -> None:
        """Stop the agent loop after the current request and kill any running command."""
        self._is_cancelled = True
        tools = self._active_tools
        if tools:
            tools.cancel()

    def execute(
        self,
        context: TurnContext,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> TurnResult:
        """Run the tool-calling loop to completion and return the final answer."""
        gen = self._run_loop(context, timeout)
        while True:
            try:
                next(gen)
            except StopIteration as stop:
                return stop.value

    def execute_stream(
        self,
        context: TurnContext,
        extra_args: Optional[List[str]] = None,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> Generator[str, None, TurnResult]:
        """Run the loop, yielding one progress line per tool call and the final answer."""
        return (yield from self._run_loop(context, None))

    # -------------------------------------------------------------- agent loop
    def _run_loop(self, context: TurnContext, timeout: Optional[float]) -> Generator[str, None, TurnResult]:
        start = time.time()
        self._is_cancelled = False
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "is_estimated": False}
        tool_log: List[Dict[str, Any]] = []
        metadata: Dict[str, Any] = {
            "agent": self.name,
            "command": "openrouter",
            "display_command": f"openrouter:{self.model} (tools={self.tools})",
            "model": self.model,
            "step_id": context.step_id,
            "usage": usage,
            "tool_calls": tool_log,
            "turns": 0,
        }

        def fail(message: str, stdout: str = "", exit_code: int = 1) -> TurnResult:
            return TurnResult(
                status=TaskStatus.FAILED,
                stdout=stdout,
                stderr=message,
                exit_code=exit_code,
                duration_sec=time.time() - start,
                error_message=message,
                metadata=metadata,
            )

        try:
            client = self._get_client()
        except Exception as exc:
            return fail(str(exc))

        tools = WorkspaceTools(
            context.workspace_dir,
            level=self.tools,
            allowed_commands=self.allowed_commands,
            command_timeout=self.command_timeout,
        )
        tool_specs = tools.specs()
        system_parts = [self.system_instruction] if self.system_instruction else []
        if tool_specs:
            system_parts.append(TOOL_USE_GUIDE)
        messages: List[Dict[str, Any]] = []
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.append({"role": "user", "content": self.prepare_prompt(context)})

        self._active_tools = tools
        last_text = ""
        empty_replies = 0
        try:
            for turn in range(1, self.max_turns + 1):
                if self._is_cancelled:
                    return fail("작업이 취소되었습니다 (Execution cancelled by user)", last_text)
                remaining = None if timeout is None else timeout - (time.time() - start)
                if remaining is not None and remaining <= 0:
                    return fail(f"Execution timed out after {timeout} seconds", last_text, exit_code=124)

                metadata["turns"] = turn
                req_kwargs = self._request_kwargs(messages, tool_specs, remaining)
                try:
                    response = client.chat.completions.create(**req_kwargs)
                except Exception as exc:
                    # 모델이 reasoning.effort 파라미터를 지원하지 않아 400 오류가 난 경우 안전하게 제외 후 재시도
                    err_msg = str(exc).lower()
                    if ("reasoning" in err_msg or "effort" in err_msg) and "extra_body" in req_kwargs:
                        extra_body = dict(req_kwargs["extra_body"])
                        if "reasoning" in extra_body:
                            extra_body.pop("reasoning", None)
                            req_kwargs["extra_body"] = extra_body
                            try:
                                response = client.chat.completions.create(**req_kwargs)
                            except Exception as retry_exc:
                                return fail(_describe_api_error(retry_exc), last_text)
                        else:
                            return fail(_describe_api_error(exc), last_text)
                    else:
                        return fail(_describe_api_error(exc), last_text)

                _add_usage(usage, getattr(response, "usage", None))
                choices = getattr(response, "choices", None) or []
                if not choices:
                    return fail(f"OpenRouter returned no choices: {_response_error(response)}", last_text)
                message = choices[0].message
                text = message.content or ""
                if text.strip():
                    last_text = text
                tool_calls = list(getattr(message, "tool_calls", None) or [])

                assistant: Dict[str, Any] = {"role": "assistant", "content": text}
                if tool_calls:
                    assistant["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                        }
                        for tc in tool_calls
                    ]
                messages.append(assistant)

                if not tool_calls:
                    if not text.strip():
                        # 일부 모델은 작업 도중 빈 응답으로 멈춘다. 몇 번 재촉한 뒤에도 비어 있으면 실패로 본다.
                        empty_replies += 1
                        if empty_replies > MAX_EMPTY_REPLIES:
                            return fail("Model returned an empty response without finishing the task.", last_text)
                        messages.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                        continue
                    yield text
                    return TurnResult(
                        status=TaskStatus.COMPLETED,
                        stdout=text,
                        exit_code=0,
                        duration_sec=time.time() - start,
                        metadata=metadata,
                    )

                for tc in tool_calls:
                    if self._is_cancelled:
                        break
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        if not isinstance(args, dict):
                            raise ValueError("arguments must be a JSON object")
                    except ValueError as exc:
                        result = f"Error: could not parse arguments as JSON: {exc}"
                        args = {}
                    else:
                        result = tools.run(name, args)
                    ok = not result.startswith("Error:")
                    summary = _summarize_args(args)
                    tool_log.append({"tool": name, "args": summary, "ok": ok})
                    yield f"🔧 {name}({summary}){'' if ok else ' ✗'}\n"
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                _trim_history(messages)

            return fail(f"Agent stopped after reaching max_turns ({self.max_turns}) without a final answer.", last_text)
        finally:
            self._active_tools = None


def _add_usage(total: Dict[str, Any], usage: Any) -> None:
    if usage is None:
        return
    get = usage.get if isinstance(usage, dict) else lambda k, d=None: getattr(usage, k, d)
    prompt = int(get("prompt_tokens", 0) or 0)
    completion = int(get("completion_tokens", 0) or 0)
    total["input_tokens"] += prompt
    total["output_tokens"] += completion
    total["total_tokens"] += prompt + completion
    cost = get("cost", None)
    if cost is None:
        extra = getattr(usage, "model_extra", None) or {}
        cost = extra.get("cost")
    if cost:
        total["cost_usd"] = round(total["cost_usd"] + float(cost), 6)


def _summarize_args(args: Dict[str, Any], limit: int = 80) -> str:
    parts = []
    for key, val in args.items():
        if key in ("content", "new_string", "old_string"):
            parts.append(f"{key}=<{len(str(val))} chars>")
        else:
            parts.append(f"{key}={val!r}")
    text = ", ".join(parts)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _trim_history(messages: List[Dict[str, Any]]) -> None:
    """Blank out the oldest tool results once the conversation exceeds HISTORY_CHAR_BUDGET."""
    total = sum(len(str(m.get("content") or "")) for m in messages)
    for m in messages:
        if total <= HISTORY_CHAR_BUDGET:
            return
        if m.get("role") == "tool":
            size = len(m["content"])
            if size > 200:
                m["content"] = "[older tool output removed to save context]"
                total -= size - len(m["content"])


def _response_error(response: Any) -> str:
    err = getattr(response, "error", None)
    if err is None:
        err = (getattr(response, "model_extra", None) or {}).get("error")
    return str(err) if err else "empty response"


def _describe_api_error(exc: Exception) -> str:
    """Map SDK exceptions to messages that core/usage.py limit detection understands."""
    status = getattr(exc, "status_code", None)
    detail = getattr(exc, "message", None) or str(exc)
    if status == 429:
        return f"429 Too Many Requests: rate limit reached ({detail})"
    if status == 402:
        return f"OpenRouter API error 402 (insufficient credits): {detail}"
    if status is not None:
        return f"OpenRouter API error {status}: {detail}"
    return f"OpenRouter request failed: {type(exc).__name__}: {detail}"
