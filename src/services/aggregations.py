"""
aggregations.py - Pure aggregation utilities for meteo time-series.

This module contains stateless functions used by the service layer to:
- normalize DB rows into tabular form
- resample/bucket time series to fixed resolutions
- compute per-parameter aggregates

No database access and no FastAPI code should live here.
"""

from typing import Any, Dict, Iterable, Literal

import pandas as pd

from src.db.models import Measurement


def measurements_to_df(measurements: Iterable[Measurement]) -> pd.DataFrame:
    """
    Convert Measurement rows to a normalized DataFrame.

    Returns a DataFrame with columns: ts, parameter, value.
    If there are no usable rows, returns an empty DataFrame *with those columns*.
    """
    rows = [
        {"ts": m.ts, "parameter": m.parameter, "value": m.value}
        for m in measurements
        if m.value is not None
    ]

    if not rows:
        return pd.DataFrame(columns=["ts", "parameter", "value"])

    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    df = df.dropna(subset=["ts", "parameter", "value"])
    return df


def resample_per_parameter(
    df: pd.DataFrame,
    *,
    freq: str,
    how: Literal["mean", "last"] = "mean",
) -> pd.DataFrame:
    """
    Resample a normalized DataFrame per parameter.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: ts, parameter, value. ts should be UTC datetime.
    freq : str
        Pandas frequency string, e.g. "15min", "1D".
    how : {"mean", "last"}
        Aggregation function applied per bucket.

    Returns
    -------
    pd.DataFrame
        Resampled DataFrame with columns: ts, parameter, value.
    """
    if df.empty:
        return pd.DataFrame(columns=["ts", "parameter", "value"])

    agg = "mean" if how == "mean" else "last"

    pieces: list[pd.DataFrame] = []
    for param, g in df.groupby("parameter", sort=False):
        g = g.set_index("ts").sort_index()
        s = g["value"].resample(freq).agg(agg).dropna()
        pieces.append(pd.DataFrame({"ts": s.index, "parameter": param, "value": s.values}))

    if not pieces:
        return pd.DataFrame(columns=["ts", "parameter", "value"])

    return pd.concat(pieces, ignore_index=True)


def averages_per_parameter(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute mean value per parameter over the provided DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Normalized DataFrame with columns: parameter, value.

    Returns
    -------
    Dict[str, float]
        Mapping parameter -> mean(value).
    """
    if df.empty:
        return {}
    avg = df.groupby("parameter")["value"].mean().to_dict()
    return {k: float(v) for k, v in avg.items()}


def series_dict_from_df(df: pd.DataFrame) -> Dict[str, list[dict[str, Any]]]:
    """
    Convert a normalized DataFrame to API-friendly dict-of-series.

    Output:
      {
        "<parameter>": [{"ts": datetime, "value": float}, ...],
        ...
      }
    """
    out: Dict[str, list[dict[str, Any]]] = {}
    if df.empty:
        return out

    df = df.sort_values("ts")
    for param, g in df.groupby("parameter", sort=False):
        out[param] = [
            {"ts": ts.to_pydatetime(), "value": float(v)}
            for ts, v in zip(g["ts"], g["value"])
        ]
    return out
