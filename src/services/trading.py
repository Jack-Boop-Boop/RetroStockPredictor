"""Paper trading engine: order creation, fill simulation, position/cash updates."""

from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Portfolio, Position, Order, Fill
from ..models.base import new_uuid
from ..utils import get_logger

logger = get_logger(__name__)


class InsufficientFundsError(Exception):
    pass


class InsufficientSharesError(Exception):
    pass


class InvalidOrderError(Exception):
    pass


def create_and_fill_market_order(
    db: Session,
    portfolio: Portfolio,
    symbol: str,
    side: str,
    quantity: Decimal,
    market_price: float,
) -> Order:
    """Create a market order and immediately simulate a fill.

    For paper trading, market orders fill instantly at the given price.
    Returns the filled Order.
    """
    price = Decimal(str(market_price))

    if side not in ("buy", "sell"):
        raise InvalidOrderError(f"Invalid side: {side}")
    if quantity <= 0:
        raise InvalidOrderError("Quantity must be positive")

    # --- Validate ---
    if side == "buy":
        cost = price * quantity
        if cost > portfolio.cash:
            raise InsufficientFundsError(
                f"Need ${cost:.2f} but only have ${portfolio.cash:.2f}"
            )
    elif side == "sell":
        position = (
            db.query(Position)
            .filter_by(portfolio_id=portfolio.id, symbol=symbol)
            .first()
        )
        if not position or position.quantity < quantity:
            held = position.quantity if position else Decimal("0")
            raise InsufficientSharesError(
                f"Want to sell {quantity} {symbol} but only hold {held}"
            )

    # --- Create order ---
    order = Order(
        id=new_uuid(),
        portfolio_id=portfolio.id,
        symbol=symbol,
        side=side,
        order_type="market",
        quantity=quantity,
        status="filled",
        filled_quantity=quantity,
        filled_avg_price=price,
    )
    db.add(order)

    # --- Create fill ---
    fill = Fill(
        id=new_uuid(),
        order_id=order.id,
        quantity=quantity,
        price=price,
    )
    db.add(fill)

    # --- Update position ---
    position = (
        db.query(Position)
        .filter_by(portfolio_id=portfolio.id, symbol=symbol)
        .first()
    )

    if side == "buy":
        if position is None:
            position = Position(
                id=new_uuid(),
                portfolio_id=portfolio.id,
                symbol=symbol,
                quantity=quantity,
                avg_cost=price,
            )
            db.add(position)
        else:
            # Weighted average cost
            total_cost = position.avg_cost * position.quantity + price * quantity
            position.quantity += quantity
            position.avg_cost = total_cost / position.quantity

        portfolio.cash -= price * quantity

    elif side == "sell":
        position.quantity -= quantity
        portfolio.cash += price * quantity

        # Remove position if fully closed
        if position.quantity <= 0:
            db.delete(position)

    db.flush()
    logger.info(f"Filled: {side} {quantity} {symbol} @ ${price:.2f}")
    return order


def get_portfolio_summary(db: Session, portfolio: Portfolio) -> dict:
    """Compute portfolio summary with live prices for P&L."""
    from . import market_data

    positions = (
        db.query(Position)
        .filter_by(portfolio_id=portfolio.id)
        .all()
    )

    position_details = []
    positions_value = Decimal("0")

    for pos in positions:
        try:
            quote = market_data.get_quote(pos.symbol)
            current_price = quote.get("price") or 0
        except Exception:
            current_price = 0

        mv = float(pos.quantity) * current_price
        pnl = mv - float(pos.quantity) * float(pos.avg_cost)
        positions_value += Decimal(str(mv))

        position_details.append({
            "id": pos.id,
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "avg_cost": pos.avg_cost,
            "current_price": current_price,
            "market_value": round(mv, 2),
            "unrealized_pnl": round(pnl, 2),
        })

    total_value = float(portfolio.cash) + float(positions_value)
    initial = float(portfolio.initial_cash)
    total_pnl = total_value - initial
    total_pnl_pct = (total_pnl / initial * 100) if initial else 0

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "cash": portfolio.cash,
        "initial_cash": portfolio.initial_cash,
        "positions": position_details,
        "positions_value": round(float(positions_value), 2),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }
