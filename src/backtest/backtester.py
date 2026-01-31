"""Backtesting engine for strategy evaluation."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import pandas as pd
import numpy as np

from .metrics import calculate_metrics, PerformanceMetrics, calculate_benchmark_comparison
from ..utils import get_logger
from ..data import YahooFetcher
from ..agents import (
    TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, MLPredictor,
    QuantStrategist, RiskManager, PortfolioCEO, AgentSignal, TradeAction
)
from ..execution import PaperTrader


class Backtester:
    """
    Backtesting engine for evaluating trading strategies.

    Simulates historical trading using the full agent hierarchy.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission: float = 0.0,  # Commission per trade (Robinhood is zero)
        slippage: float = 0.001,  # 0.1% slippage assumption
    ):
        self.logger = get_logger("backtester")
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.fetcher = YahooFetcher()

        # Initialize agents
        self.technical = TechnicalAnalyst()
        self.fundamental = FundamentalAnalyst()
        self.sentiment = SentimentAnalyst()
        self.ml = MLPredictor()

        self.quant = QuantStrategist([
            self.technical, self.fundamental, self.sentiment, self.ml
        ])
        self.risk = RiskManager()
        self.ceo = PortfolioCEO(self.quant, self.risk)

        # Results storage
        self.results: Optional[Dict] = None

    def run(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        rebalance_frequency: str = "daily",  # daily, weekly, monthly
    ) -> Dict:
        """
        Run a backtest.

        Args:
            symbols: List of stock symbols to trade
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            rebalance_frequency: How often to rebalance

        Returns:
            Dictionary with backtest results
        """
        self.logger.info(f"Starting backtest: {symbols} from {start_date} to {end_date}")

        # Fetch historical data
        data = {}
        for symbol in symbols:
            df = self.fetcher.get_stock_data(
                symbol,
                start=datetime.strptime(start_date, "%Y-%m-%d"),
                end=datetime.strptime(end_date, "%Y-%m-%d"),
            )
            if not df.empty:
                data[symbol] = df
            else:
                self.logger.warning(f"No data for {symbol}")

        if not data:
            return {"error": "No data available for backtesting"}

        # Get common date range
        all_dates = set()
        for df in data.values():
            all_dates.update(df.index)
        dates = sorted(all_dates)

        # Initialize portfolio
        portfolio = PaperTrader(self.initial_capital)
        portfolio_values = []
        trades = []
        daily_returns = []

        # Minimum lookback for agents
        min_lookback = 60

        prev_value = self.initial_capital

        for i, date in enumerate(dates):
            if i < min_lookback:
                portfolio_values.append({
                    "date": date,
                    "value": self.initial_capital,
                })
                continue

            # Check if it's a rebalance day
            if not self._is_rebalance_day(date, dates, i, rebalance_frequency):
                # Just update prices and record value
                prices = {}
                for symbol, df in data.items():
                    if date in df.index:
                        prices[symbol] = df.loc[date, "close"]

                portfolio.update_prices(prices)
                current_value = portfolio.portfolio.total_value

                daily_return = (current_value - prev_value) / prev_value if prev_value > 0 else 0
                daily_returns.append(daily_return)
                prev_value = current_value

                portfolio_values.append({
                    "date": date,
                    "value": current_value,
                })
                continue

            # Rebalance day - run agent analysis
            for symbol, df in data.items():
                if date not in df.index:
                    continue

                # Get historical data up to this date
                historical = df[df.index <= date].tail(min_lookback)
                if len(historical) < min_lookback:
                    continue

                current_price = historical["close"].iloc[-1]

                # Get signals from all analysts
                try:
                    signals = [
                        self.technical.analyze(symbol, historical),
                        self.sentiment.analyze(symbol, historical),
                    ]
                    # Note: fundamental and ML might need more data/setup
                except Exception as e:
                    self.logger.debug(f"Error analyzing {symbol}: {e}")
                    continue

                # Get CEO decision
                current_position = portfolio.get_position(symbol)
                current_qty = current_position.quantity if current_position else 0

                try:
                    decision = self.ceo.make_trade_decision(
                        symbol, signals, current_price, current_qty
                    )
                except Exception as e:
                    self.logger.debug(f"Decision error for {symbol}: {e}")
                    continue

                if not decision.approved:
                    continue

                # Apply slippage
                exec_price = current_price * (1 + self.slippage if decision.action == TradeAction.BUY else 1 - self.slippage)

                # Execute trade
                if decision.action == TradeAction.BUY:
                    if portfolio.buy(symbol, decision.quantity, exec_price):
                        trades.append({
                            "date": date,
                            "symbol": symbol,
                            "action": "buy",
                            "quantity": decision.quantity,
                            "price": exec_price,
                            "signal": decision.signal_value,
                        })

                elif decision.action in [TradeAction.SELL, TradeAction.CLOSE]:
                    qty_to_sell = min(decision.quantity, current_qty)
                    if qty_to_sell > 0:
                        # Calculate P&L
                        entry_price = current_position.avg_cost if current_position else exec_price
                        pnl_pct = (exec_price - entry_price) / entry_price

                        if portfolio.sell(symbol, qty_to_sell, exec_price):
                            trades.append({
                                "date": date,
                                "symbol": symbol,
                                "action": "sell",
                                "quantity": qty_to_sell,
                                "price": exec_price,
                                "pnl_pct": pnl_pct,
                                "holding_days": 1,  # Simplified
                            })

            # Update portfolio value
            prices = {}
            for symbol, df in data.items():
                if date in df.index:
                    prices[symbol] = df.loc[date, "close"]

            portfolio.update_prices(prices)
            current_value = portfolio.portfolio.total_value

            daily_return = (current_value - prev_value) / prev_value if prev_value > 0 else 0
            daily_returns.append(daily_return)
            prev_value = current_value

            portfolio_values.append({
                "date": date,
                "value": current_value,
            })

        # Calculate metrics
        returns_series = pd.Series(daily_returns)
        metrics = calculate_metrics(returns_series, trades)

        # Store results
        self.results = {
            "metrics": metrics,
            "portfolio_values": portfolio_values,
            "trades": trades,
            "final_value": portfolio.portfolio.total_value,
            "final_positions": portfolio.get_portfolio_summary(),
            "config": {
                "symbols": symbols,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": self.initial_capital,
                "rebalance_frequency": rebalance_frequency,
            },
        }

        self.logger.info(f"Backtest complete: {len(trades)} trades, final value ${portfolio.portfolio.total_value:.2f}")
        self.logger.info(metrics.summary())

        return self.results

    def _is_rebalance_day(
        self,
        date,
        all_dates: List,
        index: int,
        frequency: str,
    ) -> bool:
        """Check if this is a rebalance day."""
        if frequency == "daily":
            return True
        elif frequency == "weekly":
            # Rebalance on Mondays (or first day of week)
            if index > 0:
                prev_date = all_dates[index - 1]
                return date.isocalendar()[1] != prev_date.isocalendar()[1]
            return True
        elif frequency == "monthly":
            if index > 0:
                prev_date = all_dates[index - 1]
                return date.month != prev_date.month
            return True
        return True

    def compare_to_benchmark(
        self,
        benchmark_symbol: str = "SPY",
    ) -> Dict:
        """Compare backtest results to a benchmark."""
        if not self.results:
            return {"error": "Run backtest first"}

        config = self.results["config"]

        # Fetch benchmark data
        bench_data = self.fetcher.get_stock_data(
            benchmark_symbol,
            start=datetime.strptime(config["start_date"], "%Y-%m-%d"),
            end=datetime.strptime(config["end_date"], "%Y-%m-%d"),
        )

        if bench_data.empty:
            return {"error": f"No benchmark data for {benchmark_symbol}"}

        # Calculate benchmark returns
        bench_returns = bench_data["close"].pct_change().dropna()

        # Get strategy returns
        pv = pd.DataFrame(self.results["portfolio_values"])
        pv["date"] = pd.to_datetime(pv["date"])
        pv = pv.set_index("date")
        strategy_returns = pv["value"].pct_change().dropna()

        comparison = calculate_benchmark_comparison(strategy_returns, bench_returns)

        self.results["benchmark_comparison"] = comparison
        return comparison

    def get_trade_analysis(self) -> Dict:
        """Get detailed analysis of trades."""
        if not self.results:
            return {"error": "Run backtest first"}

        trades = self.results["trades"]

        if not trades:
            return {"total_trades": 0}

        # Group by symbol
        by_symbol = {}
        for trade in trades:
            symbol = trade["symbol"]
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(trade)

        # Analyze each symbol
        symbol_stats = {}
        for symbol, symbol_trades in by_symbol.items():
            buys = [t for t in symbol_trades if t["action"] == "buy"]
            sells = [t for t in symbol_trades if t["action"] == "sell"]
            pnls = [t.get("pnl_pct", 0) for t in sells]

            symbol_stats[symbol] = {
                "total_trades": len(symbol_trades),
                "buys": len(buys),
                "sells": len(sells),
                "avg_pnl_pct": np.mean(pnls) * 100 if pnls else 0,
                "total_pnl_pct": sum(pnls) * 100,
            }

        return {
            "total_trades": len(trades),
            "by_symbol": symbol_stats,
            "most_traded": max(by_symbol.keys(), key=lambda s: len(by_symbol[s])),
        }
