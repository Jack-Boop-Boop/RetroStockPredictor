"""Robinhood trading client."""
from typing import Optional
import robin_stocks.robinhood as rh

from ..utils import config, get_logger, log_trade
from .database import Database

logger = get_logger(__name__)


class RobinhoodClient:
    """Client for Robinhood trading operations."""

    def __init__(self):
        self.db = Database()
        self._logged_in = False

    def login(self) -> bool:
        """
        Login to Robinhood.

        Requires environment variables:
        - ROBINHOOD_USERNAME
        - ROBINHOOD_PASSWORD
        - ROBINHOOD_TOTP (optional, for 2FA)
        """
        username = config.robinhood_username
        password = config.robinhood_password
        totp = config.robinhood_totp

        if not username or not password:
            logger.warning("Robinhood credentials not configured")
            return False

        try:
            if totp:
                rh.login(username, password, mfa_code=totp)
            else:
                rh.login(username, password)

            self._logged_in = True
            logger.info("Successfully logged into Robinhood")
            return True
        except Exception as e:
            logger.error(f"Robinhood login failed: {e}")
            return False

    def logout(self):
        """Logout from Robinhood."""
        if self._logged_in:
            rh.logout()
            self._logged_in = False
            logger.info("Logged out from Robinhood")

    def _ensure_logged_in(self):
        """Ensure we're logged in before making requests."""
        if not self._logged_in:
            if not self.login():
                raise RuntimeError("Not logged into Robinhood")

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        self._ensure_logged_in()
        quote = rh.stocks.get_latest_price(symbol)
        return {
            "symbol": symbol,
            "price": float(quote[0]) if quote else None,
        }

    def get_quotes(self, symbols: list[str]) -> dict[str, float]:
        """Get quotes for multiple symbols."""
        self._ensure_logged_in()
        prices = rh.stocks.get_latest_price(symbols)
        return {
            symbol: float(price) if price else None
            for symbol, price in zip(symbols, prices)
        }

    def get_portfolio(self) -> dict:
        """Get current portfolio holdings."""
        self._ensure_logged_in()
        holdings = rh.account.build_holdings()
        return holdings

    def get_account_info(self) -> dict:
        """Get account information."""
        self._ensure_logged_in()
        profile = rh.profiles.load_account_profile()
        return {
            "buying_power": float(profile.get("buying_power", 0)),
            "cash": float(profile.get("cash", 0)),
            "portfolio_value": float(profile.get("portfolio_cash", 0)),
        }

    def buy_market(
        self,
        symbol: str,
        quantity: float,
        dry_run: bool = True,
    ) -> Optional[dict]:
        """
        Place a market buy order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares (can be fractional)
            dry_run: If True, don't actually place the order

        Returns:
            Order details or None if dry_run
        """
        self._ensure_logged_in()

        if dry_run or config.trading_mode == "paper":
            price = self.get_quote(symbol)["price"]
            logger.info(f"[PAPER] BUY {quantity} {symbol} @ ${price:.2f}")
            log_trade(f"PAPER BUY {quantity} {symbol} @ ${price:.2f}")

            # Save to database as paper trade
            trade = self.db.save_trade(
                symbol=symbol,
                side="buy",
                quantity=quantity,
                price=price,
                is_paper=True,
            )
            return {"paper": True, "trade_id": trade.id, "price": price}

        # Live order
        logger.warning(f"[LIVE] Placing BUY order: {quantity} {symbol}")
        log_trade(f"LIVE BUY {quantity} {symbol}")

        order = rh.orders.order_buy_fractional_by_quantity(
            symbol, quantity, timeInForce="gfd"
        )

        if order:
            self.db.save_trade(
                symbol=symbol,
                side="buy",
                quantity=quantity,
                price=float(order.get("price", 0)),
                is_paper=False,
                order_id=order.get("id"),
            )

        return order

    def sell_market(
        self,
        symbol: str,
        quantity: float,
        dry_run: bool = True,
    ) -> Optional[dict]:
        """
        Place a market sell order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            dry_run: If True, don't actually place the order

        Returns:
            Order details or None if dry_run
        """
        self._ensure_logged_in()

        if dry_run or config.trading_mode == "paper":
            price = self.get_quote(symbol)["price"]
            logger.info(f"[PAPER] SELL {quantity} {symbol} @ ${price:.2f}")
            log_trade(f"PAPER SELL {quantity} {symbol} @ ${price:.2f}")

            trade = self.db.save_trade(
                symbol=symbol,
                side="sell",
                quantity=quantity,
                price=price,
                is_paper=True,
            )
            return {"paper": True, "trade_id": trade.id, "price": price}

        # Live order
        logger.warning(f"[LIVE] Placing SELL order: {quantity} {symbol}")
        log_trade(f"LIVE SELL {quantity} {symbol}")

        order = rh.orders.order_sell_fractional_by_quantity(
            symbol, quantity, timeInForce="gfd"
        )

        if order:
            self.db.save_trade(
                symbol=symbol,
                side="sell",
                quantity=quantity,
                price=float(order.get("price", 0)),
                is_paper=False,
                order_id=order.get("id"),
            )

        return order

    def buy_limit(
        self,
        symbol: str,
        quantity: float,
        limit_price: float,
        dry_run: bool = True,
    ) -> Optional[dict]:
        """Place a limit buy order."""
        self._ensure_logged_in()

        if dry_run or config.trading_mode == "paper":
            logger.info(f"[PAPER] LIMIT BUY {quantity} {symbol} @ ${limit_price:.2f}")
            return {"paper": True, "limit_price": limit_price}

        return rh.orders.order_buy_limit(symbol, quantity, limit_price)

    def sell_limit(
        self,
        symbol: str,
        quantity: float,
        limit_price: float,
        dry_run: bool = True,
    ) -> Optional[dict]:
        """Place a limit sell order."""
        self._ensure_logged_in()

        if dry_run or config.trading_mode == "paper":
            logger.info(f"[PAPER] LIMIT SELL {quantity} {symbol} @ ${limit_price:.2f}")
            return {"paper": True, "limit_price": limit_price}

        return rh.orders.order_sell_limit(symbol, quantity, limit_price)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        self._ensure_logged_in()
        result = rh.orders.cancel_stock_order(order_id)
        return result is not None

    def get_open_orders(self) -> list:
        """Get all open orders."""
        self._ensure_logged_in()
        return rh.orders.get_all_open_stock_orders()
