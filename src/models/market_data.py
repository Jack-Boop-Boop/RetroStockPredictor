"""Market data (candle) model for cached OHLCV data."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, BigInteger, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow, new_uuid


class Candle(Base):
    """Cached OHLCV candle data."""
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("symbol", "interval", "timestamp", name="uq_candles_symbol_interval_ts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(5), nullable=False)  # 1d, 1h, 5m, etc.
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Candle {self.symbol} {self.interval} {self.timestamp} c={self.close}>"
