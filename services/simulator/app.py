"""Generate fog-enriched demo telemetry for the hosted dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fog.processor import FogProcessor
from shared.events import Domain, SensorEvent
from simulator.config import load_config
from simulator.generators import VehicleSensorGenerator


ROOT = Path(__file__).parents[2]
SQS_BATCH_SIZE = 10


def generate_events(timestamp: str) -> list[SensorEvent]:
    """Create one fog-processed event for every configured sensor stream."""
    config = load_config(ROOT / "config" / "sensors.yaml")
    generated_events = []
    for domain_index, (domain_name, profile) in enumerate(config["domains"].items(), start=1):
        domain = Domain(domain_name)
        for vehicle_index in range(1, int(profile.get("vehicle_count", 1)) + 1):
            vehicle_id = f"{profile['vehicle_prefix']}-{domain_index * 1000 + vehicle_index:04d}"
            processor = FogProcessor(
                fog_node_id=f"FOG-{profile['vehicle_prefix']}-DUBLIN-{vehicle_index:02d}",
                geofence=config["geofences"]["dublin_rental_zone"] if domain is Domain.RENTAL else None,
            )
            generator = VehicleSensorGenerator(domain, seed=domain_index * 100 + vehicle_index)
            for sensor_type in profile["sensors"]:
                generated_events.append(
                    processor.process(
                        vehicle_id=vehicle_id,
                        domain=domain,
                        sensor_type=sensor_type,
                        timestamp=timestamp,
                        sensor_data=generator.generate(sensor_type),
                    )
                )
    return generated_events


def queue_batches(events: list[SensorEvent]) -> list[list[dict[str, str]]]:
    """Encode generated events into SQS batches of at most ten entries."""
    entries = [
        {"Id": str(index), "MessageBody": json.dumps(item.to_dict(), separators=(",", ":"))}
        for index, item in enumerate(events)
    ]
    return [entries[index : index + SQS_BATCH_SIZE] for index in range(0, len(entries), SQS_BATCH_SIZE)]


def handler(_event: dict[str, Any], _context: Any) -> dict[str, int]:
    """EventBridge target that sends a fresh demo batch into the telemetry queue."""
    import boto3

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    queue = boto3.client("sqs")
    generated_events = generate_events(timestamp)
    for entries in queue_batches(generated_events):
        response = queue.send_message_batch(QueueUrl=os.environ["QUEUE_URL"], Entries=entries)
        if response.get("Failed"):
            raise RuntimeError(f"Failed to enqueue simulator events: {response['Failed']}")
    return {"generated": len(generated_events)}