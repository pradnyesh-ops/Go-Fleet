"""Serve dashboard queries from DynamoDB without exposing AWS credentials."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any


class DecimalEncoder(json.JSONEncoder):
    def default(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return super().default(value)


def response(status_code: int, body: object) -> dict[str, object]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def handler(event: dict[str, Any], _context: Any) -> dict[str, object]:
    """Return latest state, or a recent event timeline for one vehicle."""
    import boto3

    path = event.get("rawPath") or event.get("path", "")
    vehicle_id = (event.get("pathParameters") or {}).get("vehicleId")

    dynamodb = boto3.resource("dynamodb")
    if path.endswith("/alerts"):
        events_table = dynamodb.Table(os.environ["EVENTS_TABLE_NAME"])
        latest_vehicles = dynamodb.Table(os.environ["LATEST_TABLE_NAME"]).scan().get("Items", [])

        def get_vehicle_events(vehicle: dict[str, Any]) -> list[dict[str, Any]]:
            return events_table.query(
                KeyConditionExpression="vehicle_id = :vehicle_id",
                ExpressionAttributeValues={":vehicle_id": vehicle["vehicle_id"]},
                ScanIndexForward=False,
                Limit=50,
            ).get("Items", [])

        with ThreadPoolExecutor(max_workers=4) as executor:
            vehicle_events = executor.map(get_vehicle_events, latest_vehicles)
        critical_by_vehicle: dict[str, dict[str, Any]] = {}
        for events in vehicle_events:
            for item in events:
                if float(item["anomaly_score"]) < 0.8:
                    continue
                vehicle = item["vehicle_id"]
                existing = critical_by_vehicle.get(vehicle)
                if existing is None or item["timestamp_event_id"] > existing["timestamp_event_id"]:
                    critical_by_vehicle[vehicle] = item
        alerts = sorted(
            critical_by_vehicle.values(),
            key=lambda item: float(item["anomaly_score"]),
            reverse=True,
        )
        return response(200, {"items": alerts})
    if not vehicle_id:
        return response(400, {"message": "vehicleId is required"})
    if path.endswith("/latest"):
        item = dynamodb.Table(os.environ["LATEST_TABLE_NAME"]).get_item(
            Key={"vehicle_id": vehicle_id}
        ).get("Item")
        return response(200, item or {})

    result = dynamodb.Table(os.environ["EVENTS_TABLE_NAME"]).query(
        KeyConditionExpression="vehicle_id = :vehicle_id",
        ExpressionAttributeValues={":vehicle_id": vehicle_id},
        ScanIndexForward=False,
        Limit=50,
    )
    return response(200, {"items": result.get("Items", [])})