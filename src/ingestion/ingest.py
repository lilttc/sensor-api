"""
ingest.py - End-to-end ingestion entry point for meteo JSON data.

This module orchestrates the ingestion pipeline by:
- Discovering meteo JSON files on disk
- Parsing each file into one or more structured records
- Aggregating all records into a single pandas DataFrame
- Optionally writing the result to disk for inspection

It is intentionally thin and delegates:
- file discovery → loader.py
- parsing & normalization → parser.py
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .loader import iter_meteo_files
from .parser import parse_meteo_json_file

logger = logging.getLogger(__name__)


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


def run_ingestion(data_root: Path) -> pd.DataFrame:
    """
    Run ingestion over a directory of meteo JSON files.

    Steps:
    1. Discover meteo JSON files under `data_root`
    2. Parse each file into record dict(s)
    3. Aggregate records into a DataFrame
    4. Normalize `ts` to timezone-aware UTC datetime if present

    Parameters
    ----------
    data_root : Path
        Root directory containing meteo data.

    Returns
    -------
    pd.DataFrame
        DataFrame containing all successfully parsed records.
    """
    data_root = data_root.resolve()
    if not data_root.exists():
        raise FileNotFoundError(f"data_root does not exist: {data_root}")

    all_records: List[Dict[str, Any]] = []
    failures = 0
    processed = 0

    logger.info("Starting ingestion. data_root=%s", data_root)

    for meteo_file in iter_meteo_files(data_root):
        processed += 1
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

            all_records.extend(records)

        except Exception:
            failures += 1
            logger.exception("Failed to parse file=%s", meteo_file.path)

    df = pd.DataFrame(all_records)

    # Normalize timestamp if present
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce", utc=True)

    logger.info(
        "Ingestion finished. processed=%d parsed_records=%d failures=%d df_shape=%s",
        processed,
        len(all_records),
        failures,
        df.shape,
    )
    return df


def main() -> None:
    """
    CLI entry point for running ingestion locally.

    - Configures logging
    - Runs ingestion
    - Writes the resulting DataFrame to CSV
    """
    configure_logging(level="INFO", log_file=Path("data/outputs/ingest.log"))

    data_root = Path("data/raw/may")
    logger.info("CWD=%s", Path.cwd())
    logger.info("Using data_root=%s exists=%s", data_root.resolve(), data_root.exists())

    df = run_ingestion(data_root)

    logger.info("Preview head:\n%s", df.head())
    logger.info("DataFrame shape: %s", df.shape)

    out_dir = Path("data/outputs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "meteo_may.csv"
    df.to_csv(out_path, index=False)

    logger.info("Wrote %s", out_path.resolve())


if __name__ == "__main__":
    main()
