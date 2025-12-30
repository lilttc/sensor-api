from datetime import datetime, timedelta, timezone

from src.db.models import Measurement
from src.services.aggregations import (
    measurements_to_df,
    resample_per_parameter,
    averages_per_parameter,
)


def test_resample_15min_and_average():
    base = datetime(2021, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    measurements = [
        Measurement(sensor_id="S1", ts=base + timedelta(minutes=0),  parameter="temp", value=10.0, pt=0),
        Measurement(sensor_id="S1", ts=base + timedelta(minutes=5),  parameter="temp", value=12.0, pt=0),
        Measurement(sensor_id="S1", ts=base + timedelta(minutes=20), parameter="temp", value=20.0, pt=0),
        Measurement(sensor_id="S1", ts=base + timedelta(minutes=0),  parameter="wind", value=1.0,  pt=0),
        Measurement(sensor_id="S1", ts=base + timedelta(minutes=15), parameter="wind", value=3.0,  pt=0),
    ]

    df = measurements_to_df(measurements)
    assert set(df["parameter"].unique()) == {"temp", "wind"}

    # 15-minute resample: temp should bucket (0-15) mean of 10 and 12 -> 11.0
    res = resample_per_parameter(df, freq="15min")
    temp_bucket = res[(res["parameter"] == "temp")].sort_values("ts").iloc[0]
    assert temp_bucket["value"] == 11.0

    avgs = averages_per_parameter(df)
    assert avgs["temp"] == (10.0 + 12.0 + 20.0) / 3.0
    assert avgs["wind"] == (1.0 + 3.0) / 2.0
