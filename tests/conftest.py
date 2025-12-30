import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import src.db.session as db_session


@pytest.fixture()
def engine(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    SQLModel.metadata.create_all(engine)

    # Create the UNIQUE index needed for ON CONFLICT(sensor_id, ts, parameter, pt)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_measurement_sensor_ts_param_pt
                ON measurement (sensor_id, ts, parameter, pt);
                """
            )
        )

    return engine


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(engine, monkeypatch):
    """
    Patch the application's global DB engine so:
    - startup init_db() operates on our test DB
    - get_session dependency yields sessions bound to our test DB
    """
    monkeypatch.setattr(db_session, "engine", engine)

    from src.api.main import app  # import after patch so startup uses test engine

    return TestClient(app)