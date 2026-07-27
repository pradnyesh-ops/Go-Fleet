import json

from services.simulator.app import generate_events, queue_batches


def test_cloud_simulator_generates_a_valid_event_for_each_configured_sensor() -> None:
    events = generate_events("2026-07-27T09:15:01Z")

    assert len(events) == 13
    assert {event.vehicle_id for event in events} == {"RNT-0001", "FLT-0002", "IND-0003"}
    assert all(event.topic.startswith("fleet/v1/") for event in events)
    assert all(json.loads(json.dumps(event.to_dict()))["event_id"] == event.event_id for event in events)


def test_cloud_simulator_splits_messages_to_sqs_batch_limit() -> None:
    events = generate_events("2026-07-27T09:15:01Z")

    batches = queue_batches(events)

    assert [len(batch) for batch in batches] == [10, 3]
    assert sum(len(batch) for batch in batches) == len(events)