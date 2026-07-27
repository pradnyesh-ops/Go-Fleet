from pathlib import Path

from fog.outbox import SQLiteOutbox
from fog.processor import FogProcessor, point_in_polygon
from shared.events import DataCategory, Domain
from simulator.config import load_config
from simulator.generators import VehicleSensorGenerator


ROOT = Path(__file__).parents[1]


def test_sensor_profiles_generate_all_documented_sensor_shapes() -> None:
    generator = VehicleSensorGenerator(Domain.FLEET, seed=7)

    assert "latitude" in generator.generate("telematics")
    assert "rpm" in generator.generate("engine_drivetrain")
    assert "event_type" in generator.generate("driver_behaviour")
    assert "cargo_weight_kg" in generator.generate("load_structural")
    assert "impact_detected" in generator.generate("environment_cabin")


def test_config_and_geofence_breach_become_high_severity_compliance_event() -> None:
    config = load_config(ROOT / "config" / "sensors.yaml")
    polygon = config["geofences"]["dublin_rental_zone"]
    processor = FogProcessor("FOG-RNT-DUBLIN-01", geofence=polygon)

    event = processor.process(
        vehicle_id="RNT-2041",
        domain=Domain.RENTAL,
        sensor_type="telematics",
        timestamp="2026-07-27T09:15:01Z",
        sensor_data={"latitude": 53.50, "longitude": -6.26, "speed_kmh": 62.4},
    )

    assert event.data_category is DataCategory.COMPLIANCE
    assert event.anomaly_score == 0.9
    assert event.sensor_data["geofence_status"] == "breach"
    assert not point_in_polygon(53.50, -6.26, polygon)


def test_sqlite_outbox_replays_events_in_order_with_original_event_id(tmp_path: Path) -> None:
    processor = FogProcessor("FOG-FLT-DUBLIN-01")
    first = processor.process(
        vehicle_id="FLT-0192",
        domain=Domain.FLEET,
        sensor_type="engine_drivetrain",
        timestamp="2026-07-27T09:15:01Z",
        sensor_data={"rpm": 2100},
    )
    second = processor.process(
        vehicle_id="FLT-0192",
        domain=Domain.FLEET,
        sensor_type="engine_drivetrain",
        timestamp="2026-07-27T09:15:02Z",
        sensor_data={"rpm": 2200},
    )
    outbox = SQLiteOutbox(tmp_path / "outbox.db")
    outbox.enqueue(first)
    outbox.enqueue(second)
    replayed = []

    assert outbox.replay(replayed.append) == 2
    assert [event.event_id for event in replayed] == [first.event_id, second.event_id]
    assert all(event.buffered for event in replayed)
    assert outbox.replay(replayed.append) == 0
    outbox.close()