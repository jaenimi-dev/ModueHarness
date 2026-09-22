"""Adapter package exposing adapters and factory."""

import inspect
from typing import Any, Dict, Type

from modue_harness.adapters.agy import (
    AGYCLIAdapter,
    get_agy_model_ids,
    get_available_agy_models,
)
from modue_harness.adapters.aider import AiderCLIAdapter
from modue_harness.adapters.base import BaseCLIAdapter, strip_ansi
from modue_harness.adapters.claude import (
    ClaudeCLIAdapter,
    get_available_claude_models,
    get_claude_model_ids,
)
from modue_harness.adapters.codex import (
    CodexCLIAdapter,
    get_available_codex_models,
    get_codex_model_ids,
)
from modue_harness.adapters.generic import GenericCLIAdapter

ADAPTER_REGISTRY: Dict[str, Type[BaseCLIAdapter]] = {
    "generic": GenericCLIAdapter,
    "claude": ClaudeCLIAdapter,
    "claude-code": ClaudeCLIAdapter,
    "agy": AGYCLIAdapter,
    "antigravity": AGYCLIAdapter,
    "aider": AiderCLIAdapter,
    "codex": CodexCLIAdapter,
    "chatgpt": CodexCLIAdapter,
}


# 특정 어댑터만 받는 선택적 설정. 지원하지 않는 어댑터에 넘어오면 조용히 버린다.
_OPTIONAL_ADAPTER_KWARGS = frozenset({"permission_mode", "skip_permissions", "model", "effort"})


def create_adapter(adapter_type: str, **kwargs: Any) -> BaseCLIAdapter:
    """Instantiate an adapter from registered types or fallback to generic."""
    adapter_cls = ADAPTER_REGISTRY.get(adapter_type.lower(), GenericCLIAdapter)
    if adapter_cls is GenericCLIAdapter:
        kwargs.setdefault("name", adapter_type)
        kwargs.setdefault("command", adapter_type)

    # agents.yaml 은 어댑터 종류를 가리지 않고 같은 키를 쓸 수 있으므로,
    # 해당 어댑터가 실제로 받는 선택적 설정만 남긴다. 그 외 오타는 그대로 TypeError 로 드러난다.
    accepted = set(inspect.signature(adapter_cls.__init__).parameters)
    kwargs = {
        k: v
        for k, v in kwargs.items()
        if k in accepted or k not in _OPTIONAL_ADAPTER_KWARGS
    }
    return adapter_cls(**kwargs)


__all__ = [
    "BaseCLIAdapter",
    "GenericCLIAdapter",
    "ClaudeCLIAdapter",
    "AGYCLIAdapter",
    "AiderCLIAdapter",
    "CodexCLIAdapter",
    "create_adapter",
    "strip_ansi",
    "ADAPTER_REGISTRY",
    "get_available_agy_models",
    "get_agy_model_ids",
    "get_available_claude_models",
    "get_claude_model_ids",
    "get_available_codex_models",
    "get_codex_model_ids",
]
