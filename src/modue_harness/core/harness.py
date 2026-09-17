"""Base harness abstraction and lifecycle definitions."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from modue_harness.core.config import HarnessConfig


class BaseHarness(ABC):
    """Abstract base class for all harness implementations."""

    def __init__(self, config: Optional[HarnessConfig] = None) -> None:
        self.config = config or HarnessConfig()
        self._is_initialized: bool = False

    @abstractmethod
    def setup(self) -> None:
        """Initialize and prepare resources for the harness."""
        self._is_initialized = True

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the harness workload."""
        pass

    @abstractmethod
    def teardown(self) -> None:
        """Clean up resources utilized by the harness."""
        self._is_initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check whether the harness is initialized."""
        return self._is_initialized

    def __enter__(self) -> "BaseHarness":
        self.setup()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.teardown()
