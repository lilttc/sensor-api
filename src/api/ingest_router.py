"""
ingest_router.py - API routes for bulk ingestion.

This provides:
- /ingest/meteo : triggers ingestion of a directory on disk (assignment demo helper)
- /ingest/batch : bulk ingest raw meteo payloads via HTTP
"""

from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from src.db.session import get_session
from src.db.repo import bulk_upsert_measurements
from src.ingestion.ingest_to_db import ingest_meteo_dir_to_db
from src.ingestion.parser import parse_meteo_payload
from src.ingestion.transform import wide_record_to_measurements

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/meteo",
    summary="Bulk ingest meteo JSON files into SQLite (from disk)",
)
def ingest_meteo(
    data_root: str = Query("data/raw/may", description="Root folder containing meteo JSON files"),
    limit_files: Optional[int] = Query(None, description="Optional max files to ingest"),
) -> dict:
    """
    Trigger ingestion of meteo JSON files from a directory on disk.

    Notes
    -----
    - This is designed for local/demo usage in the assignment.
    - In production, you'd ingest via HTTP payloads, file upload, object storage, or a message queue.
    """
    try:
        stats = ingest_meteo_dir_to_db(Path(data_root), limit_files=limit_files)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return {
        "data_root": str(Path(data_root).resolve()),
        "processed_files": stats.processed_files,
        "parsed_records": stats.parsed_records,
        "attempted_rows": stats.attempted_rows,
        "failures": stats.failures,
    }


class MeteoBatchItem(BaseModel):
    """
    One raw meteo payload (similar to the JSON file contents), plus sensor_id.
    """
    sensor_id: str = Field(..., description="Sensor identifier")
    ts: str = Field(..., description="ISO-8601 timestamp string (e.g. 2021-05-01T02:02:50+02:00)")
    pt: int = Field(0, description="Point index (pt)")
    rows: List[List[Any]] = Field(..., description="Rows in ['Variable','Value'] format")
    name: Optional[str] = Field(None, description="Optional payload name")
    range: Optional[str] = Field(None, description="Optional payload range")
    source_file: Optional[str] = Field(None, description="Optional label for traceability (e.g. original filename)")


@router.post(
    "/batch",
    summary="Bulk ingest raw meteo payloads via HTTP",
)
def ingest_batch(
    items: List[MeteoBatchItem] = Body(..., description="List of raw meteo payloads"),
    session: Session = Depends(get_session),
) -> dict:
    """
    Bulk ingest meteo payloads via HTTP.

    This endpoint accepts a list of raw payloads (file-like structure) and writes
    measurements into SQLite using the same parse -> transform -> upsert pipeline.
    """
    received_payloads = len(items)
    parsed_records = 0
    attempted_rows = 0
    failures = 0

    for item in items:
        try:
            raw = {
                "name": item.name or "_ws_source_meteo",
                "range": item.range or "",
                "ts": item.ts,
                "pt": item.pt,
                "rows": item.rows,
            }

            records = parse_meteo_payload(
                raw,
                sensor_id=item.sensor_id,
                source_file=item.source_file or "<http>",
            )
            parsed_records += len(records)

            for r in records:
                measurements = list(wide_record_to_measurements(r))
                attempted_rows += bulk_upsert_measurements(session, measurements)

        except Exception:
            failures += 1
            continue

    return {
        "received_payloads": received_payloads,
        "parsed_records": parsed_records,
        "attempted_rows": attempted_rows,
        "failures": failures,
    }
