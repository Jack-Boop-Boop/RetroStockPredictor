"""Portfolio and trading routes."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models import User, Portfolio, Position, Order
from ...models.db import get_db
from ...models.base import new_uuid
from ..auth import get_current_user
from ..schemas.portfolio import OrderRequest, OrderResponse, PortfolioResponse
from ..schemas.stocks import PortfolioImportRequest, PortfolioImportResponse
from ...services import trading, market_data

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_active_portfolio(db: Session, user: User) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter_by(user_id=user.id, is_active=True)
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="No active portfolio")
    return portfolio


@router.get("", response_model=PortfolioResponse)
def get_portfolio(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current portfolio summary with live position values."""
    portfolio = _get_active_portfolio(db, user)
    return trading.get_portfolio_summary(db, portfolio)


@router.post("/orders", response_model=OrderResponse, status_code=201)
def create_order(
    body: OrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place a paper trading order (market orders fill instantly)."""
    portfolio = _get_active_portfolio(db, user)

    # Get current market price
    market_data.check_rate_limit_or_raise(user.id)
    quote = market_data.get_quote(body.symbol)
    price = quote.get("price")
    if not price:
        raise HTTPException(status_code=400, detail=f"Cannot get price for {body.symbol}")

    try:
        order = trading.create_and_fill_market_order(
            db=db,
            portfolio=portfolio,
            symbol=body.symbol,
            side=body.side,
            quantity=body.quantity,
            market_price=price,
        )
    except trading.InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except trading.InsufficientSharesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except trading.InvalidOrderError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return order


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent orders."""
    portfolio = _get_active_portfolio(db, user)
    orders = (
        db.query(Order)
        .filter_by(portfolio_id=portfolio.id)
        .order_by(Order.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )
    return orders


@router.post("/import", response_model=PortfolioImportResponse, status_code=201)
def import_positions(
    body: PortfolioImportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import positions into the portfolio (simulates an existing brokerage portfolio)."""
    portfolio = _get_active_portfolio(db, user)

    imported = 0
    skipped = 0

    for item in body.positions:
        # Check if position already exists
        existing = (
            db.query(Position)
            .filter_by(portfolio_id=portfolio.id, symbol=item.symbol)
            .first()
        )
        if existing:
            # Merge: weighted average cost
            total_cost = existing.avg_cost * existing.quantity + item.avg_cost * item.shares
            existing.quantity += item.shares
            existing.avg_cost = total_cost / existing.quantity
        else:
            db.add(Position(
                id=new_uuid(),
                portfolio_id=portfolio.id,
                symbol=item.symbol,
                quantity=item.shares,
                avg_cost=item.avg_cost,
            ))
        imported += 1

    # Adjust cash down by total import cost
    total_cost = sum(float(p.shares) * float(p.avg_cost) for p in body.positions)
    portfolio.cash -= Decimal(str(total_cost))

    db.flush()
    return PortfolioImportResponse(
        imported=imported,
        skipped=skipped,
        message=f"Imported {imported} positions. Cash adjusted by -${total_cost:,.2f}.",
    )
