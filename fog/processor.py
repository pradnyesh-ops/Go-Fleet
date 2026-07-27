"""Fog enrichment: anomaly scoring, local geofence validation, and tagging."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Iterable, Sequence

from shared.events import DataCategory, Domain, SENSOR_CATEGORIES, SensorEvent


def point_in_polygon(latitude: float, longitude: float, polygon: Sequence[Sequence[float]]) -> bool:
    """Use ray casting to decide whether a latitude/longitude lies in a polygon."""
    inside = False
    previous_latitude, previous_longitude = polygon[-1]
    for current_latitude, current_longitude in polygon:
        crosses_latitude = (current_latitude > latitude) != (previous_latitude > latitude)
        if crosses_latitude:
            intersection_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )
            if longitude < intersection_longitude:
                inside = not inside
        previous_latitude, previous_longitude = current_latitude, current_longitude
    return inside


def normalized_z_score(value: float, values: Iterable[float]) -> float:
    history = list(values)
    if len(history) < 2:
        return 0.0
    mean = sum(history) / len(history)
    variance = sum((item - mean) ** 2 for item in history) / len(history)
    standard_deviation = sqrt(variance)
    if standard_deviation == 0:
        return 0.0
    return min(abs(value - mean) / standard_deviation / 3, 1.0)


@dataclass(slots=True)
class FogProcessor:
    fog_node_id: str
    geofence: Sequence[Sequence[float]] | None = None
    anomaly_window_size: int = 20
    _windows: dict[tuple[str, str], deque[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._windows = defaultdict(
            lambda: deque(maxlen=self.anomaly_window_size)
        )

    def process(
        self,
        *,
        vehicle_id: str,
        domain: Domain,
        sensor_type: str,
        timestamp: str,
        sensor_data: dict[str, Any],
    ) -> SensorEvent:
        metric = self._primary_metric(sensor_data)
        score = 0.0
        if metric is not None:
            window = self._windows[(vehicle_id, sensor_type)]
            score = normalized_z_score(metric, window)
            window.append(metric)

        default_category, _ = SENSOR_CATEGORIES[sensor_type]
        category = default_category
        enriched_data = dict(sensor_data)
        if sensor_type == "telematics" and self.geofence is not None:
            is_inside = point_in_polygon(
                float(sensor_data["latitude"]), float(sensor_data["longitude"]), self.geofence
            )
            enriched_data["geofence_status"] = "inside" if is_inside else "breach"
            if not is_inside:
                category = DataCategory.COMPLIANCE
                score = max(score, 0.9)

        return SensorEvent(
            fog_node_id=self.fog_node_id,
            vehicle_id=vehicle_id,
            domain=domain,
            sensor_type=sensor_type,
            timestamp=timestamp,
            sensor_data=enriched_data,
            data_category=category,
            anomaly_score=score,
        )

    @staticmethod
    def _primary_metric(sensor_data: dict[str, Any]) -> float | None:
        for value in sensor_data.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None