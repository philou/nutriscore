"""SQLite-backed append-only event store.

Events for one meal share a ``stream_id`` (the meal id) and a monotonic ``seq``
starting at 1. A ``UNIQUE(stream_id, seq)`` constraint plus an expected-sequence
check give optimistic concurrency: two writers racing on the same stream cannot
both succeed.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..domain.events import (
    DomainEvent,
    FoodItemAdded,
    MealConcluded,
    MealStarted,
)

_EVENT_TYPES: dict[str, type[DomainEvent]] = {
    "MealStarted": MealStarted,
    "FoodItemAdded": FoodItemAdded,
    "MealConcluded": MealConcluded,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id   TEXT    NOT NULL,
    seq         INTEGER NOT NULL,
    event_type  TEXT    NOT NULL,
    payload     TEXT    NOT NULL,
    recorded_at TEXT    NOT NULL,
    UNIQUE (stream_id, seq)
);
"""


class ConcurrencyError(Exception):
    """Raised when an append's expected sequence does not match the stream."""


class SqliteEventStore:
    """A minimal event store over a single ``events`` table."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(
        self,
        stream_id: str,
        expected_seq: int,
        events: list[DomainEvent],
    ) -> None:
        """Atomically append ``events`` to a stream.

        ``expected_seq`` must equal the stream's current highest sequence (0 for
        a new stream). Raises :class:`ConcurrencyError` otherwise.
        """

        if not events:
            return
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS m FROM events WHERE stream_id = ?",
            (stream_id,),
        ).fetchone()
        current = row["m"]
        if current != expected_seq:
            raise ConcurrencyError(
                f"stream {stream_id!r}: expected seq {expected_seq}, found {current}"
            )
        recorded_at = datetime.now(timezone.utc).isoformat()
        seq = expected_seq
        try:
            for event in events:
                seq += 1
                self._conn.execute(
                    "INSERT INTO events (stream_id, seq, event_type, payload, recorded_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (stream_id, seq, type(event).__name__, event.model_dump_json(), recorded_at),
                )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:  # UNIQUE(stream_id, seq) race
            self._conn.rollback()
            raise ConcurrencyError(str(exc)) from exc

    def load_stream(self, stream_id: str) -> list[DomainEvent]:
        """Return one meal's events, ordered by sequence."""
        rows = self._conn.execute(
            "SELECT event_type, payload FROM events WHERE stream_id = ? ORDER BY seq",
            (stream_id,),
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    def load_all(self) -> list[DomainEvent]:
        """Return every event in global append order (for projection rebuild)."""
        rows = self._conn.execute(
            "SELECT event_type, payload FROM events ORDER BY id"
        ).fetchall()
        return [self._deserialize(r) for r in rows]

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> DomainEvent:
        event_cls = _EVENT_TYPES[row["event_type"]]
        return event_cls.model_validate_json(row["payload"])
