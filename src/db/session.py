"""
session.py - Database engine and session management.

This module is responsible for:
- configuring the SQLite database connection
- initializing database tables
- providing SQLModel Session objects to the application

It is intentionally small and centralised so that:
- the DB location can be changed via environment variable
- engine configuration is defined in one place
- FastAPI dependencies can reuse the same session logic
"""

import os
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------

# Database path can be overridden via environment variable.
# Defaults to a local SQLite file under data/app.db
DEFAULT_DB_PATH = Path(os.getenv("DB_PATH", "data/app.db")).resolve()

# Ensure parent directory exists so SQLite can create the file
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH}"

# Create the SQLAlchemy engine.
#
# - check_same_thread=False is required when using SQLite with FastAPI,
#   because FastAPI may access the DB from different threads.
# - echo can be enabled via SQL_ECHO=1 for debugging SQL statements.
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "0") == "1",
    connect_args={"check_same_thread": False},
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Initialize the database schema.

    This creates all tables defined in SQLModel metadata if they do not exist.
    The operation is idempotent and safe to call multiple times.

    Typical usage:
    - called once at application startup
    - called by ingestion before writing data
    """
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """
    Yield a database session.

    This function is designed to be used as a FastAPI dependency:

        def endpoint(session: Session = Depends(get_session)):
            ...

    It ensures that:
    - a session is opened per request
    - the session is properly closed after use
    """
    with Session(engine) as session:
        yield session
