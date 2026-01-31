"""Paper Trading Portfolio Manager."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json
from pathlib import Path

from ..utils import config, get_logger, log_trade


@dataclass
class Position:
    """Represents a position in the paper portfolio."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


@dataclass
class PaperPortfolio:
    """Paper trading portfolio state."""
    cash: float = 100000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    initial_value: float = 100000.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_positions_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_value(self) -> float:
        return self.cash + self.total_positions_value

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.initial_value

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_pnl / self.initial_value) * 100


class PaperTrader:
    """
    Paper trading system for backtesting and simulation.

    Simulates portfolio management without real money.
    """

    def __init__(self, initial_cash: float = 100000.0):
        self.logger = get_logger("paper_trader")
        self.portfolio = PaperPortfolio(
            cash=initial_cash,
            initial_value=initial_cash,
        )
        self._trade_history: List[Dict] = []
        self._state_file = Path("data/paper_portfolio.json")

        # Try to load existing state
        self._load_state()

    def buy(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Execute a paper buy order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price

        Returns:
            True if successful, False if insufficient funds
        """
        total_cost = quantity * price

        if total_cost > self.portfolio.cash:
            self.logger.warning(
                f"Insufficient funds: need ${total_cost:.2f}, have ${self.portfolio.cash:.2f}"
            )
            return False

        # Update cash
        self.portfolio.cash -= total_cost

        # Update or create position
        if symbol in self.portfolio.positions:
            pos = self.portfolio.positions[symbol]
            # Calculate new average cost
            total_quantity = pos.quantity + quantity
            total_cost_basis = (pos.quantity * pos.avg_cost) + (quantity * price)
            pos.avg_cost = total_cost_basis / total_quantity
            pos.quantity = total_quantity
            pos.current_price = price
        else:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_cost=price,
                current_price=price,
            )

        # Record trade
        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "price": price,
            "total": total_cost,
            "cash_after": self.portfolio.cash,
        }
        self._trade_history.append(trade)

        self.logger.info(f"PAPER BUY: {quantity:.4f} {symbol} @ ${price:.2f} = ${total_cost:.2f}")
        log_trade(f"PAPER BUY: {quantity:.4f} {symbol} @ ${price:.2f}")

        self._save_state()
        return True

    def sell(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Execute a paper sell order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price

        Returns:
            True if successful, False if insufficient shares
        """
        if symbol not in self.portfolio.positions:
            self.logger.warning(f"No position in {symbol}")
            return False

        pos = self.portfolio.positions[symbol]

        if quantity > pos.quantity:
            self.logger.warning(
                f"Insufficient shares: have {pos.quantity:.4f}, trying to sell {quantity:.4f}"
            )
            return False

        # Calculate proceeds
        proceeds = quantity * price

        # Calculate realized P&L for this trade
        cost_of_sold = quantity * pos.avg_cost
        realized_pnl = proceeds - cost_of_sold

        # Update cash
        self.portfolio.cash += proceeds

        # Update position
        pos.quantity -= quantity
        pos.current_price = price

        # Remove position if fully closed
        if pos.quantity <= 0.0001:  # Small threshold for floating point
            del self.portfolio.positions[symbol]

        # Record trade
        trade = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "price": price,
            "total": proceeds,
            "realized_pnl": realized_pnl,
            "cash_after": self.portfolio.cash,
        }
        self._trade_history.append(trade)

        self.logger.info(
            f"PAPER SELL: {quantity:.4f} {symbol} @ ${price:.2f} = ${proceeds:.2f} "
            f"(P&L: ${realized_pnl:.2f})"
        )
        log_trade(f"PAPER SELL: {quantity:.4f} {symbol} @ ${price:.2f} (P&L: ${realized_pnl:.2f})")

        self._save_state()
        return True

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        for symbol, price in prices.items():
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].current_price = price

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.portfolio.positions.get(symbol)

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        positions_summary = []
        for symbol, pos in self.portfolio.positions.items():
            positions_summary.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            })

        return {
            "cash": self.portfolio.cash,
            "positions_value": self.portfolio.total_positions_value,
            "total_value": self.portfolio.total_value,
            "initial_value": self.portfolio.initial_value,
            "total_pnl": self.portfolio.total_pnl,
            "total_pnl_pct": self.portfolio.total_pnl_pct,
            "positions": positions_summary,
            "num_positions": len(self.portfolio.positions),
        }

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history."""
        return self._trade_history[-limit:]

    def reset(self, initial_cash: float = 100000.0):
        """Reset portfolio to initial state."""
        self.portfolio = PaperPortfolio(
            cash=initial_cash,
            initial_value=initial_cash,
        )
        self._trade_history = []
        self._save_state()
        self.logger.info(f"Portfolio reset with ${initial_cash:.2f}")

    def _save_state(self):
        """Save portfolio state to file."""
        state = {
            "cash": self.portfolio.cash,
            "initial_value": self.portfolio.initial_value,
            "created_at": self.portfolio.created_at.isoformat(),
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "current_price": pos.current_price,
                }
                for symbol, pos in self.portfolio.positions.items()
            },
            "trade_history": self._trade_history[-1000:],  # Keep last 1000 trades
        }

        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load portfolio state from file."""
        if not self._state_file.exists():
            return

        try:
            with open(self._state_file, "r") as f:
                state = json.load(f)

            self.portfolio.cash = state["cash"]
            self.portfolio.initial_value = state["initial_value"]
            self.portfolio.created_at = datetime.fromisoformat(state["created_at"])

            for symbol, pos_data in state.get("positions", {}).items():
                self.portfolio.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=pos_data["quantity"],
                    avg_cost=pos_data["avg_cost"],
                    current_price=pos_data.get("current_price", pos_data["avg_cost"]),
                )

            self._trade_history = state.get("trade_history", [])

            self.logger.info(
                f"Loaded portfolio: ${self.portfolio.total_value:.2f} "
                f"({len(self.portfolio.positions)} positions)"
            )

        except Exception as e:
            self.logger.error(f"Error loading state: {e}")
