"""Harness configuration models and environment loader."""

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, Optional


def load_dotenv(env_path: Optional[Path] = None) -> None:
    """Load environment variables from a .env file if present."""
    target = env_path or (Path.cwd() / ".env")
    if not target.exists():
        return

    try:
        content = target.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


@dataclass
class HarnessConfig:
    """Base configuration for a harness instance."""

    name: str = "default-harness"
    version: str = "0.6.0"
    debug: bool = False
    options: Dict[str, Any] = field(default_factory=dict)
