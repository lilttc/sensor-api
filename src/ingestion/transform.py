"""
transform.py - Ingestion-layer transformations for meteo data.

This module defines how parsed *wide* meteo records (one dict per file)
are transformed into *long-format* Measurement rows suitable for storage
in the database.

Responsibilities:
- Map parsed records to the storage schema
- Enforce basic validation (timestamp, sensor_id)
- Filter metadata and helper fields
- Coerce values into numeric form where possible

This module is intentionally free of:
- file I/O
- database session management
- business logic or aggregations
"""

from typing import Any, Dict, Iterable, Set

import pandas as pd

from src.db.models import Measurement


META_KEYS: Set[str] = {
    "ts",
    "pt",
    "sensor_id",
    "month",
    "day",
    "source_file",
}
"""
Keys in a parsed record that represent metadata rather than measured parameters.

These keys are excluded when converting wide records to long-format
Measurement rows.
"""


def wide_record_to_measurements(record: Dict[str, Any]) -> Iterable[Measurement]:
    """
    Convert a single wide parsed record into long-format Measurement rows.

    A *wide record* is produced by `parser.parse_meteo_json_file` and contains:
    - metadata (timestamp, sensor_id, file info)
    - many sensor variables as key/value pairs

    This function converts that structure into one Measurement row per
    (parameter, value) pair.

    Transformation rules:
    - `record["ts"]` is parsed into a UTC-aware datetime
    - `record["sensor_id"]` is required and cast to string
    - Metadata fields (META_KEYS) are skipped
    - Enum helper fields (e.g. "*_type") are skipped
    - Values are coerced to float; non-numeric values are ignored

    Parameters
    ----------
    record : Dict[str, Any]
        Parsed wide record from `parse_meteo_json_file`.

    Yields
    ------
    Measurement
        Long-format measurement rows suitable for database upsert.

    Raises
    ------
    ValueError
        If required metadata (timestamp or sensor_id) is missing or invalid.
    """
    ts_raw = record.get("ts")
    if ts_raw is None:
        raise ValueError("Record missing 'ts'")

    ts = pd.to_datetime(ts_raw, utc=True, errors="raise").to_pydatetime().replace(tzinfo=None)
    if pd.isna(ts):
        raise ValueError(f"Unparseable ts: {ts_raw!r}")

    sensor_id = str(record.get("sensor_id"))
    if not sensor_id or sensor_id == "None":
        raise ValueError("Record missing 'sensor_id'")

    pt = int(record.get("pt") or 0)
    source_file = record.get("source_file")

    for key, val in record.items():
        if key in META_KEYS:
            continue
        if key.endswith("_type"):
            continue

        # Attempt numeric coercion; skip non-numeric values
        try:
            value = None if val is None else float(val)
        except (TypeError, ValueError):
            continue

        yield Measurement(
            sensor_id=sensor_id,
            ts=ts,
            parameter=key,
            value=value,
            pt=pt,
            source_file=source_file,
        )
