"""Performance metrics for backtesting."""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class PerformanceMetrics:
    """Performance metrics for a backtest."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    avg_holding_period: float  # days
    volatility: float
    calmar_ratio: float
    beta: float = None
    alpha: float = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_return_pct": f"{self.total_return * 100:.2f}%",
            "annualized_return_pct": f"{self.annualized_return * 100:.2f}%",
            "sharpe_ratio": f"{self.sharpe_ratio:.2f}",
            "sortino_ratio": f"{self.sortino_ratio:.2f}",
            "max_drawdown_pct": f"{self.max_drawdown * 100:.2f}%",
            "max_drawdown_duration_days": self.max_drawdown_duration,
            "win_rate_pct": f"{self.win_rate * 100:.1f}%",
            "profit_factor": f"{self.profit_factor:.2f}",
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win_pct": f"{self.avg_win * 100:.2f}%",
            "avg_loss_pct": f"{self.avg_loss * 100:.2f}%",
            "best_trade_pct": f"{self.best_trade * 100:.2f}%",
            "worst_trade_pct": f"{self.worst_trade * 100:.2f}%",
            "avg_holding_days": f"{self.avg_holding_period:.1f}",
            "annual_volatility_pct": f"{self.volatility * 100:.2f}%",
            "calmar_ratio": f"{self.calmar_ratio:.2f}",
        }

    def summary(self) -> str:
        """Get a text summary."""
        return f"""
Performance Summary
==================
Total Return:     {self.total_return * 100:>8.2f}%
Annual Return:    {self.annualized_return * 100:>8.2f}%
Sharpe Ratio:     {self.sharpe_ratio:>8.2f}
Sortino Ratio:    {self.sortino_ratio:>8.2f}
Max Drawdown:     {self.max_drawdown * 100:>8.2f}%
Win Rate:         {self.win_rate * 100:>8.1f}%
Profit Factor:    {self.profit_factor:>8.2f}
Total Trades:     {self.total_trades:>8}
"""


def calculate_metrics(
    returns: pd.Series,
    trades: List[Dict],
    risk_free_rate: float = 0.04,
    trading_days: int = 252,
) -> PerformanceMetrics:
    """
    Calculate performance metrics from returns and trades.

    Args:
        returns: Daily returns series
        trades: List of trade dictionaries with 'pnl_pct' and 'holding_days'
        risk_free_rate: Annual risk-free rate (default 4%)
        trading_days: Trading days per year

    Returns:
        PerformanceMetrics object
    """
    # Total return
    total_return = (1 + returns).prod() - 1

    # Annualized return
    n_days = len(returns)
    annualized_return = (1 + total_return) ** (trading_days / n_days) - 1 if n_days > 0 else 0

    # Volatility (annualized)
    volatility = returns.std() * np.sqrt(trading_days)

    # Sharpe ratio
    excess_return = annualized_return - risk_free_rate
    sharpe_ratio = excess_return / volatility if volatility > 0 else 0

    # Sortino ratio (downside deviation)
    downside_returns = returns[returns < 0]
    downside_std = downside_returns.std() * np.sqrt(trading_days) if len(downside_returns) > 0 else 0
    sortino_ratio = excess_return / downside_std if downside_std > 0 else 0

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = abs(drawdowns.min())

    # Max drawdown duration
    in_drawdown = drawdowns < 0
    drawdown_groups = (~in_drawdown).cumsum()
    if in_drawdown.any():
        max_drawdown_duration = in_drawdown.groupby(drawdown_groups).sum().max()
    else:
        max_drawdown_duration = 0

    # Calmar ratio
    calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

    # Trade statistics
    if trades:
        pnls = [t.get("pnl_pct", 0) for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p <= 0]

        total_trades = len(trades)
        winning_trades = len(winning)
        losing_trades = len(losing)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = np.mean(winning) if winning else 0
        avg_loss = np.mean(losing) if losing else 0

        total_wins = sum(winning)
        total_losses = abs(sum(losing))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0

        holding_periods = [t.get("holding_days", 1) for t in trades]
        avg_holding_period = np.mean(holding_periods) if holding_periods else 0
    else:
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        best_trade = 0
        worst_trade = 0
        avg_holding_period = 0

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        max_drawdown=max_drawdown,
        max_drawdown_duration=int(max_drawdown_duration),
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        avg_win=avg_win,
        avg_loss=avg_loss,
        best_trade=best_trade,
        worst_trade=worst_trade,
        avg_holding_period=avg_holding_period,
        volatility=volatility,
        calmar_ratio=calmar_ratio,
    )


def calculate_benchmark_comparison(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.04,
) -> Dict:
    """
    Compare strategy performance against benchmark.

    Args:
        strategy_returns: Daily strategy returns
        benchmark_returns: Daily benchmark returns (e.g., SPY)
        risk_free_rate: Annual risk-free rate

    Returns:
        Dictionary with comparison metrics
    """
    # Align series
    aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 30:
        return {"error": "Insufficient data for comparison"}

    strat = aligned.iloc[:, 0]
    bench = aligned.iloc[:, 1]

    # Beta
    covariance = strat.cov(bench)
    benchmark_variance = bench.var()
    beta = covariance / benchmark_variance if benchmark_variance > 0 else 0

    # Alpha (Jensen's Alpha)
    strat_annual = (1 + strat).prod() ** (252 / len(strat)) - 1
    bench_annual = (1 + bench).prod() ** (252 / len(bench)) - 1
    alpha = strat_annual - (risk_free_rate + beta * (bench_annual - risk_free_rate))

    # Tracking error
    tracking_diff = strat - bench
    tracking_error = tracking_diff.std() * np.sqrt(252)

    # Information ratio
    info_ratio = (strat_annual - bench_annual) / tracking_error if tracking_error > 0 else 0

    # Up/down capture
    up_days = bench > 0
    down_days = bench < 0

    up_capture = strat[up_days].mean() / bench[up_days].mean() if up_days.any() else 0
    down_capture = strat[down_days].mean() / bench[down_days].mean() if down_days.any() else 0

    return {
        "beta": beta,
        "alpha_annual": alpha,
        "tracking_error": tracking_error,
        "information_ratio": info_ratio,
        "up_capture": up_capture,
        "down_capture": down_capture,
        "strategy_return": strat_annual,
        "benchmark_return": bench_annual,
        "outperformance": strat_annual - bench_annual,
    }
