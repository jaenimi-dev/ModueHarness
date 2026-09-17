"""ModueHarness - Multi-AI CLI Collaboration Harness Framework."""

__version__ = "0.4.0"

from modue_harness.adapters import (
    AGYCLIAdapter,
    AiderCLIAdapter,
    BaseCLIAdapter,
    ClaudeCLIAdapter,
    GenericCLIAdapter,
    create_adapter,
)
from modue_harness.core.blackboard import Blackboard
from modue_harness.core.config import HarnessConfig
from modue_harness.core.events import EventBus, EventType, HarnessEvent
from modue_harness.core.harness import BaseHarness
from modue_harness.core.supervisor import ProcessSupervisor
from modue_harness.core.types import (
    Task,
    TaskStatus,
    TurnContext,
    TurnResult,
)
from modue_harness.engine import (
    ConductorRunner,
    DebateRunner,
    PipelineRunner,
    WorkflowConfig,
)
from modue_harness.plugins import (
    BasePlugin,
    MarkdownReportPlugin,
    PluginManager,
)
from modue_harness.workspace import GitWorkspaceManager

__all__ = [
    "__version__",
    "BaseHarness",
    "HarnessConfig",
    "Blackboard",
    "Task",
    "TaskStatus",
    "TurnContext",
    "TurnResult",
    "EventBus",
    "EventType",
    "HarnessEvent",
    "ProcessSupervisor",
    "BaseCLIAdapter",
    "GenericCLIAdapter",
    "ClaudeCLIAdapter",
    "AGYCLIAdapter",
    "AiderCLIAdapter",
    "create_adapter",
    "PipelineRunner",
    "ConductorRunner",
    "DebateRunner",
    "WorkflowConfig",
    "GitWorkspaceManager",
    "BasePlugin",
    "MarkdownReportPlugin",
    "PluginManager",
]
