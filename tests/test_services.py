from services.ingestion.app import parse_iot_event
from services.processor.app import to_storage_items


def payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "fog_node_id": "FOG-RNT-DUBLIN-01",
        "vehicle_id": "RNT-2041",
        "domain": "rental",
        "sensor_type": "telematics",
        "data_category": "usage",
        "anomaly_score": 0.1,
        "timestamp": "2026-07-27T09:15:01Z",
        "dispatch_attempt": 1,
        "buffered": False,
        "sensor_data": {"latitude": 53.3498, "longitude": -6.2603},
        "mqtt_topic": "fleet/v1/rental/RNT-2041/usage",
    }


def test_ingestion_reconstructs_and_validates_iot_payload() -> None:
    event = parse_iot_event(payload())

    assert event.topic == "fleet/v1/rental/RNT-2041/usage"
    assert event.event_id


def test_processor_storage_items_preserve_idempotency_and_query_keys() -> None:
    event = parse_iot_event(payload())
    normalized = event.to_dict()

    history, latest = to_storage_items(normalized)

    assert history["timestamp_event_id"].endswith(event.event_id)
    assert history["category_timestamp"] == "usage#2026-07-27T09:15:01Z"
    assert latest["vehicle_id"] == "RNT-2041"