"""JWT authentication: token creation, verification, and FastAPI dependency.

In this configuration:
- Requests *with* a valid Bearer token get that specific user.
- Requests *without* a token transparently use a shared public demo user.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
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

    # Seed default portfolio, watchlist, and agent hierarchy.
    # If this fails, keep the basic user so the demo still works.
    try:
        from .routes.auth import _create_user_defaults

        _create_user_defaults(db, user.id)
    except Exception:
        pass

    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency:

    - If a valid Bearer token is provided, return that user (enforcing JWT auth).
    - If no token is provided, return the shared public demo user.
    """
    if credentials is None:
        return _get_or_create_public_user(db)

    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if user is None or (hasattr(user, "is_active") and not user.is_active):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional user dependency for public endpoints.

    - If a valid token is present, return that user.
    - If no/invalid token, return None so callers can treat requests as anonymous.
    """
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None
