"""Exact timestamp comparisons without rewriting immutable event material.

Legacy journal timestamps use optional fractional seconds. Their text order is
not chronological at a whole-second boundary. SQLite's date functions also
round below microsecond precision, so use aware datetimes for comparisons.
"""
from datetime import datetime
import sqlite3


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('timestamp must include a timezone')
    return parsed


def _compare(left: str, right: str) -> int:
    a, b = instant(left), instant(right)
    return (a > b) - (a < b)


def register_time_collation(connection: sqlite3.Connection) -> None:
    connection.create_collation('ICARUS_TIME', _compare)
