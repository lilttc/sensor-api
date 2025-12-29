"""
ingest_to_db.py - Bulk ingestion of meteo JSON files into SQLite.

This module provides a single entry point used by:
- CLI scripts
- API bulk ingest endpoint

It:
- walks the meteo JSON files
- parses each file
- converts parsed records to Measurement rows
- upserts them into SQLite in batches
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from src.db.models import Measurement
from src.db.repo import bulk_upsert_measurements, ensure_indexes
from src.db.session import engine, init_db
from src.ingestion.loader import iter_meteo_files
from src.ingestion.parser import parse_meteo_json_file
from src.ingestion.transform import wide_record_to_measurements


@dataclass(frozen=True)
class IngestStats:
    """Summary stats returned by bulk ingestion."""
    processed_files: int
    parsed_records: int
    attempted_rows: int
    failures: int


def ingest_meteo_dir_to_db(
    data_root: Path,
    *,
    batch_size: int = 5000,
    limit_files: Optional[int] = None,
) -> IngestStats:
    """
    Ingest all meteo JSON files under `data_root` into the SQLite database.

    Parameters
    ----------
    data_root : Path
        Root folder containing meteo data (e.g. data/raw/may).
    batch_size : int
        Number of Measurement rows to upsert per batch.
    limit_files : Optional[int]
        Optional safety limit for number of files to ingest.

    Returns
    -------
    IngestStats
        Summary of processing, parsed records, attempted row upserts, and failures.
    """
    data_root = data_root.resolve()
    if not data_root.exists():
        raise FileNotFoundError(f"data_root does not exist: {data_root}")

    init_db()
    processed_files = 0
    parsed_records = 0
    attempted_rows = 0
    failures = 0

    with Session(engine) as session:
        ensure_indexes(session)

        batch: list[Measurement] = []

        for mf in iter_meteo_files(data_root):
            if limit_files is not None and processed_files >= limit_files:
                break

            processed_files += 1
            try:
                records = parse_meteo_json_file(
                    mf.path,
                    sensor_id=mf.sensor_id,
                    month=mf.month,
                    day=mf.day,
                )
                # parser returns list[dict]
                parsed_records += len(records)

                for r in records:
                    batch.extend(
                        wide_record_to_measurements(
                            r,
                            sensor_id=r["sensor_id"],
                            source_file=r.get("source_file"),
                        )
                    )

                if len(batch) >= batch_size:
                    attempted_rows += bulk_upsert_measurements(session, batch)
                    batch.clear()

            except Exception:
                failures += 1
                # swallow and continue — ingestion endpoint should be resilient
                continue

        if batch:
            attempted_rows += bulk_upsert_measurements(session, batch)
            batch.clear()

    return IngestStats(
        processed_files=processed_files,
        parsed_records=parsed_records,
        attempted_rows=attempted_rows,
        failures=failures,
    )
