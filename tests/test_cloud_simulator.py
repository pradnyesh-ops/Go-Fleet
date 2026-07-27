import json

from services.simulator.app import generate_events, queue_batches


def test_cloud_simulator_generates_a_valid_event_for_each_configured_sensor() -> None:
    events = generate_events("2026-07-27T09:15:01Z")

    assert len(events) == 52
    assert {event.vehicle_id for event in events} == {
        "RNT-1001", "RNT-1002", "RNT-1003", "RNT-1004",
        "FLT-2001", "FLT-2002", "FLT-2003", "FLT-2004",
        "IND-3001", "IND-3002", "IND-3003", "IND-3004",
    }
    assert all(event.topic.startswith("fleet/v1/") for event in events)
    assert all(json.loads(json.dumps(event.to_dict()))["event_id"] == event.event_id for event in events)


def test_cloud_simulator_splits_messages_to_sqs_batch_limit() -> None:
    events = generate_events("2026-07-27T09:15:01Z")

    batches = queue_batches(events)

    assert [len(batch) for batch in batches] == [10, 10, 10, 10, 10, 2]
    assert sum(len(batch) for batch in batches) == len(events)