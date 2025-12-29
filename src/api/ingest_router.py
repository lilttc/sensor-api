"""
ingest_router.py - API routes for bulk ingestion.

This provides a minimal way to ingest raw meteo files in bulk via HTTP.
It is intentionally simple for the assignment: it triggers ingestion of a
directory on disk (the sample dataset).
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.ingestion.ingest_to_db import ingest_meteo_dir_to_db

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/meteo",
    summary="Bulk ingest meteo JSON files into SQLite",
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
    - In production, you'd ingest via file upload, object storage, or a message queue.
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
