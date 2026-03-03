"""Database engine and session management.

Usage:
    from src.models.db import get_session, engine

    # As context manager (preferred):
    with get_session() as session:
        user = session.get(User, user_id)

    # As FastAPI dependency (see src/api/):
    def my_route(session: Session = Depends(get_db)):
        ...
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..utils.settings import settings
from .base import Base

engine = create_engine(
    settings.database_url,
    # pool_pre_ping keeps connections alive through Postgres idle timeouts
    pool_pre_ping=True,
    # SQLite doesn't support pool settings, Postgres does
    **({} if "sqlite" in settings.database_url else {
        "pool_size": 5,
        "max_overflow": 10,
    }),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, auto-closing on exit."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables() -> None:
    """Create all tables (for development/testing only; use Alembic in production)."""
    Base.metadata.create_all(bind=engine)
