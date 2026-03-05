"""
Auth routes: register, login, guest, upgrade, me.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models import User, Portfolio, Watchlist, CustomAgent
from ...models.db import get_db
from ...models.base import new_uuid
from ...utils.security import hash_password, verify_password
from ..auth import create_access_token, get_current_user
from ..schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    UpgradeRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


def _create_default_agent_hierarchy(db: Session, user_id: str) -> None:
    """Seed the default 7-agent hierarchy for a new user."""
    ceo = CustomAgent(
        id=new_uuid(),
        user_id=user_id,
        name="Portfolio CEO",
        agent_type="ceo",
        parent_id=None,
        sort_order=0,
        prompt="You are the CEO agent. Make the final buy/sell/hold decision by weighing all subordinate signals.",
        weight=1.0,
    )
    db.add(ceo)
    db.flush()

    risk = CustomAgent(
        id=new_uuid(),
        user_id=user_id,
        name="Risk Manager",
        agent_type="risk",
        parent_id=ceo.id,
        sort_order=1,
        prompt="Evaluate downside risk. Flag extreme volatility or overexposure.",
        weight=1.0,
    )
    quant = CustomAgent(
        id=new_uuid(),
        user_id=user_id,
        name="Quant Strategist",
        agent_type="quant",
        parent_id=ceo.id,
        sort_order=2,
        prompt="Combine signals from sub-agents using quantitative methods.",
        weight=1.0,
    )
    db.add_all([risk, quant])
    db.flush()

    sub_agents = [
        CustomAgent(
            id=new_uuid(),
            user_id=user_id,
            name="Technical Analyst",
            agent_type="technical",
            parent_id=quant.id,
            sort_order=0,
            prompt="Analyze RSI, MACD, Bollinger Bands, and moving averages for trend signals.",
            weight=1.0,
        ),
        CustomAgent(
            id=new_uuid(),
            user_id=user_id,
            name="Fundamental Analyst",
            agent_type="fundamental",
            parent_id=quant.id,
            sort_order=1,
            prompt="Evaluate P/E ratio, earnings growth, and balance sheet health.",
            weight=1.0,
        ),
        CustomAgent(
            id=new_uuid(),
            user_id=user_id,
            name="Sentiment Analyst",
            agent_type="sentiment",
            parent_id=quant.id,
            sort_order=2,
            prompt="Gauge market mood from news flow, social media, and price momentum.",
            weight=1.0,
        ),
        CustomAgent(
            id=new_uuid(),
            user_id=user_id,
            name="ML Predictor",
            agent_type="ml",
            parent_id=quant.id,
            sort_order=3,
            prompt="Use machine learning momentum models to predict short-term price movement.",
            weight=1.0,
        ),
    ]
    db.add_all(sub_agents)
    db.flush()


def _create_user_defaults(db: Session, user_id: str) -> None:
    """Create portfolio, watchlist, and default agent hierarchy for a new user."""
    db.add(
        Portfolio(
            id=new_uuid(),
            user_id=user_id,
            name="Paper Trading",
            initial_cash=100000,
            cash=100000,
        )
    )
    db.add(
        Watchlist(
            id=new_uuid(),
            user_id=user_id,
            name="Default",
            symbols=DEFAULT_WATCHLIST,
        )
    )
    _create_default_agent_hierarchy(db, user_id)
    db.flush()


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
        is_guest=False,
        is_active=True,  # remove if your User model doesn't have it
    )
    db.add(user)
    db.flush()

    _create_user_defaults(db, user.id)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, is_guest=False)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()

    # guest users won't have passwords, so block password login for them
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, is_guest=bool(getattr(user, "is_guest", False)))


@router.post("/guest", response_model=TokenResponse, status_code=201)
def guest_login(db: Session = Depends(get_db)):
    """Create a guest account with no credentials required."""
    guest_id = new_uuid()
    guest_email = f"guest_{guest_id[:8]}@local"

    user = User(
        id=guest_id,
        email=guest_email,
        password_hash=None,
        display_name="Guest",
        is_guest=True,
        is_active=True,  # remove if your User model doesn't have it
    )
    db.add(user)
    db.flush()

    _create_user_defaults(db, user.id)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, is_guest=True)


@router.post("/upgrade", response_model=TokenResponse)
def upgrade_guest(
    body: UpgradeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upgrade a guest account to a full account with email/password."""
    if not getattr(user, "is_guest", False):
        raise HTTPException(status_code=400, detail="Account is already a full account")

    existing = db.query(User).filter_by(email=body.email).first()
    if existing and existing.id != user.id:
        raise HTTPException(status_code=409, detail="Email already registered")

    user.email = body.email
    user.password_hash = hash_password(body.password)
    if body.display_name:
        user.display_name = body.display_name
    user.is_guest = False
    db.flush()

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, is_guest=False)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=getattr(user, "display_name", None),
        is_guest=bool(getattr(user, "is_guest", False)),
    )
