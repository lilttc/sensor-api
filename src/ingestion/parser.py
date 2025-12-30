"""
parser.py - Pure-Python parsers for Source.ag meteo JSON sample files.

This module intentionally avoids pandas to keep ingestion lightweight and
easy to reason about. The input JSON files are small, and their structure
(`rows` with ["Variable","Value"] pairs) maps naturally to a dictionary.

Key behaviors:
- Validates input shape.
- Cleans variable names.
- Handles duplicates by keeping the last non-missing value (or last seen if all missing).
- Flattens enum-like dict values into scalar + namespaced metadata columns.
- Extracts file-level timestamp metadata ("ts") and point index ("pt").
- Adds metadata (sensor_id, month, day, source_file) to each parsed record.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple, Optional
from datetime import datetime

VARIABLE_COL = "Variable"
VALUE_COL = "Value"


def _is_missing(v: Any) -> bool:
    """
    Return True if a value should be treated as missing.

    Missing values include:
    - None
    - NaN (float('nan'))
    - empty / whitespace-only strings
    """
    if v is None:
        return True
    if isinstance(v, float) and v != v:  # NaN check without pandas
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _flatten_dict_values(record: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Flatten dict-valued fields in a record into scalar columns.

    This is primarily used for enum-like values of the form:
        {"type": "...", "key": 123, "value": "W"}

    Flattening rules:
    - If the dict contains a "value" key, the base field is set to that value
    - All other keys are added as namespaced fields: <field>_<subkey>
    """
    out: Dict[str, Any] = {}

    for field, value in record.items():
        if not isinstance(value, dict):
            out[field] = value
            continue

        if "value" in value:
            out[field] = value.get("value")

        for sub_k, sub_v in value.items():
            if sub_k == "value":
                continue
            out[f"{field}_{sub_k}"] = sub_v

    return out


def _load_meteo_json(path: Path) -> Dict[str, Any]:
    """
    Load and return the raw JSON object for a meteo file.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_ts(data: Mapping[str, Any], *, path: Path) -> str:
    """
    Extract and validate the top-level timestamp ("ts").
    Returns an ISO-8601 string.
    """
    ts = data.get("ts")
    if ts is None:
        raise ValueError(f"Missing 'ts' in {path}")

    if isinstance(ts, datetime):
        return ts.isoformat()

    if not isinstance(ts, str) or ts.strip() == "":
        raise ValueError(f"Invalid 'ts' in {path}: {ts}")

    # Light validation: must be parseable ISO-8601 (accept Z)
    try:
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception as e:
        raise ValueError(f"Unparseable 'ts' in {path}: {ts}") from e

    return ts


def _extract_pt(data: Mapping[str, Any], *, path: Path) -> int:
    """
    Extract and validate the point index ("pt").
    """
    pt = data.get("pt")
    if pt is None:
        # In many cases it's always present, but defaulting here makes HTTP ingestion friendlier.
        return 0

    if isinstance(pt, bool):
        raise ValueError(f"Invalid 'pt' in {path}: {pt}")

    if isinstance(pt, int):
        return pt

    # Some payloads may provide pt as string
    if isinstance(pt, str) and pt.strip().isdigit():
        return int(pt.strip())

    raise ValueError(f"Invalid 'pt' in {path}: {pt}")


def _extract_rows(data: Mapping[str, Any], *, path: Path) -> List[List[Any]]:
    """
    Extract and validate the `rows` array from a meteo JSON object.
    """
    rows = data.get("rows")
    if not rows or not isinstance(rows, list) or len(rows) < 2:
        raise ValueError(f"Missing/empty 'rows' in {path}")

    header = rows[0]
    if not isinstance(header, list) or len(header) < 2:
        raise ValueError(f"Unexpected header row in {path}: {header}")

    return rows  # type: ignore[return-value]


def _parse_header(header: List[Any], *, path: Path) -> Tuple[int, int]:
    """
    Identify the indices of the Variable and Value columns in the header.
    """
    header_str = [str(c).strip() for c in header]
    try:
        var_i = header_str.index(VARIABLE_COL)
        val_i = header_str.index(VALUE_COL)
    except ValueError:
        raise ValueError(
            f"Expected header columns '{VARIABLE_COL}' and '{VALUE_COL}' in {path}, got {header_str}"
        )
    return var_i, val_i


def _dedupe_last_non_missing(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    """
    Deduplicate (variable, value) pairs, keeping the last non-missing value per variable.
    """
    out: Dict[str, Any] = {}
    last_missing: Dict[str, Any] = {}

    for var, val in pairs:
        if _is_missing(val):
            last_missing[var] = val
            continue
        out[var] = val  # overwrite => last non-missing wins

    for var, val in last_missing.items():
        if var not in out:
            out[var] = val

    return out


def _rows_to_record(rows: List[List[Any]], *, path: Path) -> Dict[str, Any]:
    """
    Convert rows into a wide record dict:
      - validate header
      - build (var, val) pairs
      - dedupe
      - flatten dict values
    """
    header = rows[0]
    var_i, val_i = _parse_header(header, path=path)

    pairs: List[Tuple[str, Any]] = []
    for r in rows[1:]:
        if not isinstance(r, list):
            continue
        if len(r) <= max(var_i, val_i):
            continue

        var = str(r[var_i]).strip()
        if not var:
            continue

        val = r[val_i]
        pairs.append((var, val))

    record = _dedupe_last_non_missing(pairs)
    record = _flatten_dict_values(record)
    return record


def parse_meteo_json_file(
    path: Path,
    *,
    sensor_id: str,
    month: str,
    day: str,
) -> List[Dict[str, Any]]:
    """
    Parse a single meteo-XXXX.json file into one wide record dict (pure Python).

    Returns a list with exactly one record for the current data format.
    """
    data = _load_meteo_json(path)

    ts = _extract_ts(data, path=path)
    pt = _extract_pt(data, path=path)

    rows = _extract_rows(data, path=path)
    record = _rows_to_record(rows, path=path)

    record.update(
        {
            "ts": ts,
            "pt": pt,
            "sensor_id": sensor_id,
            "month": month,
            "day": day,
            "source_file": path.name,
        }
    )

    return [record]


def parse_meteo_payload(
    data: Mapping[str, Any],
    *,
    sensor_id: str,
    source_file: str = "<http>",
    month: Optional[str] = None,
    day: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Parse an in-memory meteo JSON payload (already loaded dict) into one wide record.

    This mirrors parse_meteo_json_file() but is intended for HTTP ingestion.

    If month/day are not provided, they are derived from ts where possible.
    """
    path = Path(source_file)

    ts = _extract_ts(data, path=path)
    pt = _extract_pt(data, path=path)

    # Derive month/day from ts if not supplied
    if month is None or day is None:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if month is None:
                month = f"{dt.month:02d}"
            if day is None:
                day = f"{dt.day:02d}"
        except Exception:
            # Fall back to sentinel values; ingestion can still proceed
            month = month or "unknown"
            day = day or "unknown"

    rows = _extract_rows(data, path=path)
    record = _rows_to_record(rows, path=path)

    record.update(
        {
            "ts": ts,
            "pt": pt,
            "sensor_id": sensor_id,
            "month": month,
            "day": day,
            "source_file": source_file,
        }
    )

    return [record]
