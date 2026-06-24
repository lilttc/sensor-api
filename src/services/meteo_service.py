"""
meteo_service.py - Domain logic for meteo data access and aggregation.

This module implements the service layer between:
- persistence (src/db/repo.py)
- API layer (src/api/router.py)

Responsibilities
---------------
- Resolve query windows (end anchoring, 24h/7d ranges)
- Query measurements from the database
- Delegate aggregation/resampling to src/services/aggregations.py
- Shape results into API-ready dictionaries

Design notes
------------
- This module contains no FastAPI code and no SQL.
- All "business logic" lives here (window semantics, response shaping).
- Aggregation math is delegated to aggregations.py.
- Timestamps are treated as UTC. For historical datasets, windows are anchored to
  the latest timestamp available in the DB instead of "now".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlmodel import Session

from src.db.repo import get_latest_per_parameter, get_max_ts, get_measurements_window
from src.services.aggregations import (
    averages_per_parameter,
    measurements_to_df,
    resample_per_parameter,
    series_dict_from_df,
)


# ---------------------------------------------------------------------------
# Time helpers / window semantics
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    """
    Return current UTC time.

    Returns
    -------
    datetime
        Timezone-aware datetime in UTC.
    """
    return datetime.now(timezone.utc)


def _resolve_end(session: Session, *, sensor_id: str, end: Optional[datetime]) -> datetime:
    """
    Resolve the window end timestamp.

    If the caller does not provide `end`, anchor to the latest timestamp in the DB
    for this sensor. This prevents empty windows when running on historical data.

    Parameters
    ----------
    session : Session
        Active DB session.
    sensor_id : str
        Sensor identifier.
    end : Optional[datetime]
        Optional end bound.

    Returns
    -------
    datetime
        End timestamp to use (UTC). If DB has no data for sensor, falls back to now.
    """
    if end is not None:
        return end

    latest = get_max_ts(session, sensor_id=sensor_id)
    return latest if latest is not None else _utc_now()


def _floor_to_day(dt: datetime) -> datetime:
    """
    Floor a datetime to the start of its day.

    Parameters
    ----------
    dt : datetime

    Returns
    -------
    datetime
        dt at 00:00:00 (preserves tzinfo if present).
    """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _compute_window(
    session: Session,
    *,
    sensor_id: str,
    horizon: str,
    end: Optional[datetime],
) -> Tuple[datetime, datetime]:
    """
    Compute (start, end) for a time horizon.

    Horizon semantics
    -----------------
    - "24h":
        For the sample data (often 1 snapshot/day), a strict
        end-24h window can be empty due to seconds-level jitter. We therefore use
        a *calendar-day window* that captures the previous day and current day
        around the latest available snapshot.

        Specifically:
          end_anchor = resolved end (latest ts in DB)
          day_start = floor(end_anchor)
          start = day_start - 1 day
          end = day_start + 1 day

        This yields up to ~2 daily snapshots, which makes the endpoint useful and
        robust for sparse data, while still representing a "24h-ish" view.

    - "7d":
        A standard trailing 7-day window from the anchored end:
          start = end - 7 days

    Parameters
    ----------
    session : Session
        Active DB session.
    sensor_id : str
        Sensor identifier.
    horizon : str
        Either "24h" or "7d".
    end : Optional[datetime]
        Optional end bound.

    Returns
    -------
    (datetime, datetime)
        (start, end) bounds for querying the DB.
    """
    end_anchor = _resolve_end(session, sensor_id=sensor_id, end=end)

    if horizon == "24h":
        day_start = _floor_to_day(end_anchor)
        start = day_start - timedelta(days=1)
        end_out = day_start + timedelta(days=1)
        return start, end_out

    if horizon == "7d":
        start = end_anchor - timedelta(days=7)
        return start, end_anchor

    raise ValueError(f"Unknown horizon: {horizon!r}")


# ---------------------------------------------------------------------------
# DB access (thin)
# ---------------------------------------------------------------------------

def _fetch_window_df(
    session: Session,
    *,
    sensor_id: str,
    start: datetime,
    end: datetime,
    parameters: Optional[list[str]],
):
    """
    Fetch measurements in a window and return a normalized DataFrame.

    Returns an empty DataFrame with the expected schema when no data exists.
    """
    ms = get_measurements_window(
        session,
        sensor_id=sensor_id,
        start=start,
        end=end,
        parameters=parameters,
    ) or []
    return measurements_to_df(ms)


# ---------------------------------------------------------------------------
# Public service API
# ---------------------------------------------------------------------------

def get_current_weather(session: Session, *, sensor_id: str) -> Dict[str, Any]:
    """
    Latest value per parameter for a sensor.

    Returns
    -------
    Dict[str, Any]
        {
          "sensor_id": "...",
          "as_of": datetime | None,
          "values": { "<parameter>": <value>, ... }
        }
    """
    latest = get_latest_per_parameter(session, sensor_id=sensor_id)
    if not latest:
        return {"sensor_id": sensor_id, "as_of": None, "values": {}}

    as_of = max(m.ts for m in latest.values())
    values = {param: m.value for param, m in latest.items() if m.value is not None}
    return {"sensor_id": sensor_id, "as_of": as_of, "values": values}


def get_24h_series(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    "24h" time series with 15-minute resolution.

    Notes
    -----
    With sparse sample data (often 1 snapshot/day), resampling at 15 minutes will
    produce only a small number of buckets. We use `how="last"` to keep the series
    intuitive (carry the last observed value in each bucket that has data).
    """
    start, end_out = _compute_window(session, sensor_id=sensor_id, horizon="24h", end=end)
    df = _fetch_window_df(session, sensor_id=sensor_id, start=start, end=end_out, parameters=parameters)

    df_resampled = resample_per_parameter(df, freq="15min", how="last")

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end_out,
        "resolution": "15min",
        "series": series_dict_from_df(df_resampled),
    }


def get_24h_average(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    "24h" averages per parameter.

    Uses the same window semantics as `get_24h_series`.
    """
    start, end_out = _compute_window(session, sensor_id=sensor_id, horizon="24h", end=end)
    df = _fetch_window_df(session, sensor_id=sensor_id, start=start, end=end_out, parameters=parameters)

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end_out,
        "averages": averages_per_parameter(df),
    }


def get_7d_series(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    7-day time series with daily resolution (mean per day).
    """
    start, end_out = _compute_window(session, sensor_id=sensor_id, horizon="7d", end=end)
    df = _fetch_window_df(session, sensor_id=sensor_id, start=start, end=end_out, parameters=parameters)

    df_resampled = resample_per_parameter(df, freq="1D", how="mean")

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end_out,
        "resolution": "1D",
        "series": series_dict_from_df(df_resampled),
    }


def get_7d_average(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    7-day averages per parameter.
    """
    start, end_out = _compute_window(session, sensor_id=sensor_id, horizon="7d", end=end)
    df = _fetch_window_df(session, sensor_id=sensor_id, start=start, end=end_out, parameters=parameters)

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end_out,
        "averages": averages_per_parameter(df),
    }
