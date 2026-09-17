"""Harness configuration models."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class HarnessConfig:
    """Base configuration for a harness instance."""

    name: str = "default-harness"
    version: str = "0.0.0"
    debug: bool = False
    options: Dict[str, Any] = field(default_factory=dict)
