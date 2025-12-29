"""
ingest.py - End-to-end ingestion entry point for meteo JSON data.

This module orchestrates ingestion by:
- Discovering meteo JSON files on disk
- Parsing each file into one or more *wide* record dict(s)
- Converting wide records into *long* Measurement rows
- Upserting rows into a persistent SQLite database (via SQLModel/SQLAlchemy)

It is intentionally thin and delegates:
- file discovery → loader.py
- parsing → parser.py
- persistence → db/*
"""

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import pandas as pd
from sqlmodel import Session

from .loader import iter_meteo_files
from .parser import parse_meteo_json_file
from .transform import wide_record_to_measurements

from src.db.models import Measurement
from src.db.repo import bulk_upsert_measurements, ensure_indexes
from src.db.session import engine, init_db

logger = logging.getLogger(__name__)

META_KEYS: Set[str] = {"ts", "pt", "sensor_id", "month", "day", "source_file"}


def configure_logging(*, level: str = "INFO", log_file: Path | None = None) -> None:
    """
    Configure application logging.

    Parameters
    ----------
    level : str
        Logging level name (e.g. "DEBUG", "INFO", "WARNING").
    log_file : Path | None
        Optional file path to also write logs to (in addition to stderr).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

def run_ingestion_to_db(data_root: Path) -> None:
    """
    Run ingestion over a directory of meteo JSON files and persist into SQLite.

    Steps:
    1. Initialize DB tables
    2. Ensure indexes/unique constraints exist
    3. Discover and parse meteo JSON files
    4. Convert parsed records (wide) to long Measurement rows
    5. Bulk upsert into DB

    Parameters
    ----------
    data_root : Path
        Root directory containing meteo data.
    """
    data_root = data_root.resolve()
    if not data_root.exists():
        raise FileNotFoundError(f"data_root does not exist: {data_root}")

    logger.info("Starting DB ingestion. data_root=%s", data_root)

    init_db()
    with Session(engine) as session:
        ensure_indexes(session)

        processed_files = 0
        failures = 0
        attempted_rows = 0

        for meteo_file in iter_meteo_files(data_root):
            processed_files += 1
            logger.debug(
                "Processing file=%s sensor_id=%s month=%s day=%s",
                meteo_file.path,
                meteo_file.sensor_id,
                meteo_file.month,
                meteo_file.day,
            )

            try:
                records = parse_meteo_json_file(
                    meteo_file.path,
                    sensor_id=meteo_file.sensor_id,
                    month=meteo_file.month,
                    day=meteo_file.day,
                )
                if not isinstance(records, list):
                    raise TypeError(f"Parser should return list[dict], got {type(records)}")

                measurements: List[Measurement] = []
                for rec in records:
                    measurements.extend(list(wide_record_to_measurements(rec)))

                attempted_rows += bulk_upsert_measurements(session, measurements)

            except Exception:
                failures += 1
                logger.exception("Failed to ingest file=%s", meteo_file.path)

        logger.info(
            "DB ingestion finished. files_processed=%d failures=%d rows_attempted=%d",
            processed_files,
            failures,
            attempted_rows,
        )


def main() -> None:
    """
    CLI entry point for running ingestion locally.

    - Configures logging
    - Runs ingestion into SQLite DB
    """
    configure_logging(level="INFO", log_file=Path("data/outputs/ingest.log"))

    data_root = Path("data/raw/may")
    logger.info("CWD=%s", Path.cwd())
    logger.info("Using data_root=%s exists=%s", data_root.resolve(), data_root.exists())

    run_ingestion_to_db(data_root)


if __name__ == "__main__":
    main()
