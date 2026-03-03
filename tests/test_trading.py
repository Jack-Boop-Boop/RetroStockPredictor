"""Unit tests for paper trading: fills, P&L math, position updates."""

from decimal import Decimal
import pytest

from src.models import Portfolio, Position, Order, Fill
from src.models.base import new_uuid
from src.services.trading import (
    create_and_fill_market_order,
    InsufficientFundsError,
    InsufficientSharesError,
    InvalidOrderError,
)


@pytest.fixture
def portfolio(db) -> Portfolio:
    from src.models import User
    from src.utils.security import hash_password

    user = User(id=new_uuid(), email="trader@test.com", password_hash=hash_password("pass12345"))
    db.add(user)
    p = Portfolio(id=new_uuid(), user_id=user.id, name="Test", initial_cash=100000, cash=100000)
    db.add(p)
    db.commit()
    return p


class TestBuyOrder:
    def test_buy_creates_position_and_deducts_cash(self, db, portfolio):
        order = create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("10"), 150.00)
        db.commit()

        assert order.status == "filled"
        assert order.filled_quantity == Decimal("10")
        assert order.filled_avg_price == Decimal("150.00")

        # Cash reduced
        db.refresh(portfolio)
        assert portfolio.cash == Decimal("98500.00")

        # Position created
        pos = db.query(Position).filter_by(portfolio_id=portfolio.id, symbol="AAPL").first()
        assert pos is not None
        assert pos.quantity == Decimal("10")
        assert pos.avg_cost == Decimal("150.00")

    def test_buy_updates_avg_cost_on_second_purchase(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("10"), 100.00)
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("10"), 200.00)
        db.commit()

        pos = db.query(Position).filter_by(portfolio_id=portfolio.id, symbol="AAPL").first()
        assert pos.quantity == Decimal("20")
        assert pos.avg_cost == Decimal("150.000000")  # (100*10 + 200*10) / 20

        db.refresh(portfolio)
        assert portfolio.cash == Decimal("97000.00")  # 100k - 1000 - 2000

    def test_buy_insufficient_funds(self, db, portfolio):
        with pytest.raises(InsufficientFundsError):
            create_and_fill_market_order(db, portfolio, "BRK.A", "buy", Decimal("1"), 500000.00)


class TestSellOrder:
    def test_sell_reduces_position_and_adds_cash(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("20"), 100.00)
        create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("10"), 120.00)
        db.commit()

        pos = db.query(Position).filter_by(portfolio_id=portfolio.id, symbol="AAPL").first()
        assert pos.quantity == Decimal("10")

        db.refresh(portfolio)
        # Started 100k, bought 20@100 = -2000, sold 10@120 = +1200 → 99200
        assert portfolio.cash == Decimal("99200.00")

    def test_sell_all_removes_position(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("5"), 100.00)
        create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("5"), 110.00)
        db.commit()

        pos = db.query(Position).filter_by(portfolio_id=portfolio.id, symbol="AAPL").first()
        assert pos is None  # Fully closed position is deleted

    def test_sell_insufficient_shares(self, db, portfolio):
        with pytest.raises(InsufficientSharesError):
            create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("1"), 100.00)

    def test_sell_more_than_held(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("5"), 100.00)
        with pytest.raises(InsufficientSharesError):
            create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("10"), 100.00)


class TestPnL:
    def test_profitable_trade(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("10"), 100.00)
        create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("10"), 150.00)
        db.commit()

        db.refresh(portfolio)
        # Bought at 1000, sold at 1500 → profit = 500
        assert portfolio.cash == Decimal("100500.00")

    def test_losing_trade(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("10"), 100.00)
        create_and_fill_market_order(db, portfolio, "AAPL", "sell", Decimal("10"), 80.00)
        db.commit()

        db.refresh(portfolio)
        # Bought at 1000, sold at 800 → loss = 200
        assert portfolio.cash == Decimal("99800.00")

    def test_fill_records_created(self, db, portfolio):
        create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("5"), 100.00)
        db.commit()

        fills = db.query(Fill).all()
        assert len(fills) == 1
        assert fills[0].quantity == Decimal("5")
        assert fills[0].price == Decimal("100.00")


class TestValidation:
    def test_invalid_side(self, db, portfolio):
        with pytest.raises(InvalidOrderError):
            create_and_fill_market_order(db, portfolio, "AAPL", "short", Decimal("1"), 100.00)

    def test_zero_quantity(self, db, portfolio):
        with pytest.raises(InvalidOrderError):
            create_and_fill_market_order(db, portfolio, "AAPL", "buy", Decimal("0"), 100.00)
