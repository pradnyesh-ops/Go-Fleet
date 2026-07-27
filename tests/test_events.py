from shared.events import DataCategory, Domain, SensorEvent, validate_topic


def make_event(**overrides: object) -> SensorEvent:
    values: dict[str, object] = {
        "fog_node_id": "FOG-RNT-DUBLIN-01",
        "vehicle_id": "RNT-2041",
        "domain": Domain.RENTAL,
        "sensor_type": "telematics",
        "timestamp": "2026-07-27T09:15:01Z",
        "sensor_data": {"latitude": 53.3498, "longitude": -6.2603},
    }
    values.update(overrides)
    return SensorEvent(**values)  # type: ignore[arg-type]


def test_event_builds_stable_id_and_topic() -> None:
    event = make_event()

    assert event.event_id == make_event().event_id
    assert event.topic == "fleet/v1/rental/RNT-2041/usage"
    assert event.to_dict()["data_category"] == "usage"


def test_event_rejects_invalid_contract_values() -> None:
    invalid_timestamp = "2026-07-27 09:15:01"

    try:
        make_event(timestamp=invalid_timestamp)
    except ValueError as error:
        assert "timezone" in str(error)
    else:
        raise AssertionError("Expected invalid timestamp to be rejected")

    try:
        make_event(data_category=DataCategory.LOAD)
    except ValueError as error:
        assert "must use one of" in str(error)
    else:
        raise AssertionError("Expected mismatched data category to be rejected")


def test_topic_validation_rejects_mismatch() -> None:
    event = make_event()

    validate_topic(event, event.topic)

    try:
        validate_topic(event, "fleet/v1/fleet/FLT-0192/usage")
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("Expected mismatched topic to be rejected")