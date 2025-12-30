from datetime import datetime, timezone

from sqlmodel import Session

from src.db.models import Measurement
from src.db.repo import bulk_upsert_measurements


def test_weather_current_endpoint(client, engine):
    with Session(engine) as session:
        ts = datetime(2021, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        bulk_upsert_measurements(
            session,
            [
                Measurement(sensor_id="S_CURRENT", ts=ts, parameter="temp", value=15.0, pt=0),
                Measurement(sensor_id="S_CURRENT", ts=ts, parameter="wind", value=5.0, pt=0),
            ],
        )

    resp = client.get("/weather/current", params={"sensor_id": "S_CURRENT"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["sensor_id"] == "S_CURRENT"
    assert data["values"]["temp"] == 15.0
    assert data["values"]["wind"] == 5.0


def test_ingest_batch_endpoint(client):
    payload = [
        {
            "sensor_id": "S_BATCH",
            "ts": "2021-05-03T18:57:51+02:00",
            "pt": 0,
            "rows": [
                ["Variable", "Value"],
                ["external_temperature_c", 12.0],
                ["wind_speed_unmuted_m_s", 4.2],
            ],
            "source_file": "http-1",
        }
    ]

    resp = client.post("/ingest/batch", json=payload)
    assert resp.status_code == 200
    out = resp.json()
    assert out["received_payloads"] == 1
    assert out["failures"] == 0
    assert out["attempted_rows"] > 0

    r2 = client.get("/weather/current", params={"sensor_id": "S_BATCH"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["values"]["external_temperature_c"] == 12.0
    assert data["values"]["wind_speed_unmuted_m_s"] == 4.2


def test_ingest_meteo_rejects_outside_data_root(client):
    resp = client.post("/ingest/meteo", params={"data_root": "/etc"})
    assert resp.status_code == 400
    body = resp.json()
    assert "data_root must be under" in body["detail"]
