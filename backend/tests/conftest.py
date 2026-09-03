"""Pytest configuration and fixtures."""

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.main import app
from app.dependencies import get_db

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a test database and session."""
    Base.metadata.create_all(bind=engine)
    yield from override_get_db()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """Create a test client with overridden database."""
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def tenant_data() -> dict:
    """Sample tenant data for tests."""
    return {
        "name": "Test Tenant",
        "email": "test@example.com",
        "plan": "free",
    }


@pytest.fixture
def usage_data() -> dict:
    """Sample usage data for tests."""
    return {
        "type": "api_call",
        "quantity": 1,
        "cost_cents": 1,
        "idempotency_key": "test-key-123",
    }
