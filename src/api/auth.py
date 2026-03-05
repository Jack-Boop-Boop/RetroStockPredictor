"""JWT authentication: token creation, verification, and FastAPI dependency."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.orm import Session

from ..models import User
from ..models.db import get_db
from ..models.base import new_uuid
from ..utils.settings import settings

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, email: str) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiration_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def _get_or_create_public_user(db: Session) -> User:
    """Return a single shared 'public' user, creating defaults on first use."""
    public_email = "public@local"
    user = db.query(User).filter_by(email=public_email).first()
    if user:
        return user

    # Create a new public user
    user = User(
        id=new_uuid(),
        email=public_email,
        password_hash=None,
        display_name="Public User",
        is_guest=True,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Seed default portfolio, watchlist, and agent hierarchy
    try:
        from .routes.auth import _create_user_defaults

        _create_user_defaults(db, user.id)
    except Exception:
        # If seeding fails for any reason, still return the basic user
        db.rollback()
        db.refresh(user)

    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: in this configuration, authentication is disabled.

    All callers receive the same shared public user; no token is required.
    """
    return _get_or_create_public_user(db)


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional user dependency for public endpoints.

    With authentication disabled, this simply returns the shared public user.
    """
    return _get_or_create_public_user(db)
