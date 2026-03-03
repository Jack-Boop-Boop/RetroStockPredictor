"""Shared test fixtures: in-memory SQLite DB, test client, auth helpers."""

import os
import pytest
from decimal import Decimal

# Force SQLite for tests (must be set before importing settings)
os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-chars-long"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.base import Base
from src.models import User, Portfolio, Watchlist
from src.models.db import get_db
from src.utils.security import hash_password
from src.models.base import new_uuid
from src.api.app import app


# Use in-memory SQLite with StaticPool so all sessions share one DB
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


def override_get_db():
    session = TestSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def db():
    session = TestSession()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def demo_user(db) -> User:
    """Create a demo user with portfolio and watchlist."""
    user = User(
        id=new_uuid(),
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        display_name="Test User",
    )
    db.add(user)
    db.add(Portfolio(
        id=new_uuid(), user_id=user.id, name="Paper Trading",
        initial_cash=100000, cash=100000,
    ))
    db.add(Watchlist(
        id=new_uuid(), user_id=user.id, name="Default",
        symbols=["AAPL", "MSFT"],
    ))
    db.commit()
    return user


@pytest.fixture
def auth_headers(demo_user) -> dict:
    """Return Authorization headers for the demo user."""
    from src.api.auth import create_access_token
    token = create_access_token(demo_user.id, demo_user.email)
    return {"Authorization": f"Bearer {token}"}
