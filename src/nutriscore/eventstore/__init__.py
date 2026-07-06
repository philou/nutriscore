"""Append-only SQLite event store."""

from .sqlite import ConcurrencyError, SqliteEventStore

__all__ = ["ConcurrencyError", "SqliteEventStore"]
