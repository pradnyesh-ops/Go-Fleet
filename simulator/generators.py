"""Deterministic mock readings for the five documented sensor types."""

from __future__ import annotations

from random import Random
from typing import Any

from shared.events import Domain


class VehicleSensorGenerator:
    """Generate realistic-enough sensor values for a configured vehicle profile."""

    def __init__(self, domain: Domain, seed: int | None = None) -> None:
        self.domain = domain
        self.random = Random(seed)

    def generate(self, sensor_type: str) -> dict[str, Any]:
        generators = {
            "telematics": self._telematics,
            "engine_drivetrain": self._engine_drivetrain,
            "driver_behaviour": self._driver_behaviour,
            "load_structural": self._load_structural,
            "environment_cabin": self._environment_cabin,
        }
        try:
            return generators[sensor_type]()
        except KeyError as error:
            raise ValueError(f"unsupported sensor type: {sensor_type}") from error

    def _telematics(self) -> dict[str, Any]:
        return {
            "latitude": round(53.3498 + self.random.uniform(-0.03, 0.03), 6),
            "longitude": round(-6.2603 + self.random.uniform(-0.03, 0.03), 6),
            "speed_kmh": round(max(0, self.random.gauss(48, 14)), 1),
            "heading_deg": self.random.randrange(360),
            "idle_seconds": self.random.randrange(0, 60),
        }

    def _engine_drivetrain(self) -> dict[str, Any]:
        return {
            "rpm": round(max(650, self.random.gauss(2200, 400))),
            "engine_temp_c": round(self.random.gauss(90, 4), 1),
            "oil_pressure_bar": round(self.random.gauss(3.8, 0.4), 2),
            "coolant_pct": round(self.random.uniform(70, 100), 1),
            "fuel_l_per_100km": round(self.random.gauss(9.2, 1.1), 2),
        }

    def _driver_behaviour(self) -> dict[str, Any]:
        event_type = self.random.choice(("heartbeat", "hard_brake", "sharp_corner"))
        return {
            "event_type": event_type,
            "severity_g": round(self.random.uniform(0.1, 0.7), 2),
            "seatbelt_on": self.random.random() > 0.02,
            "phone_detected": self.random.random() < 0.01,
            "speed_limit_compliant": self.random.random() > 0.04,
        }

    def _load_structural(self) -> dict[str, Any]:
        capacity = 3000 if self.domain is Domain.INDUSTRIAL else 8000
        weight = self.random.uniform(capacity * 0.2, capacity * 0.98)
        return {
            "cargo_weight_kg": round(weight, 1),
            "rated_capacity_kg": capacity,
            "load_utilisation_pct": round(weight / capacity * 100, 1),
            "tilt_angle_deg": round(self.random.uniform(0, 5), 1),
        }

    def _environment_cabin(self) -> dict[str, Any]:
        return {
            "ambient_temp_c": round(self.random.gauss(15, 5), 1),
            "cabin_temp_c": round(self.random.gauss(21, 2), 1),
            "humidity_pct": round(self.random.uniform(40, 80), 1),
            "impact_detected": self.random.random() < 0.01,
            "fuel_level_pct": round(self.random.uniform(15, 100), 1),
        }