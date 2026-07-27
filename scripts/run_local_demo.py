"""Generate one fog-enriched reading for every configured sensor profile."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from fog.processor import FogProcessor
from shared.events import Domain
from simulator.config import load_config
from simulator.generators import VehicleSensorGenerator


def main() -> None:
    config = load_config(ROOT / "config" / "sensors.yaml")
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for index, (domain_name, profile) in enumerate(config["domains"].items(), start=1):
        domain = Domain(domain_name)
        vehicle_id = f"{profile['vehicle_prefix']}-{index:04d}"
        processor = FogProcessor(
            fog_node_id=f"FOG-{profile['vehicle_prefix']}-DUBLIN-01",
            geofence=config["geofences"]["dublin_rental_zone"] if domain is Domain.RENTAL else None,
        )
        generator = VehicleSensorGenerator(domain, seed=index)
        for sensor_type in profile["sensors"]:
            event = processor.process(
                vehicle_id=vehicle_id,
                domain=domain,
                sensor_type=sensor_type,
                timestamp=timestamp,
                sensor_data=generator.generate(sensor_type),
            )
            print(json.dumps({"topic": event.topic, "event": event.to_dict()}))


if __name__ == "__main__":
    main()