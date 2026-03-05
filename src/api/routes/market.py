"""Market data and watchlist routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...models import User, Watchlist
from ...models.db import get_db
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


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's watchlist."""
    wl = db.query(Watchlist).filter_by(user_id=user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="No watchlist found")
    return wl


@router.put("/watchlist", response_model=WatchlistResponse)
def update_watchlist(
    body: WatchlistUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's watchlist symbols."""
    wl = db.query(Watchlist).filter_by(user_id=user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="No watchlist found")

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
    wl = db.query(Watchlist).filter_by(user_id=user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="No watchlist found")

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
    wl = db.query(Watchlist).filter_by(user_id=user.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="No watchlist found")

    sym = symbol.upper()
    if sym in wl.symbols:
        wl.symbols = [s for s in wl.symbols if s != sym]
        db.flush()
    return wl
