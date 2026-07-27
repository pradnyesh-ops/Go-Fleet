"""Generate fog-enriched demo telemetry for the hosted dashboard."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from random import Random
from typing import Any

from fog.processor import FogProcessor
from shared.events import Domain, SensorEvent
from simulator.config import load_config
from simulator.generators import VehicleSensorGenerator


ROOT = Path(__file__).parents[2]
SQS_BATCH_SIZE = 10


def enrich_operational_risk(event: SensorEvent, seed: str) -> SensorEvent:
    """Add a reproducible mix of advisory and critical demo conditions."""
    random = Random(seed)
    data = dict(event.sensor_data)
    score = event.anomaly_score
    if event.sensor_type == "telematics" and random.random() < 0.24:
        data.update({"speed_kmh": round(random.uniform(103, 128), 1), "idle_seconds": 0})
        score = max(score, round(random.uniform(0.42, 0.76), 2))
    elif event.sensor_type == "driver_behaviour" and random.random() < 0.3:
        data.update({"event_type": "hard_brake", "severity_g": round(random.uniform(0.62, 0.92), 2)})
        score = max(score, round(random.uniform(0.45, 0.78), 2))
    elif event.sensor_type == "engine_drivetrain" and random.random() < 0.22:
        data.update({"engine_temp_c": round(random.uniform(105, 119), 1), "oil_pressure_bar": round(random.uniform(1.6, 2.5), 2)})
        score = max(score, round(random.uniform(0.68, 0.93), 2))
    elif event.sensor_type == "load_structural" and random.random() < 0.2:
        capacity = data["rated_capacity_kg"]
        data.update({"cargo_weight_kg": round(capacity * random.uniform(1.01, 1.12), 1), "load_utilisation_pct": round(random.uniform(101, 112), 1), "tilt_angle_deg": round(random.uniform(6, 11), 1)})
        score = max(score, round(random.uniform(0.74, 0.96), 2))
    elif event.sensor_type == "environment_cabin" and random.random() < 0.16:
        data.update({"impact_detected": True, "fuel_level_pct": round(random.uniform(4, 12), 1)})
        score = max(score, round(random.uniform(0.72, 0.91), 2))
    data["risk_band"] = "critical" if score >= 0.8 else "advisory" if score >= 0.4 else "normal"
    return replace(event, sensor_data=data, anomaly_score=score)


def generate_events(timestamp: str) -> list[SensorEvent]:
    """Create one fog-processed event for every configured sensor stream."""
    config = load_config(ROOT / "config" / "sensors.yaml")
    batch_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    generated_events = []
    for domain_index, (domain_name, profile) in enumerate(config["domains"].items(), start=1):
        domain = Domain(domain_name)
        for vehicle_index in range(1, int(profile.get("vehicle_count", 1)) + 1):
            vehicle_id = f"{profile['vehicle_prefix']}-{domain_index * 1000 + vehicle_index:04d}"
            processor = FogProcessor(
                fog_node_id=f"FOG-{profile['vehicle_prefix']}-DUBLIN-{vehicle_index:02d}",
                geofence=config["geofences"]["dublin_rental_zone"] if domain is Domain.RENTAL else None,
            )
            generator = VehicleSensorGenerator(domain, seed=f"{timestamp}:{vehicle_id}")
            for sensor_type in profile["sensors"]:
                event_timestamp = batch_time + timedelta(seconds=5 if sensor_type == "telematics" else 0)
                event = processor.process(
                        vehicle_id=vehicle_id,
                        domain=domain,
                        sensor_type=sensor_type,
                        timestamp=event_timestamp.isoformat().replace("+00:00", "Z"),
                        sensor_data=generator.generate(sensor_type),
                    )
                generated_events.append(enrich_operational_risk(event, f"{timestamp}:{vehicle_id}:{sensor_type}"))
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