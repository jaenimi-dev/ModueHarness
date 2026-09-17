"""Event system and bus for ModueHarness lifecycle events."""

from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class EventType(str, Enum):
    """Types of harness execution events."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    TASK_STATUS_CHANGED = "task_status_changed"
    ARTIFACT_PRODUCED = "artifact_produced"
    LOG_EMITTED = "log_emitted"


@dataclass
class HarnessEvent:
    """Represents a single lifecycle or operational event."""

    event_type: EventType
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    step_id: Optional[str] = None
    agent_name: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "payload": self.payload,
        }


class EventBus:
    """In-memory publish-subscribe event broker."""

    def __init__(self) -> None:
        self._listeners: Dict[EventType, List[Callable[[HarnessEvent], None]]] = {}
        self._history: List[HarnessEvent] = []

    def subscribe(self, event_type: EventType, callback: Callable[[HarnessEvent], None]) -> None:
        """Register a callback handler for a specific event type."""
        self._listeners.setdefault(event_type, []).append(callback)

    def publish(self, event: HarnessEvent) -> None:
        """Publish an event to all subscribers and append to history."""
        self._history.append(event)
        for callback in self._listeners.get(event.event_type, []):
            try:
                callback(event)
            except Exception:
                # Event subscriber failures should not crash workflow
                pass

    def get_history(self, event_type: Optional[EventType] = None) -> List[HarnessEvent]:
        """Retrieve recorded event history, optionally filtered by type."""
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e.event_type == event_type]

    def clear(self) -> None:
        """Clear recorded event history."""
        self._history.clear()
