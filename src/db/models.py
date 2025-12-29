"""
models.py - Database models for meteo measurements.

This module defines the persistent storage schema using SQLModel.
It contains only database-facing models and no business logic.

Design notes:
- Measurements are stored in *long format*:
    one row = one parameter value at one timestamp.
- This keeps the schema flexible: adding new sensor parameters
  does not require schema migrations.
- Uniqueness and indexing are enforced at the database level
  (see repo.py), not in application logic.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Measurement(SQLModel, table=True):
    """
    A single timestamped measurement for one sensor parameter.

    Each row represents:
        - one sensor
        - one timestamp
        - one measured parameter (e.g. temperature, wind speed)
        - one numeric value

    The table is intentionally normalized (long format) to support:
    - flexible schema evolution
    - efficient time-window queries
    - simple aggregation across parameters and time ranges
    """

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Surrogate primary key."
    )

    sensor_id: str = Field(
        index=True,
        description="Identifier of the sensor/station producing the measurement."
    )

    ts: datetime = Field(
        index=True,
        description="Timestamp of the measurement (stored as UTC datetime)."
    )

    parameter: str = Field(
        index=True,
        description="Name of the measured parameter (e.g. 'external_temperature_c')."
    )

    value: Optional[float] = Field(
        default=None,
        description="Numeric value of the measurement, if available."
    )

    pt: int = Field(
        default=0,
        index=True,
        description="Point index within the source file (usually 0 for current data)."
    )

    source_file: Optional[str] = Field(
        default=None,
        description="Name of the source JSON file the measurement originated from."
    )

    # NOTE:
    # Uniqueness is enforced via a database-level unique index:
    #   (sensor_id, ts, parameter, pt)
    #
    # This is created in repo.ensure_indexes().
    # We intentionally avoid inline SQLAlchemy constraints here to keep
    # SQLModel definitions simple and SQLite-friendly.
