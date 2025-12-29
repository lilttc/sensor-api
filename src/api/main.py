"""
main.py - FastAPI application entry point for the Meteo API.

This module is responsible for:
- Creating the FastAPI application instance
- Initializing the SQLite database on startup
- Ensuring required tables and indexes exist
- Registering API routers

The application exposes:
- Read-only weather endpoints under `/weather`
- Bulk ingestion endpoints under `/ingest`

This file intentionally contains:
- no business logic
- no database queries beyond initialization
- no data transformation logic
"""

import logging

from fastapi import FastAPI
from sqlmodel import Session

from src.api.router import router as weather_router
from src.api.ingest_router import router as ingest_router
from src.db.repo import ensure_indexes
from src.db.session import DEFAULT_DB_PATH, engine, init_db

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Meteo API",
    description="Backend service for ingesting and querying weather sensor data",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup() -> None:
    """
    FastAPI startup hook.

    Responsibilities:
    - Create database tables if they do not exist
    - Ensure indexes and uniqueness constraints are present
    - Log the active SQLite database path

    This function is safe to run multiple times.
    """
    init_db()

    with Session(engine) as session:
        ensure_indexes(session)

    logger.info("Using SQLite DB at: %s", DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

app.include_router(weather_router)
app.include_router(ingest_router)
