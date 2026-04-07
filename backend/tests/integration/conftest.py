"""
Integration-only fixtures: database engine, schema lifecycle, TestClient.

These are scoped to the integration/ directory so unit tests never open
a database connection.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models.database  # noqa: F401 — registers all ORM classes with Base
from app.clients.database import Base
from app.core.deps_database import get_db
from app.main import app
from tests.conftest import TEST_GOOGLE_SUB, make_user

_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://app:app@localhost:5432/app_test",
)

_engine = create_engine(_TEST_DB_URL, echo=False)
_TestSession = sessionmaker(bind=_engine)


# ---------------------------------------------------------------------------
# Schema lifecycle (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


# ---------------------------------------------------------------------------
# Per-test DB session + table cleanup
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_tables(db):
    yield
    db.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


# ---------------------------------------------------------------------------
# TestClient (session-scoped; overrides get_db to use test sessions)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client():
    def _override_get_db():
        s = _TestSession()
        try:
            yield s
        finally:
            s.rollback()
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def approved_user(db):
    return make_user(db, google_sub=TEST_GOOGLE_SUB)
