"""
repo.py - Database repository functions for meteo measurements.

This module provides the persistence and query primitives used by
the service layer. It intentionally contains:
- no FastAPI code
- no business aggregation logic
- no pandas usage

All functions operate on SQLModel Session objects and return either
SQLModel instances or plain Python collections.

SQLite note
-----------
In this assignment we store timestamps in SQLite and they are represented
as TEXT in the database (e.g. "2021-05-01 01:52:50"). To keep time-window
filtering reliable, this module normalizes datetime boundaries into the
same sortable string format when querying time windows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func
from sqlmodel import Session, select, text

from .models import Measurement


def _dt_to_sqlite_ts(dt: datetime) -> str:
    """
    Convert a datetime into the exact timestamp string format used in SQLite.

    The DB stores timestamps like: "YYYY-MM-DD HH:MM:SS" (TEXT).
    Comparing strings in this format is safe for chronological ordering.

    Parameters
    ----------
    dt : datetime
        Datetime boundary. If timezone-aware, it is converted to UTC and made naive.

    Returns
    -------
    str
        Timestamp formatted as "YYYY-MM-DD HH:MM:SS".
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_sqlite_ts(v: object) -> datetime | None:
    """
    Parse a timestamp coming back from SQLite.

    SQLite may return timestamps as strings (TEXT) or as datetime objects,
    depending on driver configuration.

    Supported string forms:
    - "YYYY-MM-DD HH:MM:SS"
    - ISO8601 like "YYYY-MM-DDTHH:MM:SSZ" / with offsets

    Returns
    -------
    datetime | None
        Parsed datetime as naive UTC datetime, or None if parsing fails.
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        # normalize to naive UTC
        return v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v

    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None

        # Try common SQLite format first
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

        # Try ISO formats (handle 'Z')
        try:
            s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            return None

    return None


def ensure_indexes(session: Session) -> None:
    """
    Ensure required indexes and uniqueness constraints exist in the database.

    This function is idempotent and safe to call multiple times.
    SQLite supports `CREATE INDEX IF NOT EXISTS`, so no checks are needed.

    Indexes created:
    - Unique constraint on (sensor_id, ts, parameter, pt) to prevent duplicates
    - Index on (sensor_id, ts) for time-window queries
    - Index on (sensor_id, parameter, ts) for per-parameter lookups
    """
    session.exec(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_measurement
            ON measurement(sensor_id, ts, parameter, pt);
            """
        )
    )
    session.exec(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_measurement_sensor_ts
            ON measurement(sensor_id, ts);
            """
        )
    )
    session.exec(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_measurement_sensor_param_ts
            ON measurement(sensor_id, parameter, ts);
            """
        )
    )
    session.commit()


def bulk_upsert_measurements(session: Session, rows: Iterable[Measurement]) -> int:
    """
    Bulk insert or update Measurement rows using SQLite UPSERT semantics.

    Rows are uniquely identified by:
        (sensor_id, ts, parameter, pt)

    If a row with the same unique key already exists, its value and
    source_file are updated.

    Returns number of rows attempted (not necessarily newly inserted).
    """
    rows = list(rows)
    if not rows:
        return 0

    session.exec(
        text(
            """
            INSERT INTO measurement (sensor_id, ts, parameter, value, pt, source_file)
            VALUES (:sensor_id, :ts, :parameter, :value, :pt, :source_file)
            ON CONFLICT(sensor_id, ts, parameter, pt)
            DO UPDATE SET
                value=excluded.value,
                source_file=excluded.source_file;
            """
        ),
        params=[
            {
                "sensor_id": m.sensor_id,
                # Store as "YYYY-MM-DD HH:MM:SS" to match our query normalization
                "ts": _dt_to_sqlite_ts(m.ts),
                "parameter": m.parameter,
                "value": m.value,
                "pt": m.pt,
                "source_file": m.source_file,
            }
            for m in rows
        ],
    )
    session.commit()
    return len(rows)


def get_measurements_window(
    session: Session,
    *,
    sensor_id: str,
    start: datetime,
    end: datetime,
    parameters: Optional[list[str]] = None,
) -> list[Measurement]:
    """
    Fetch measurements for a sensor within a half-open time window [start, end).

    Because SQLite stores ts as TEXT in this project, we normalize `start` and `end`
    to the same sortable string format used in the DB ("YYYY-MM-DD HH:MM:SS").
    This prevents subtle mismatches in datetime binding and ensures deterministic
    filtering.

    Results are ordered by ascending timestamp.
    """
    start_s = _dt_to_sqlite_ts(start)
    end_s = _dt_to_sqlite_ts(end)

    stmt = select(Measurement).where(
        Measurement.sensor_id == sensor_id,
        Measurement.ts >= start_s,
        Measurement.ts < end_s,
    )

    if parameters:
        stmt = stmt.where(Measurement.parameter.in_(parameters))

    stmt = stmt.order_by(Measurement.ts.asc())
    return list(session.exec(stmt).all())


def get_max_ts(session: Session, *, sensor_id: str) -> datetime | None:
    """
    Return the latest timestamp available for a given sensor.

    Notes
    -----
    - With SQLite TEXT timestamps, MAX(ts) returns a string.
    - We parse it into a Python datetime (naive UTC) so the service layer can
      compute windows like `end - timedelta(days=7)` safely.
    """
    stmt = select(func.max(Measurement.ts)).where(Measurement.sensor_id == sensor_id)
    v = session.exec(stmt).one()
    return _parse_sqlite_ts(v)


def get_latest_per_parameter(session: Session, *, sensor_id: str) -> dict[str, Measurement]:
    """
    Retrieve the most recent measurement per parameter for a sensor.

    Implementation strategy:
    - Query all rows for the sensor ordered by ts DESC
    - Take the first occurrence per parameter
    """
    stmt = (
        select(Measurement)
        .where(Measurement.sensor_id == sensor_id)
        .order_by(Measurement.ts.desc())
    )

    latest: dict[str, Measurement] = {}
    for m in session.exec(stmt):
        if m.parameter not in latest:
            latest[m.parameter] = m
    return latest
