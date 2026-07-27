"""Idempotently persist accepted events from the SQS pipeline."""

from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Any


def to_storage_items(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create event-history and latest-state items from a normalized event."""
    timestamp = payload["timestamp"]
    event_item = {
        "vehicle_id": payload["vehicle_id"],
        "timestamp_event_id": f"{timestamp}#{payload['event_id']}",
        "event_id": payload["event_id"],
        "domain": payload["domain"],
        "category_timestamp": f"{payload['data_category']}#{timestamp}",
        "sensor_type": payload["sensor_type"],
        "anomaly_score": payload["anomaly_score"],
        "payload": payload,
        "ttl": int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp())
        + 90 * 24 * 60 * 60,
    }
    latest_item = {
        "vehicle_id": payload["vehicle_id"],
        "timestamp": timestamp,
        "domain": payload["domain"],
        "data_category": payload["data_category"],
        "sensor_type": payload["sensor_type"],
        "anomaly_score": payload["anomaly_score"],
        "sensor_data": payload["sensor_data"],
    }
    return event_item, latest_item


def _archive_key(payload: dict[str, Any]) -> str:
    timestamp = datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
    return (
        f"events/domain={payload['domain']}/date={timestamp:%Y-%m-%d}/"
        f"hour={timestamp:%H}/{payload['event_id']}.json"
    )


def _process_record(
    payload: dict[str, Any], events_table: Any, latest_table: Any, archive_bucket: Any, alerts: Any
) -> None:
    from botocore.exceptions import ClientError

    event_item, latest_item = to_storage_items(payload)
    try:
        events_table.put_item(
            Item=event_item,
            ConditionExpression="attribute_not_exists(timestamp_event_id)",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return

    try:
        latest_table.put_item(
            Item=latest_item,
            ConditionExpression="attribute_not_exists(vehicle_id) OR #timestamp <= :timestamp",
            ExpressionAttributeNames={"#timestamp": "timestamp"},
            ExpressionAttributeValues={":timestamp": payload["timestamp"]},
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
    archive_bucket.put_object(
        Key=_archive_key(payload),
        Body=json.dumps(payload, separators=(",", ":")),
        ContentType="application/json",
    )
    if payload["anomaly_score"] > 0.8:
        alerts.publish(
            TopicArn=os.environ["ALERT_TOPIC_ARN"],
            Subject=f"Fleet alert: {payload['domain']}",
            Message=json.dumps(payload, separators=(",", ":")),
        )


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """SQS trigger with partial batch failure reporting for transient errors."""
    import boto3

    resource = boto3.resource("dynamodb")
    events_table = resource.Table(os.environ["EVENTS_TABLE_NAME"])
    latest_table = resource.Table(os.environ["LATEST_TABLE_NAME"])
    archive_bucket = boto3.resource("s3").Bucket(os.environ["ARCHIVE_BUCKET_NAME"])
    alerts = boto3.client("sns", region_name=os.environ.get("AWS_REGION"))
    failures = []
    for record in event["Records"]:
        try:
            _process_record(
                json.loads(record["body"]), events_table, latest_table, archive_bucket, alerts
            )
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}