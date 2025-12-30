# Sensor Measurements API (Meteo)

Backend service that ingests greenhouse **meteo (external weather)** sensor snapshots from JSON files, stores them in **SQLite**, and exposes aggregated views via a **FastAPI** API.

Built for the [**Source.ag](http://source.ag/) Sensor Measurements API** assignment.

---

## Features

### Weather API endpoints

- **Current weather**: latest value per parameter
- **24h time series**: 15-minute resolution (resampled)
- **24h averages**: per parameter
- **7d time series**: 1-day resolution (resampled)
- **7d averages**: per parameter

### Bulk ingestion

- **POST `/ingest/meteo`**: ingest all meteo JSON files under a directory into SQLite

### Data handling

- Parses raw JSON `rows` into a normalized long format: **(sensor_id, ts, parameter, value, pt)**
- Handles duplicates via **unique index + UPSERT**
- Handles missing/malformed rows gracefully (skips invalid values/rows)
- Stores data persistently in SQLite (`data/app.db`) so it survives restarts

---

## Project structure

```markdown

src/
api/
[main.py](http://main.py/) # FastAPI app, startup DB init, router registration
[router.py](http://router.py/) # /weather endpoints
ingest_router.py # /ingest endpoints
[schemas.py](http://schemas.py/) # Pydantic response models
db/
[models.py](http://models.py/) # SQLModel Measurement table
[repo.py](http://repo.py/) # DB queries + upsert + indexes
[session.py](http://session.py/) # engine/session/init_db
ingestion/
[loader.py](http://loader.py/) # discover files + metadata extraction
[parser.py](http://parser.py/) # parse meteo JSON -> record dicts (ts, pt, values)
ingest_to_db.py # bulk ingest directory -> SQLite (batch upsert)
[transform.py](http://transform.py/) # record -> Measurement rows (long format)
services/
meteo_service.py # time window semantics + response shaping
[aggregations.py](http://aggregations.py/) # pandas utilities: resample + averages

```

---

## Requirements

- Python **3.12+** recommended (assignment requirement)
- SQLite (bundled)
- FastAPI + SQLModel

---

### Quick start

```bash
cp .env.example .env
pip install -r requirements.txt
./run.sh
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `DB_PATH` | `data/app.db` | SQLite file path |
| `SQL_ECHO` | `0` | Set to `1` to enable SQLAlchemy SQL logging |

Example:

```bash
export DB_PATH="$(pwd)/data/app.db"
export SQL_ECHO=0
```

Copy the example file and adjust if needed:

```bash
cp .env.example .env
```

## Run the API

```bash
uvicorn src.api.main:app --reload
```

Open :

- Swagger UI: http://127.0.0.1:8000/docs

---

## Bulk ingest data

### Option A: ingest via API endpoint (recommended)

```bash
curl -X POST "<http://127.0.0.1:8000/ingest/meteo?data_root=data/raw/may>"
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

### Option B: ingest via CLI (local/dev)

```bash
python -m src.ingestion.ingest_to_db
```

(Adjust if your local entrypoint differs.)

---

## Example API calls

### Current values

```bash
curl "<http://127.0.0.1:8000/weather/current?sensor_id=0152>"
```

### 24h averages (use a non-zero parameter like temperature)

```bash
curl "<http://127.0.0.1:8000/weather/24h/avg?sensor_id=0152&parameters=external_temperature_c>"
```

### 24h series (multiple parameters must be repeated)

```bash
curl "<http://127.0.0.1:8000/weather/24h/series?sensor_id=0152&parameters=external_temperature_c&parameters=relative_humidity_perc>"
```

### 7d averages

```bash
curl "<http://127.0.0.1:8000/weather/7d/avg?sensor_id=0152>"
```

---

## Notes on the sample dataset

The provided sample meteo data appears to be sparse, often containing ~one snapshot per day per sensor (many parameters recorded at the same timestamp).
As a result:

- A “24h series at 15-minute resolution” may contain only a small number of points.
- Resampling still works, but buckets will be sparse.

To avoid empty windows on historical datasets, the service anchors time windows to the latest timestamp available in the DB, instead of using “now”.

---

## Architecture & design choices

### Data model: long format

Measurements are stored as one row per `(sensor_id, ts, parameter, pt)`:

- Flexible: adding new parameters requires no schema migration
- Queryable: window queries + per-parameter aggregations are straightforward
- Deduplication: enforced via a unique index

### Deduplication & UPSERT

The database enforces uniqueness with:

- `UNIQUE(sensor_id, ts, parameter, pt)`

Ingestion performs UPSERT so re-ingesting the same data is safe and idempotent.

### Layered structure

- `ingestion/*`: parsing + loading + transformation
- `db/*`: persistence primitives only
- `services/*`: domain logic and aggregation orchestration
- `api/*`: request/response layer only

This separation keeps the codebase easy to navigate and extend.

---

## Testing

```bash
pytest -q
```

Suggested test coverage:

- Parser unit tests (JSON → record dict)
- Repo unit tests (upsert + window query)
- Service unit tests (windowing + aggregation output shape)
- One integration test: ingest small subset → query endpoints

---

## Trade-offs & assumptions

- SQLite is used for simplicity and portability. For production, Postgres is recommended.
- The sample dataset is relatively small; ingestion uses batch upsert without heavy optimization.
- Timestamp handling is designed for historical datasets (anchor windows to DB max timestamp).
- Aggregations use pandas for clarity; for large-scale production, consider server-side aggregation or OLAP storage.

---

## If I had 3 months instead of 8 hours

- Use Postgres + TIMESTAMPTZ columns and schema migrations (Alembic)
- Add authentication/authorization for ingestion endpoints
- Stream ingestion via object storage (S3/GCS) + queue (Kafka/PubSub)
- Add observability: structured logs, metrics, tracing
- Add caching for “current” and popular windows
- Improve API design: parameter discovery endpoints, versioning, pagination
- Improve aggregation strategy for high-frequency data (SQL window functions / pre-aggregations)
- Expand test suite with integration + property-based tests + load tests

---