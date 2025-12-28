"""
loader.py - File discovery and metadata extraction for meteo ingestion.

This module is responsible for:
- Discovering meteo JSON files on disk
- Extracting metadata (month, day, sensor_id) from file paths
- Yielding strongly-typed file descriptors used by the ingestion pipeline

It deliberately contains no parsing or data transformation logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Tuple
import re
import logging
logger = logging.getLogger(__name__)

# Matches filenames like: meteo-0037.json
METEO_FILE_RE = re.compile(r"meteo-(\d+)\.json$", re.IGNORECASE)


@dataclass(frozen=True)
class MeteoFile:
    """
    Descriptor for a single meteo JSON file discovered on disk.

    Attributes
    ----------
    path : Path
        Absolute path to the meteo JSON file.
    month : str
        Month component inferred from the directory structure (e.g. "may").
    day : str
        Day component inferred from the directory structure (e.g. "12").
    sensor_id : str
        Sensor identifier extracted from the filename (e.g. "0037").
    """
    path: Path
    month: str
    day: str
    sensor_id: str


def extract_sensor_id(path: Path) -> str:
    """
    Extract the sensor ID from a meteo filename.

    Expected filename format:
        meteo-<sensor_id>.json

    Parameters
    ----------
    path : Path
        Path to a meteo JSON file.

    Returns
    -------
    str
        Extracted sensor ID.

    Raises
    ------
    ValueError
        If the filename does not match the expected pattern.
    """
    m = METEO_FILE_RE.search(path.name)
    if not m:
        raise ValueError(f"Unrecognized meteo filename format: {path.name}")
    return m.group(1)


def iter_meteo_paths(data_root: Path) -> Iterator[Path]:
    """
    Yield all meteo JSON file paths under a root directory.

    This function performs recursive discovery and works for both:
      - data/
      - data/may/

    Parameters
    ----------
    data_root : Path
        Root directory to search under.

    Yields
    ------
    Path
        Path to a discovered meteo JSON file.
    """
    data_root = data_root.resolve()
    yield from data_root.rglob("meteo-*.json")


def path_to_metadata(fpath: Path) -> Tuple[str, str, str]:
    """
    Infer (month, day, sensor_id) from a meteo file path.

    Expected directory structure:
        .../<month>/<day>/meteo-XXXX.json

    Example:
        data/may/12/meteo-0037.json
        -> ("may", "12", "0037")

    If data_root is passed as data/may, the month is still resolved
    from the parent directory.

    Parameters
    ----------
    fpath : Path
        Path to a meteo JSON file.

    Returns
    -------
    Tuple[str, str, str]
        (month, day, sensor_id)

    Raises
    ------
    ValueError
        If the filename format is invalid.
    """
    sensor_id = extract_sensor_id(fpath)
    day = fpath.parent.name
    month = fpath.parent.parent.name  # expects .../<month>/<day>/<file>
    return month, day, sensor_id


def iter_meteo_files(data_root: Path) -> Iterator[MeteoFile]:
    """
    Yield MeteoFile descriptors for all valid meteo JSON files under a root directory.

    Files that do not conform to the expected directory or filename structure
    are silently skipped.

    Parameters
    ----------
    data_root : Path
        Root directory to search under.

    Yields
    ------
    MeteoFile
        Structured descriptor containing file path and extracted metadata.
    """
    for fpath in sorted(iter_meteo_paths(data_root)):
        try:
            month, day, sensor_id = path_to_metadata(fpath)
        except Exception:
            logger.debug("Skipping unexpected path: %s", fpath)
            continue
        yield MeteoFile(
            path=fpath,
            month=month,
            day=day,
            sensor_id=sensor_id,
        )
