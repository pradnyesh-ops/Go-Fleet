"""SQLite-backed outbox for fog-node MQTT connectivity loss."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Callable

from shared.events import DataCategory, Domain, SensorEvent


class SQLiteOutbox:
    def __init__(self, path: Path, capacity: int = 10_000) -> None:
        self.connection = sqlite3.connect(path)
        self.capacity = capacity
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_events (
                event_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                dispatch_attempt INTEGER NOT NULL DEFAULT 1
            )
            """
        )

    def enqueue(self, event: SensorEvent) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO pending_events(event_id, payload, created_at, dispatch_attempt)
            VALUES (?, ?, ?, ?)
            """,
            (event.event_id, json.dumps(event.to_dict()), event.timestamp, event.dispatch_attempt),
        )
        self.connection.execute(
            """
            DELETE FROM pending_events WHERE event_id IN (
                SELECT event_id FROM pending_events
                ORDER BY created_at ASC LIMIT MAX((SELECT COUNT(*) FROM pending_events) - ?, 0)
            )
            """,
            (self.capacity,),
        )
        self.connection.commit()

    def replay(self, publish: Callable[[SensorEvent], None]) -> int:
        rows = self.connection.execute(
            "SELECT event_id, payload, dispatch_attempt FROM pending_events ORDER BY created_at ASC"
        ).fetchall()
        sent = 0
        for event_id, payload, dispatch_attempt in rows:
            event = self._event_from_payload(json.loads(payload), dispatch_attempt)
            publish(event)
            self.connection.execute("DELETE FROM pending_events WHERE event_id = ?", (event_id,))
            self.connection.commit()
            sent += 1
        return sent

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _event_from_payload(payload: dict[str, object], dispatch_attempt: int) -> SensorEvent:
        return SensorEvent(
            fog_node_id=str(payload["fog_node_id"]),
            vehicle_id=str(payload["vehicle_id"]),
            domain=Domain(str(payload["domain"])),
            sensor_type=str(payload["sensor_type"]),
            timestamp=str(payload["timestamp"]),
            sensor_data=dict(payload["sensor_data"]),  # type: ignore[arg-type]
            data_category=DataCategory(str(payload["data_category"])),
            anomaly_score=float(payload["anomaly_score"]),
            schema_version=str(payload["schema_version"]),
            dispatch_attempt=dispatch_attempt + 1,
            buffered=True,
        )