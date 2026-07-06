"""Shared pytest fixtures.

Provides an isolated event-store database per test so that event-sourced
components can be exercised without sharing state between tests. A temp-file
SQLite database (rather than a pure in-memory one) is used because the event
store is expected to be reopened by fresh connections — e.g. rebuilding
projections on startup replays events through a new connection — which an
``:memory:`` database (torn down when its single connection closes) cannot
represent.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Path to a fresh, isolated SQLite database file for one test.

    The file lives under pytest's per-test ``tmp_path`` and is removed with it,
    so no state leaks between tests. The file itself is not created here; the
    event store is responsible for creating its own schema at this path.
    """
    return tmp_path / "events.db"


@pytest.fixture
def db_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """An open connection to the isolated per-test database, closed on teardown."""
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()
