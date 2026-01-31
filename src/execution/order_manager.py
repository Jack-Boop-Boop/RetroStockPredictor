"""Order Manager - Routes orders to paper or live trading."""
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..utils import config, get_logger, log_trade
from ..data import Database, RobinhoodClient
from ..agents import TradeDecision, TradeAction


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents an order in the system."""
    id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    order_type: str  # "market", "limit"
    limit_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    status: OrderStatus
    filled_price: Optional[float]
    filled_quantity: float
    created_at: datetime
    filled_at: Optional[datetime]
    is_paper: bool
    decision: Optional[TradeDecision]


class OrderManager:
    """
    Central order management system.

    Routes orders to appropriate execution venue (paper or live).
    Tracks order status and manages order lifecycle.
    """

    def __init__(self):
        self.logger = get_logger("order_manager")
        self.db = Database()
        self.robinhood = RobinhoodClient()

        self._orders: Dict[str, Order] = {}
        self._order_counter = 0

        # Determine trading mode
        self.is_paper = config.trading_mode == "paper"
        self.logger.info(f"Order Manager initialized in {'PAPER' if self.is_paper else 'LIVE'} mode")

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        prefix = "PAPER" if self.is_paper else "LIVE"
        return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._order_counter:04d}"

    def execute_decision(self, decision: TradeDecision, current_price: float) -> Optional[Order]:
        """
        Execute a trade decision from the Portfolio CEO.

        Args:
            decision: The trade decision to execute
            current_price: Current market price

        Returns:
            Order object if executed, None if rejected
        """
        if not decision.approved:
            self.logger.info(f"{decision.symbol}: Decision not approved, skipping")
            return None

        if decision.action == TradeAction.HOLD:
            self.logger.info(f"{decision.symbol}: HOLD - no order placed")
            return None

        # Determine order side
        if decision.action in [TradeAction.BUY]:
            side = "buy"
        elif decision.action in [TradeAction.SELL, TradeAction.CLOSE]:
            side = "sell"
        else:
            self.logger.warning(f"Unknown action: {decision.action}")
            return None

        # Create order
        order = Order(
            id=self._generate_order_id(),
            symbol=decision.symbol,
            side=side,
            quantity=decision.quantity,
            order_type="market",
            limit_price=None,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
            status=OrderStatus.PENDING,
            filled_price=None,
            filled_quantity=0,
            created_at=datetime.utcnow(),
            filled_at=None,
            is_paper=self.is_paper,
            decision=decision,
        )

        self._orders[order.id] = order

        # Execute
        if self.is_paper:
            return self._execute_paper(order, current_price)
        else:
            return self._execute_live(order)

    def _execute_paper(self, order: Order, price: float) -> Order:
        """Execute order in paper trading mode."""
        self.logger.info(
            f"[PAPER] {order.side.upper()} {order.quantity:.4f} {order.symbol} @ ${price:.2f}"
        )

        # Simulate immediate fill
        order.status = OrderStatus.FILLED
        order.filled_price = price
        order.filled_quantity = order.quantity
        order.filled_at = datetime.utcnow()

        # Save to database
        self.db.save_trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            is_paper=True,
            order_id=order.id,
            signals_snapshot=order.decision.reasoning if order.decision else None,
        )

        log_trade(
            f"PAPER {order.side.upper()}: {order.quantity:.4f} {order.symbol} @ ${price:.2f} "
            f"(total: ${order.quantity * price:.2f})"
        )

        return order

    def _execute_live(self, order: Order) -> Order:
        """Execute order through Robinhood."""
        self.logger.warning(f"[LIVE] Executing: {order.side} {order.quantity} {order.symbol}")

        try:
            if order.side == "buy":
                result = self.robinhood.buy_market(
                    order.symbol, order.quantity, dry_run=False
                )
            else:
                result = self.robinhood.sell_market(
                    order.symbol, order.quantity, dry_run=False
                )

            if result:
                order.status = OrderStatus.FILLED
                order.filled_price = result.get("price", 0)
                order.filled_quantity = order.quantity
                order.filled_at = datetime.utcnow()

                log_trade(
                    f"LIVE {order.side.upper()}: {order.quantity:.4f} {order.symbol} "
                    f"@ ${order.filled_price:.2f}"
                )
            else:
                order.status = OrderStatus.REJECTED
                self.logger.error(f"Order rejected: {order.id}")

        except Exception as e:
            order.status = OrderStatus.REJECTED
            self.logger.error(f"Order execution failed: {e}")

        return order

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        limit_price: float,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> Order:
        """Place a limit order."""
        order = Order(
            id=self._generate_order_id(),
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="limit",
            limit_price=limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=OrderStatus.PENDING,
            filled_price=None,
            filled_quantity=0,
            created_at=datetime.utcnow(),
            filled_at=None,
            is_paper=self.is_paper,
            decision=None,
        )

        self._orders[order.id] = order

        if self.is_paper:
            # Paper limit orders are queued for price matching
            self.logger.info(
                f"[PAPER] LIMIT {side.upper()} {quantity:.4f} {symbol} @ ${limit_price:.2f}"
            )
        else:
            # Submit to Robinhood
            if side == "buy":
                self.robinhood.buy_limit(symbol, quantity, limit_price, dry_run=False)
            else:
                self.robinhood.sell_limit(symbol, quantity, limit_price, dry_run=False)

        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if not order:
            self.logger.warning(f"Order not found: {order_id}")
            return False

        if order.status != OrderStatus.PENDING:
            self.logger.warning(f"Cannot cancel order in status: {order.status}")
            return False

        if not self.is_paper:
            self.robinhood.cancel_order(order_id)

        order.status = OrderStatus.CANCELLED
        self.logger.info(f"Order cancelled: {order_id}")
        return True

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_open_orders(self) -> list[Order]:
        """Get all open/pending orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.PENDING]

    def get_filled_orders(self, symbol: str = None) -> list[Order]:
        """Get filled orders, optionally filtered by symbol."""
        orders = [o for o in self._orders.values() if o.status == OrderStatus.FILLED]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders
