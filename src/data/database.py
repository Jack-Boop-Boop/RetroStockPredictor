"""Database models and management for Stock Predictor."""
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..utils import config, get_logger

logger = get_logger(__name__)
Base = declarative_base()


class StockPrice(Base):
    """Historical stock price data."""
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    adjusted_close = Column(Float)

    def __repr__(self):
        return f"<StockPrice {self.symbol} {self.date.date()} close={self.close}>"


class Signal(Base):
    """Trading signals from agents."""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    agent_type = Column(String(50), nullable=False)  # technical, fundamental, sentiment, ml
    signal_value = Column(Float)  # -1.0 (strong sell) to 1.0 (strong buy)
    confidence = Column(Float)  # 0.0 to 1.0
    reasoning = Column(JSON)  # Detailed breakdown

    def __repr__(self):
        return f"<Signal {self.symbol} {self.agent_type} value={self.signal_value}>"


class Trade(Base):
    """Executed trades (paper or live)."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    side = Column(String(10))  # buy or sell
    quantity = Column(Float)
    price = Column(Float)
    total_value = Column(Float)
    is_paper = Column(Boolean, default=True)
    order_id = Column(String(100))  # External order ID
    status = Column(String(20))  # pending, filled, cancelled
    signals_snapshot = Column(JSON)  # Signals at time of trade

    def __repr__(self):
        mode = "PAPER" if self.is_paper else "LIVE"
        return f"<Trade [{mode}] {self.side} {self.quantity} {self.symbol} @ {self.price}>"


class Portfolio(Base):
    """Portfolio positions and cash."""
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    symbol = Column(String(10), index=True)  # None for cash
    quantity = Column(Float)
    avg_cost = Column(Float)
    current_price = Column(Float)
    market_value = Column(Float)
    unrealized_pnl = Column(Float)
    is_paper = Column(Boolean, default=True)


class Database:
    """Database manager singleton."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize database connection."""
        db_path = config.database_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized at {db_path}")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def save_price(self, symbol: str, date: datetime, open_: float, high: float,
                   low: float, close: float, volume: int, adj_close: float):
        """Save a stock price record."""
        with self.get_session() as session:
            price = StockPrice(
                symbol=symbol, date=date, open=open_, high=high,
                low=low, close=close, volume=volume, adjusted_close=adj_close
            )
            session.merge(price)
            session.commit()

    def save_signal(self, symbol: str, agent_type: str, signal_value: float,
                    confidence: float, reasoning: Optional[dict] = None) -> Signal:
        """Save a trading signal."""
        with self.get_session() as session:
            signal = Signal(
                symbol=symbol, agent_type=agent_type,
                signal_value=signal_value, confidence=confidence,
                reasoning=reasoning or {}
            )
            session.add(signal)
            session.commit()
            session.refresh(signal)
            return signal

    def save_trade(self, symbol: str, side: str, quantity: float, price: float,
                   is_paper: bool = True, order_id: str = None,
                   signals_snapshot: dict = None) -> Trade:
        """Save a trade record."""
        with self.get_session() as session:
            trade = Trade(
                symbol=symbol, side=side, quantity=quantity, price=price,
                total_value=quantity * price, is_paper=is_paper,
                order_id=order_id, status="filled", signals_snapshot=signals_snapshot
            )
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade

    def get_latest_prices(self, symbol: str, limit: int = 100):
        """Get the latest price records for a symbol."""
        with self.get_session() as session:
            return session.query(StockPrice).filter(
                StockPrice.symbol == symbol
            ).order_by(StockPrice.date.desc()).limit(limit).all()

    def get_latest_signals(self, symbol: str, limit: int = 10):
        """Get the latest signals for a symbol."""
        with self.get_session() as session:
            return session.query(Signal).filter(
                Signal.symbol == symbol
            ).order_by(Signal.timestamp.desc()).limit(limit).all()
