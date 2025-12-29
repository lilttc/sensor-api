"""
meteo_service.py - Domain logic for meteo data access and aggregation.

This module implements the service layer between:
- the persistence layer (db/repo.py)
- the API layer (api/router.py)

Responsibilities:
- Query measurements from the database
- Perform time-window filtering
- Resample and aggregate data (24h / 7d)
- Shape results into API-ready dictionaries

This module intentionally:
- does NOT contain FastAPI code
- does NOT contain SQL or persistence logic
- does NOT define API schemas

All timestamps are assumed to be UTC.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import pandas as pd
from sqlmodel import Session

from src.db.repo import get_latest_per_parameter, get_measurements_window, get_max_ts
from src.services.aggregations import (
    averages_per_parameter,
    measurements_to_df,
    resample_per_parameter,
    series_dict_from_df,
)


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


def _resolve_end(session: Session, *, sensor_id: str, end: Optional[datetime]) -> datetime:
    """
    Resolve the window end timestamp.

    If `end` is None, anchor to the latest timestamp available in the DB for this
    sensor (instead of "now"). This prevents empty 24h/7d windows when the dataset
    is historical.
    """
    if end is not None:
        return end

    latest = get_max_ts(session, sensor_id=sensor_id)
    return latest if latest is not None else _utc_now()


def get_current_weather(session: Session, *, sensor_id: str) -> Dict[str, Any]:
    """Retrieve the latest measurement per parameter for a sensor."""
    latest = get_latest_per_parameter(session, sensor_id=sensor_id)
    if not latest:
        return {"sensor_id": sensor_id, "as_of": None, "values": {}}

    as_of = max(m.ts for m in latest.values())
    values = {param: m.value for param, m in latest.items() if m.value is not None}
    return {"sensor_id": sensor_id, "as_of": as_of, "values": values}


def get_window(
    session: Session,
    *,
    sensor_id: str,
    start: datetime,
    end: datetime,
    parameters: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Fetch raw measurements in [start, end) and return a normalized DataFrame."""
    ms = get_measurements_window(
        session,
        sensor_id=sensor_id,
        start=start,
        end=end,
        parameters=parameters,
    ) or []
    return measurements_to_df(ms)


def get_24h_series(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """24-hour time series with 15-minute resolution (mean per bucket)."""
    end = _resolve_end(session, sensor_id=sensor_id, end=end)
    start = end - timedelta(hours=24)

    df = get_window(session, sensor_id=sensor_id, start=start, end=end, parameters=parameters)
    df_resampled = resample_per_parameter(df, freq="15min", how="mean")

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end,
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
    """24-hour averages per parameter."""
    end = _resolve_end(session, sensor_id=sensor_id, end=end)
    start = end - timedelta(hours=24)

    df = get_window(session, sensor_id=sensor_id, start=start, end=end, parameters=parameters)
    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end,
        "averages": averages_per_parameter(df),
    }


def get_7d_series(
    session: Session,
    *,
    sensor_id: str,
    end: Optional[datetime] = None,
    parameters: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """7-day time series with daily resolution (mean per day)."""
    end = _resolve_end(session, sensor_id=sensor_id, end=end)
    start = end - timedelta(days=7)

    df = get_window(session, sensor_id=sensor_id, start=start, end=end, parameters=parameters)
    df_resampled = resample_per_parameter(df, freq="1D", how="mean")

    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end,
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
    """7-day averages per parameter."""
    end = _resolve_end(session, sensor_id=sensor_id, end=end)
    start = end - timedelta(days=7)

    df = get_window(session, sensor_id=sensor_id, start=start, end=end, parameters=parameters)
    return {
        "sensor_id": sensor_id,
        "from": start,
        "to": end,
        "averages": averages_per_parameter(df),
    }