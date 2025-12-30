import json
from datetime import datetime, timezone

from sqlmodel import Session

from src.db.repo import bulk_upsert_measurements, get_latest_per_parameter
from src.ingestion.parser import parse_meteo_json_file
from src.ingestion.transform import wide_record_to_measurements


def test_parse_transform_and_upsert(tmp_path, session: Session):
    # Create a minimal raw meteo file (matches the provided sample format)
    p = tmp_path / "meteo-0001.json"
    payload = {
        "name": "_ws_source_meteo",
        "range": "dummy",
        "ts": "2021-05-03T18:57:51+02:00",
        "pt": 0,
        "rows": [
            ["Variable", "Value"],
            ["external_temperature_c", 11.0],
            ["external_temperature_c", 12.0],  # duplicate -> parser keeps last non-missing
            ["wind_speed_unmuted_m_s", 4.2],
            ["bad_value", "not-a-number"],     # transform should drop non-numerics safely
        ],
    }
    p.write_text(json.dumps(payload))

    records = parse_meteo_json_file(p, sensor_id="S1", month=5, day=3)
    assert isinstance(records, list)
    assert len(records) >= 1

    record = records[0]
    assert record["sensor_id"] == "S1"
    assert record["pt"] == 0

    # Parser dedupe behavior: last duplicate value should win
    assert record["external_temperature_c"] == 12.0

    measurements = list(wide_record_to_measurements(record))

    # Should contain only numeric measurement rows
    params = sorted({m.parameter for m in measurements})
    assert "external_temperature_c" in params
    assert "wind_speed_unmuted_m_s" in params
    assert "bad_value" not in params

    # Upsert into DB
    rows = bulk_upsert_measurements(session, measurements)
    assert isinstance(rows, int)
    assert rows == len(measurements)

    # Validate latest-per-parameter query
    latest = get_latest_per_parameter(session, sensor_id="S1")
    assert latest["external_temperature_c"].value == 12.0
    assert latest["wind_speed_unmuted_m_s"].value == 4.2


def test_upsert_updates_existing_row(session: Session):
    # Two measurements with same (sensor_id, ts, parameter, pt) -> second should overwrite
    ts = datetime(2021, 5, 1, 10, 0, 0, tzinfo=timezone.utc)

    from src.db.models import Measurement

    m1 = Measurement(sensor_id="S1", ts=ts, parameter="temp", value=1.0, pt=0, source_file="a.json")
    m2 = Measurement(sensor_id="S1", ts=ts, parameter="temp", value=2.0, pt=0, source_file="a.json")

    bulk_upsert_measurements(session, [m1])
    bulk_upsert_measurements(session, [m2])

    latest = get_latest_per_parameter(session, sensor_id="S1")
    assert latest["temp"].value == 2.0
