from fastapi import FastAPI

from src.api.router import router
from src.db.session import DEFAULT_DB_PATH, init_db, engine
from src.db.repo import ensure_indexes
from sqlmodel import Session

app = FastAPI(title="Meteo API")

@app.on_event("startup")
def on_startup() -> None:
    # Create tables
    init_db()

    # Create indexes/unique constraints
    with Session(engine) as session:
        ensure_indexes(session)

    # Helpful log to confirm which DB file is used
    print(f"[INFO] Using SQLite DB at: {DEFAULT_DB_PATH}")

app.include_router(router)
