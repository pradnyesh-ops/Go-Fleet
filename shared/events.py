"""Versioned sensor-event contract used across the platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
from typing import Any, Mapping


class Domain(StrEnum):
    RENTAL = "rental"
    FLEET = "fleet"
    INDUSTRIAL = "industrial"


class DataCategory(StrEnum):
    USAGE = "usage"
    BEHAVIOUR = "behaviour"
    HEALTH = "health"
    LOAD = "load"
    COMPLIANCE = "compliance"
    EFFICIENCY = "efficiency"


SENSOR_CATEGORIES: dict[str, tuple[DataCategory, frozenset[DataCategory]]] = {
    "telematics": (
        DataCategory.USAGE,
        frozenset((DataCategory.USAGE, DataCategory.COMPLIANCE)),
    ),
    "engine_drivetrain": (DataCategory.HEALTH, frozenset((DataCategory.HEALTH,))),
    "driver_behaviour": (
        DataCategory.BEHAVIOUR,
        frozenset((DataCategory.BEHAVIOUR, DataCategory.COMPLIANCE)),
    ),
    "load_structural": (
        DataCategory.LOAD,
        frozenset((DataCategory.LOAD, DataCategory.COMPLIANCE)),
    ),
    "environment_cabin": (
        DataCategory.EFFICIENCY,
        frozenset((DataCategory.EFFICIENCY, DataCategory.COMPLIANCE)),
    ),
}


def parse_utc_timestamp(value: str) -> datetime:
    """Return a UTC datetime for an ISO-8601 timestamp ending in Z or an offset."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def build_event_id(
    fog_node_id: str, vehicle_id: str, timestamp: str, sensor_type: str
) -> str:
    source = ":".join((fog_node_id, vehicle_id, timestamp, sensor_type))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SensorEvent:
    """The normalized envelope sent by a fog node to the cloud pipeline."""

    fog_node_id: str
    vehicle_id: str
    domain: Domain
    sensor_type: str
    timestamp: str
    sensor_data: Mapping[str, Any]
    data_category: DataCategory | None = None
    anomaly_score: float = 0.0
    schema_version: str = "1.0"
    dispatch_attempt: int = 1
    buffered: bool = False
    event_id: str = field(init=False)

    def __post_init__(self) -> None:
        parse_utc_timestamp(self.timestamp)
        if not self.fog_node_id or not self.vehicle_id:
            raise ValueError("fog_node_id and vehicle_id are required")
        if self.sensor_type not in SENSOR_CATEGORIES:
            raise ValueError(f"unsupported sensor type: {self.sensor_type}")
        default_category, allowed_categories = SENSOR_CATEGORIES[self.sensor_type]
        category = self.data_category or default_category
        if category not in allowed_categories:
            raise ValueError(
                f"{self.sensor_type} must use one of "
                f"{', '.join(item.value for item in allowed_categories)}"
            )
        if not 0.0 <= self.anomaly_score <= 1.0:
            raise ValueError("anomaly_score must be between 0.0 and 1.0")
        if self.dispatch_attempt < 1:
            raise ValueError("dispatch_attempt must be at least 1")
        object.__setattr__(self, "data_category", category)
        object.__setattr__(
            self,
            "event_id",
            build_event_id(
                self.fog_node_id, self.vehicle_id, self.timestamp, self.sensor_type
            ),
        )

    @property
    def topic(self) -> str:
        return (
            f"fleet/v1/{self.domain.value}/{self.vehicle_id}/"
            f"{self.data_category.value}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "fog_node_id": self.fog_node_id,
            "vehicle_id": self.vehicle_id,
            "domain": self.domain.value,
            "sensor_type": self.sensor_type,
            "data_category": self.data_category.value,
            "anomaly_score": self.anomaly_score,
            "timestamp": self.timestamp,
            "dispatch_attempt": self.dispatch_attempt,
            "buffered": self.buffered,
            "sensor_data": dict(self.sensor_data),
        }


def validate_topic(event: SensorEvent, topic: str) -> None:
    """Reject messages whose MQTT topic does not match their trusted envelope."""
    if topic != event.topic:
        raise ValueError("MQTT topic does not match event envelope")
