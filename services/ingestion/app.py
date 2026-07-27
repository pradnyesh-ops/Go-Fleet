"""Validate AWS IoT messages before placing them on the durable queue."""

from __future__ import annotations

import json
import os
from typing import Any

from shared.events import DataCategory, Domain, SensorEvent, validate_topic


def parse_iot_event(message: dict[str, Any]) -> SensorEvent:
    """Reconstruct and validate the shared contract from an IoT Rule payload."""
    event = SensorEvent(
        fog_node_id=message["fog_node_id"],
        vehicle_id=message["vehicle_id"],
        domain=Domain(message["domain"]),
        sensor_type=message["sensor_type"],
        timestamp=message["timestamp"],
        sensor_data=message["sensor_data"],
        data_category=DataCategory(message["data_category"]),
        anomaly_score=float(message["anomaly_score"]),
        schema_version=message.get("schema_version", "1.0"),
        dispatch_attempt=int(message.get("dispatch_attempt", 1)),
        buffered=bool(message.get("buffered", False)),
    )
    validate_topic(event, message["mqtt_topic"])
    if message.get("event_id") and message["event_id"] != event.event_id:
        raise ValueError("event_id does not match its deterministic source fields")
    return event


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """AWS IoT Rule target: validate then enqueue one normalized event."""
    normalized = parse_iot_event(event)
    import boto3

    queue_url = os.environ["QUEUE_URL"]
    boto3.client("sqs").send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(normalized.to_dict(), separators=(",", ":")),
    )
    return {"event_id": normalized.event_id, "accepted": True}