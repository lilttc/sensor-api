from datetime import datetime, timezone

from sqlmodel import Session

from src.db.models import Measurement
from src.db.repo import bulk_upsert_measurements


def test_weather_current_endpoint(client, engine):
    # Insert some data into the same DB that the app uses (engine is patched in conftest)
    with Session(engine) as session:
        ts = datetime(2021, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
        bulk_upsert_measurements(
            session,
            [
                Measurement(sensor_id="S1", ts=ts, parameter="temp", value=15.0, pt=0),
                Measurement(sensor_id="S1", ts=ts, parameter="wind", value=5.0, pt=0),
            ],
        )

    resp = client.get("/weather/current", params={"sensor_id": "S1"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["sensor_id"] == "S1"
    assert data["values"]["temp"] == 15.0
    assert data["values"]["wind"] == 5.0


def test_ingest_batch_endpoint(client):
    payload = [
        {
            "sensor_id": "S1",
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

    # Verify data is queryable
    r2 = client.get("/weather/current", params={"sensor_id": "S1"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["values"]["external_temperature_c"] == 12.0
    assert data["values"]["wind_speed_unmuted_m_s"] == 4.2
