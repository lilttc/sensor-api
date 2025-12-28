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
from typing import Any, Dict, Iterable, List, Mapping, Tuple


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

    Parameters
    ----------
    path : Path
        File path to the JSON file.

    Returns
    -------
    Dict[str, Any]
        Parsed JSON object.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_rows(data: Mapping[str, Any], *, path: Path) -> List[List[Any]]:
    """
    Extract and validate the `rows` array from a meteo JSON object.

    Expected shape:
        {
          ...,
          "rows": [
            ["Variable", "Value"],
            ["external_temperature_c", 11.4],
            ...
          ]
        }

    Raises
    ------
    ValueError
        If `rows` is missing/empty or the header is malformed.
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

    Returns
    -------
    (variable_index, value_index)

    Raises
    ------
    ValueError
        If required columns are missing.
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

    Behavior per variable:
    - If at least one non-missing value appears, keep the last non-missing one.
    - Otherwise (all missing), keep the last seen missing value.
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


def parse_meteo_json_file(
    path: Path,
    *,
    sensor_id: str,
    month: str,
    day: str,
) -> List[Dict[str, Any]]:
    """
    Parse a single meteo-XXXX.json file into one wide record dict (pure Python).

    In addition to `rows`, the file contains:
      - ts: ISO-8601 timestamp string (timezone-aware)
      - pt: point index (often 0 in sample data)

    Input JSON expected:
        {
          "ts": "2021-05-01T02:02:50+02:00",
          "pt": 0,
          "rows": [["Variable","Value"], ["external_temperature_c", 11.4], ...]
        }

    Processing steps:
    1. Load JSON, extract file-level metadata (ts, pt)
    2. Validate rows/header and extract (variable, value) pairs
    3. Deduplicate per variable (keep last non-missing; otherwise last missing)
    4. Flatten enum-like dict values into scalar + namespaced metadata columns
    5. Attach metadata keys: ts, pt, sensor_id, month, day, source_file

    Returns
    -------
    List[Dict[str, Any]]
        A list of parsed record(s). For the current data format, this list
        contains exactly one record per file.
    """
    data = _load_meteo_json(path)

    ts = data.get("ts")
    pt = data.get("pt")

    rows = _extract_rows(data, path=path)
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
