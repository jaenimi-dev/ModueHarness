"""ModueHarness - Multi-AI CLI Collaboration Harness Framework."""

__version__ = "0.1.0"

from modue_harness.adapters import (
    BaseCLIAdapter,
    GenericCLIAdapter,
    create_adapter,
)
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.config import HarnessConfig
from modue_harness.core.harness import BaseHarness
from modue_harness.core.types import (
    Task,
    TaskStatus,
    TurnContext,
    TurnResult,
)
from modue_harness.engine import PipelineRunner, WorkflowConfig

__all__ = [
    "__version__",
    "BaseHarness",
    "HarnessConfig",
    "Blackboard",
    "Task",
    "TaskStatus",
    "TurnContext",
    "TurnResult",
    "BaseCLIAdapter",
    "GenericCLIAdapter",
    "create_adapter",
    "PipelineRunner",
    "WorkflowConfig",
]
