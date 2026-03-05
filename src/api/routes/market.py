"""Market data and watchlist routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...models import User, Watchlist
from ...models.db import get_db
from ...models.base import new_uuid
from ..auth import get_current_user, get_optional_user
from ..schemas.market import QuoteResponse, WatchlistResponse, WatchlistUpdateRequest
from ...services import market_data

router = APIRouter(tags=["market"])


@router.get("/quote", response_model=QuoteResponse)
def get_quote(
    symbol: str = Query(..., min_length=1, max_length=10, pattern=r"^[A-Za-z]{1,10}$"),
    user: User | None = Depends(get_optional_user),
):
    """Get a real-time stock quote (public, rate-limited when authenticated)."""
    if user:
        market_data.check_rate_limit_or_raise(user.id)
    try:
        return market_data.get_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _get_or_create_watchlist(db: Session, user: User) -> Watchlist:
    """Return the user's watchlist, creating a default one if missing."""
    wl = db.query(Watchlist).filter_by(user_id=user.id).first()
    if wl:
        return wl

    wl = Watchlist(
        id=new_uuid(),
        user_id=user.id,
        name="Default",
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
    )
    db.add(wl)
    db.flush()
    return wl


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's watchlist (auto-creating a default if needed)."""
    wl = _get_or_create_watchlist(db, user)
    return wl


@router.put("/watchlist", response_model=WatchlistResponse)
def update_watchlist(
    body: WatchlistUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's watchlist symbols."""
    wl = _get_or_create_watchlist(db, user)

    wl.symbols = [s.upper() for s in body.symbols]
    db.flush()
    return wl


@router.post("/watchlist/add", response_model=WatchlistResponse)
def add_to_watchlist(
    symbol: str = Query(..., min_length=1, max_length=10, pattern=r"^[A-Za-z.]{1,10}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a single symbol to the user's watchlist."""
    wl = _get_or_create_watchlist(db, user)

    sym = symbol.upper()
    if sym not in wl.symbols:
        wl.symbols = wl.symbols + [sym]
        db.flush()
    return wl


@router.post("/watchlist/remove", response_model=WatchlistResponse)
def remove_from_watchlist(
    symbol: str = Query(..., min_length=1, max_length=10, pattern=r"^[A-Za-z.]{1,10}$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a single symbol from the user's watchlist."""
    wl = _get_or_create_watchlist(db, user)

    sym = symbol.upper()
    if sym in wl.symbols:
        wl.symbols = [s for s in wl.symbols if s != sym]
        db.flush()
    return wl
