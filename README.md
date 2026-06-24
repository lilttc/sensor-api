# Sensor Measurements API (Meteo)

Backend service that ingests greenhouse **meteo (external weather)** sensor snapshots from JSON data,
stores them in **SQLite**, and exposes aggregated views via a **FastAPI** API.

A backend service for ingesting and serving greenhouse sensor data.

---

## Features

### Weather API endpoints

- **Current weather**: latest value per parameter
- **24h time series**: 15-minute resolution (resampled)
- **24h averages**: per parameter
- **7d time series**: 1-day resolution (resampled)
- **7d averages**: per parameter

### Bulk ingestion

- **POST `/ingest/batch`**: ingest raw meteo payloads via HTTP (file-like JSON)
- **POST `/ingest/meteo`**: ingest meteo JSON files from a directory on disk (local/demo helper)

### Data handling

- Parses raw JSON `rows` into a normalized long format: **(sensor_id, ts, parameter, value, pt)**
- Handles duplicates via **unique index + UPSERT**
- Skips invalid / malformed values gracefully
- Stores data persistently in SQLite (`data/app.db`) so it survives restarts

---

## Measurement schema

Each stored measurement row contains:

- `sensor_id` (string)
- `ts` (timestamp; stored consistently and used for time-window queries)
- `parameter` (string)
- `value` (float)
- `pt` (int point index)
- `source_file` (string, optional)

Uniqueness is enforced on:

- `UNIQUE(sensor_id, ts, parameter, pt)`

This enables idempotent re-ingestion via UPSERT.

---

## Project structure

```
src/
  api/
    main.py            # FastAPI app, router registration
    router.py          # /weather endpoints
    ingest_router.py   # /ingest endpoints
    schemas.py         # Pydantic response models
  db/
    models.py          # SQLModel Measurement table
    repo.py            # DB queries + upsert + indexes
    session.py         # engine / session / init_db
  ingestion/
    loader.py          # discover files + metadata extraction
    parser.py          # parse meteo JSON -> record dicts (ts, pt, values)
    transform.py       # record -> Measurement rows (long format)
    ingest_to_db.py    # bulk ingest directory -> SQLite (batch upsert)
  services/
    meteo_service.py   # time window semantics + response shaping
    aggregations.py    # pandas utilities: resample + averages
tests/
```

---

## Requirements

- Python **3.12+** recommended
- SQLite (bundled with Python)
- FastAPI + SQLModel

---

## Quick start (local)

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Swagger UI:
- http://127.0.0.1:8000/docs

---

## Environment variables

| Variable     | Default        | Description |
|--------------|----------------|-------------|
| `DB_PATH`    | `data/app.db`  | SQLite database file path |
| `DATA_ROOT`  | `data/raw`     | Allowed root directory for disk ingestion |
| `SQL_ECHO`   | `0`            | Set to `1` to enable SQLAlchemy SQL logging |
| `LOG_LEVEL`  | `INFO`         | Application log level |

---

## Run with Docker

Docker support is provided for easy evaluation.

### Option A: Docker build & run (works without docker-compose)

```bash
docker build -t sensor-measurements-api:latest .

docker run --rm -p 8000:8000 \
  -e DB_PATH=./data/app.db \
  -e DATA_ROOT=./data/raw \
  -v "$(pwd)/data:/app/data" \
  sensor-measurements-api:latest
```

Then open:
- http://127.0.0.1:8000/docs

### Option B: Docker Compose v2 (if available)

```bash
docker compose up --build
```

---

## Bulk ingest data

### Option A: ingest raw payloads via HTTP (recommended)

```bash
curl -X POST "http://127.0.0.1:8000/ingest/batch" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "sensor_id": "S1",
      "ts": "2021-05-03T18:57:51+02:00",
      "pt": 0,
      "rows": [
        ["Variable", "Value"],
        ["external_temperature_c", 12.0],
        ["wind_speed_unmuted_m_s", 4.2]
      ]
    }
  ]'
```

### Option B: ingest sample dataset from disk (local/demo helper)

```bash
curl -X POST "http://127.0.0.1:8000/ingest/meteo?data_root=data/raw/may"
```

Example response:

```json
{
  "data_root": "/abs/path/data/raw/may",
  "processed_files": 1234,
  "parsed_records": 1234,
  "attempted_rows": 98765,
  "failures": 0
}
```

> Note: for safety, `data_root` must be **under `DATA_ROOT`** (default: `data/raw`).
> Paths outside this directory are rejected.

---

## Example API calls

### Current values

```bash
curl "http://127.0.0.1:8000/weather/current?sensor_id=0152"
```

### 24h averages

```bash
curl "http://127.0.0.1:8000/weather/24h/avg?sensor_id=0152&parameters=external_temperature_c"
```

### 24h series (repeat parameters)

```bash
curl "http://127.0.0.1:8000/weather/24h/series?sensor_id=0152&parameters=external_temperature_c&parameters=relative_humidity_perc"
```

### 7d averages

```bash
curl "http://127.0.0.1:8000/weather/7d/avg?sensor_id=0152"
```

---

## Notes on time windows and dataset sparsity

The provided sample meteo data is sparse and often contains only a single snapshot per day per sensor.
As a result:

- A “24h series at 15-minute resolution” may contain only a small number of points.
- Resampling still works, but buckets may be sparse.

To avoid empty windows, time windows are **anchored to the latest timestamp in the database**, rather than using the current wall-clock time.

---

## Resetting the database

To start from a clean state:

```bash
rm -f data/app.db
```

The database and indexes will be recreated automatically on next startup / ingestion.

---

## Health / readiness

A dedicated `/health` endpoint is not included. API readiness can be verified via:
- `/docs`
- `/weather/current` (after ingesting data)

---

## Architecture & design choices

### Data model: long format

Measurements are stored as one row per `(sensor_id, ts, parameter, pt)`:

- Flexible: new parameters require no schema migration
- Queryable: window queries and aggregations are straightforward
- Deduplication: enforced via a unique constraint + UPSERT semantics

### Layered structure

- `ingestion/*`: parsing, validation, transformation
- `db/*`: persistence primitives only
- `services/*`: domain logic and aggregation orchestration
- `api/*`: request/response layer only

---

## Testing

```bash
pytest -q
```

The test suite includes:
- Ingestion pipeline tests (parse → transform → upsert)
- Aggregation tests (resampling + averages)
- API integration tests (ingest + query endpoints)

---

## Trade-offs & assumptions

- SQLite is used for simplicity and portability; Postgres is recommended for production.
- The dataset is relatively small; ingestion uses batch upsert without heavy optimization.
- Aggregations use pandas for clarity; for large-scale production, consider SQL/window functions or pre-aggregations.

---

## If I had more time

- Postgres + Alembic migrations
- Authentication/authorization for ingestion endpoints
- Stream ingestion via object storage + queue
- Observability: structured logs, metrics, tracing
- Caching for “current” and popular windows
- Parameter discovery endpoints and API versioning
- Load testing and property-based tests
