"""Tests for EventBus and HarnessEvent."""

from modue_harness.core.events import EventBus, EventType, HarnessEvent


def test_event_bus_publish_and_subscribe():
    """Verify subscribing and receiving events via EventBus."""
    bus = EventBus()
    received = []

    def handler(event: HarnessEvent):
        received.append(event)

    bus.subscribe(EventType.STEP_STARTED, handler)

    event = HarnessEvent(
        event_type=EventType.STEP_STARTED,
        step_id="step_alpha",
        agent_name="planner",
        payload={"info": "started"},
    )
    bus.publish(event)

    assert len(received) == 1
    assert received[0].step_id == "step_alpha"
    assert received[0].payload["info"] == "started"


def test_event_bus_history_and_filter():
    """Verify event history recording and filtering."""
    bus = EventBus()
    bus.publish(HarnessEvent(event_type=EventType.WORKFLOW_STARTED))
    bus.publish(HarnessEvent(event_type=EventType.STEP_STARTED, step_id="1"))
    bus.publish(HarnessEvent(event_type=EventType.STEP_COMPLETED, step_id="1"))
    bus.publish(HarnessEvent(event_type=EventType.WORKFLOW_COMPLETED))

    assert len(bus.get_history()) == 4
    step_starts = bus.get_history(EventType.STEP_STARTED)
    assert len(step_starts) == 1
    assert step_starts[0].step_id == "1"

    bus.clear()
    assert len(bus.get_history()) == 0
