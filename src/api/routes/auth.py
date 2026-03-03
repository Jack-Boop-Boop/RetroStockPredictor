"""Auth routes: register, login, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...models import User
from ...models.db import get_db
from ...models.base import new_uuid
from ...utils.security import hash_password, verify_password
from ..auth import create_access_token, get_current_user
from ..schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        id=new_uuid(),
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.flush()

    # Auto-create a default portfolio + watchlist
    from ...models import Portfolio, Watchlist
    db.add(Portfolio(id=new_uuid(), user_id=user.id, name="Paper Trading", initial_cash=100000, cash=100000))
    db.add(Watchlist(id=new_uuid(), user_id=user.id, name="Default", symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]))
    db.flush()

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
