"""
router.py - API routes for meteo data.

This module defines HTTP endpoints for retrieving:
- current weather values
- 24-hour and 7-day time series
- 24-hour and 7-day averages

It delegates all business logic to the service layer and
uses Pydantic schemas to define the API contract.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from src.api.schemas import (
    AveragesResponse,
    CurrentWeatherResponse,
    TimeSeriesResponse,
)
from src.db.session import get_session
from src.services import meteo_service

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get(
    "/current",
    response_model=CurrentWeatherResponse,
    summary="Get current weather values",
)
def get_current_weather(
    sensor_id: str = Query(..., description="Sensor identifier"),
    session: Session = Depends(get_session),
) -> CurrentWeatherResponse:
    """
    Return the latest available value per parameter for a sensor.
    """
    result = meteo_service.get_current_weather(
        session=session,
        sensor_id=sensor_id,
    )
    return CurrentWeatherResponse(**result)


@router.get(
    "/24h/series",
    response_model=TimeSeriesResponse,
    summary="Get 24h weather time series (15-minute resolution)",
)
def get_24h_series(
    sensor_id: str = Query(..., description="Sensor identifier"),
    parameters: Optional[List[str]] = Query(
        None,
        description="Optional list of parameters to include",
    ),
    end: Optional[datetime] = Query(
        None,
        description="Optional end timestamp (defaults to now, UTC)",
    ),
    session: Session = Depends(get_session),
) -> TimeSeriesResponse:
    """
    Return a 24-hour time series aggregated at 15-minute resolution.
    """
    result = meteo_service.get_24h_series(
        session=session,
        sensor_id=sensor_id,
        end=end,
        parameters=parameters,
    )
    return TimeSeriesResponse(**result)


@router.get(
    "/24h/avg",
    response_model=AveragesResponse,
    summary="Get 24h average weather values",
)
def get_24h_average(
    sensor_id: str = Query(..., description="Sensor identifier"),
    parameters: Optional[List[str]] = Query(
        None,
        description="Optional list of parameters to include",
    ),
    end: Optional[datetime] = Query(
        None,
        description="Optional end timestamp (defaults to now, UTC)",
    ),
    session: Session = Depends(get_session),
) -> AveragesResponse:
    """
    Return 24-hour average values per parameter.
    """
    result = meteo_service.get_24h_average(
        session=session,
        sensor_id=sensor_id,
        end=end,
        parameters=parameters,
    )
    return AveragesResponse(**result)


@router.get(
    "/7d/series",
    response_model=TimeSeriesResponse,
    summary="Get 7-day weather time series (daily resolution)",
)
def get_7d_series(
    sensor_id: str = Query(..., description="Sensor identifier"),
    parameters: Optional[List[str]] = Query(
        None,
        description="Optional list of parameters to include",
    ),
    end: Optional[datetime] = Query(
        None,
        description="Optional end timestamp (defaults to now, UTC)",
    ),
    session: Session = Depends(get_session),
) -> TimeSeriesResponse:
    """
    Return a 7-day time series aggregated at daily resolution.
    """
    result = meteo_service.get_7d_series(
        session=session,
        sensor_id=sensor_id,
        end=end,
        parameters=parameters,
    )
    return TimeSeriesResponse(**result)


@router.get(
    "/7d/avg",
    response_model=AveragesResponse,
    summary="Get 7-day average weather values",
)
def get_7d_average(
    sensor_id: str = Query(..., description="Sensor identifier"),
    parameters: Optional[List[str]] = Query(
        None,
        description="Optional list of parameters to include",
    ),
    end: Optional[datetime] = Query(
        None,
        description="Optional end timestamp (defaults to now, UTC)",
    ),
    session: Session = Depends(get_session),
) -> AveragesResponse:
    """
    Return 7-day average values per parameter.
    """
    result = meteo_service.get_7d_average(
        session=session,
        sensor_id=sensor_id,
        end=end,
        parameters=parameters,
    )
    return AveragesResponse(**result)
