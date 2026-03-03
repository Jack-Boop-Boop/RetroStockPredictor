"""Portfolio, Position, Order, and Fill models for paper trading."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Boolean, ForeignKey, Numeric, Integer, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow, new_uuid


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Default")
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=100000)
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=100000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="portfolios")
    positions = relationship("Position", back_populates="portfolio", lazy="selectin")
    orders = relationship("Order", back_populates="portfolio", lazy="select")

    def __repr__(self) -> str:
        return f"<Portfolio {self.name} cash={self.cash}>"


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "symbol", name="uq_positions_portfolio_symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False, default=0)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="positions")

    def __repr__(self) -> str:
        return f"<Position {self.symbol} qty={self.quantity} avg={self.avg_cost}>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(4), nullable=False)  # buy / sell
    order_type: Mapped[str] = mapped_column(String(10), nullable=False, default="market")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    limit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 6))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False, default=0)
    filled_avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 6))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="orders")
    fills = relationship("Fill", back_populates="order", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Order {self.side} {self.quantity} {self.symbol} status={self.status}>"


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="fills")

    def __repr__(self) -> str:
        return f"<Fill {self.quantity} @ {self.price}>"
