"""Adapter package exposing adapters and factory."""

from typing import Any, Dict, Type

from modue_harness.adapters.agy import AGYCLIAdapter
from modue_harness.adapters.aider import AiderCLIAdapter
from modue_harness.adapters.base import BaseCLIAdapter, strip_ansi
from modue_harness.adapters.claude import ClaudeCLIAdapter
from modue_harness.adapters.generic import GenericCLIAdapter

ADAPTER_REGISTRY: Dict[str, Type[BaseCLIAdapter]] = {
    "generic": GenericCLIAdapter,
    "claude": ClaudeCLIAdapter,
    "claude-code": ClaudeCLIAdapter,
    "agy": AGYCLIAdapter,
    "antigravity": AGYCLIAdapter,
    "aider": AiderCLIAdapter,
}


def create_adapter(adapter_type: str, **kwargs: Any) -> BaseCLIAdapter:
    """Instantiate an adapter from registered types or fallback to generic."""
    adapter_cls = ADAPTER_REGISTRY.get(adapter_type.lower(), GenericCLIAdapter)
    if adapter_cls is GenericCLIAdapter:
        kwargs.setdefault("name", adapter_type)
        kwargs.setdefault("command", adapter_type)
    return adapter_cls(**kwargs)


__all__ = [
    "BaseCLIAdapter",
    "GenericCLIAdapter",
    "ClaudeCLIAdapter",
    "AGYCLIAdapter",
    "AiderCLIAdapter",
    "create_adapter",
    "strip_ansi",
    "ADAPTER_REGISTRY",
]
