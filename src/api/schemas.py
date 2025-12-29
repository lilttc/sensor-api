"""
schemas.py - API request/response models.

These schemas define the public API contract exposed by the FastAPI layer.
They are intentionally decoupled from the database models (SQLModel) so the
API can evolve independently of storage details.

Timestamps are represented as timezone-aware datetimes (UTC recommended).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SeriesPoint(BaseModel):
    """
    A single point in a time series.
    """
    ts: datetime = Field(..., description="Timestamp of the point (timezone-aware).")
    value: float = Field(..., description="Numeric value at timestamp.")


class CurrentWeatherResponse(BaseModel):
    """
    Latest (most recent) value per parameter for a sensor.
    """
    sensor_id: str = Field(..., description="Sensor identifier.")
    as_of: Optional[datetime] = Field(
        None, description="Timestamp of the latest observation across returned parameters."
    )
    values: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of parameter name to latest numeric value.",
    )


class TimeSeriesResponse(BaseModel):
    """
    Parameter-keyed time series response over a time window.
    """
    sensor_id: str = Field(..., description="Sensor identifier.")
    from_: datetime = Field(..., alias="from", description="Inclusive window start (timezone-aware).")
    to: datetime = Field(..., description="Exclusive window end (timezone-aware).")
    resolution: str = Field(..., description="Series resolution, e.g. '15min' or '1D'.")
    series: Dict[str, List[SeriesPoint]] = Field(
        default_factory=dict,
        description="Mapping of parameter name to list of time series points.",
    )

    class Config:
        populate_by_name = True  # allow using from_ in python while exposing 'from' in JSON


class AveragesResponse(BaseModel):
    """
    Average value per parameter over a time window.
    """
    sensor_id: str = Field(..., description="Sensor identifier.")
    from_: datetime = Field(..., alias="from", description="Inclusive window start (timezone-aware).")
    to: datetime = Field(..., description="Exclusive window end (timezone-aware).")
    averages: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of parameter name to average value over the window.",
    )

    class Config:
        populate_by_name = True
