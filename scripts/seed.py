"""Seed script: create a demo user with a $100,000 paper portfolio and default watchlist.

Usage:
    python -m scripts.seed

Requires DATABASE_URL to be set (or .env to exist).
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.security import hash_password
from src.models import User, Portfolio, Watchlist
from src.models.db import get_session, create_all_tables, engine
from src.models.base import new_uuid
from src.utils.settings import settings

DEFAULT_EMAIL = "demo@stockpredictor.local"
DEFAULT_PASSWORD = "changeme123"
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def seed() -> None:
    print(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")

    # In dev with no Alembic, create tables directly
    if not settings.is_production:
        print("Creating tables (dev mode)...")
        create_all_tables()

    with get_session() as session:
        # Check if demo user already exists
        existing = session.query(User).filter_by(email=DEFAULT_EMAIL).first()
        if existing:
            print(f"Demo user already exists: {existing.email}")
            return

        # Create user
        user = User(
            id=new_uuid(),
            email=DEFAULT_EMAIL,
            password_hash=hash_password(DEFAULT_PASSWORD),
            display_name="Demo Trader",
        )
        session.add(user)
        session.flush()  # Get user.id

        # Create portfolio with $100k
        portfolio = Portfolio(
            id=new_uuid(),
            user_id=user.id,
            name="Paper Trading",
            initial_cash=100000,
            cash=100000,
        )
        session.add(portfolio)

        # Create default watchlist
        watchlist = Watchlist(
            id=new_uuid(),
            user_id=user.id,
            name="Default",
            symbols=DEFAULT_WATCHLIST,
        )
        session.add(watchlist)

        print(f"Created demo user: {DEFAULT_EMAIL} (password: {DEFAULT_PASSWORD})")
        print(f"Created portfolio: $100,000.00 cash")
        print(f"Created watchlist: {', '.join(DEFAULT_WATCHLIST)}")


def main() -> None:
    seed()
    print("Seed complete.")


if __name__ == "__main__":
    main()
