#!/usr/bin/env python3
"""
Stock Predictor - AI-Powered Trading System

A hierarchical multi-agent AI system for stock prediction and automated trading.
Agents: Technical, Fundamental, Sentiment, ML -> Quant -> Risk -> CEO

Usage:
    python main.py --analyze AAPL MSFT         # Analyze specific stocks
    python main.py --backtest --start 2024-01-01  # Run backtest
    python main.py --trade                      # Start paper trading loop
"""
import argparse
from datetime import datetime, timedelta

from src.utils import config, get_logger
from src.data import Database, YahooFetcher
from src.agents import (
    TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, MLPredictor,
    QuantStrategist, RiskManager, PortfolioCEO
)
from src.execution import OrderManager, PaperTrader
from src.backtest import Backtester

logger = get_logger("main")


def analyze_stocks(symbols: list[str]):
    """Run full agent analysis on given symbols."""
    logger.info(f"Analyzing: {symbols}")

    fetcher = YahooFetcher()

    # Initialize agent hierarchy
    technical = TechnicalAnalyst()
    fundamental = FundamentalAnalyst()
    sentiment = SentimentAnalyst()
    ml = MLPredictor()

    quant = QuantStrategist([technical, fundamental, sentiment, ml])
    risk = RiskManager()
    ceo = PortfolioCEO(quant, risk)

    results = {}

    for symbol in symbols:
        logger.info(f"\n{'='*50}")
        logger.info(f"Analyzing {symbol}")
        logger.info("=" * 50)

        # Fetch data
        data = fetcher.get_stock_data(symbol, period="1y")
        if data.empty:
            logger.warning(f"No data for {symbol}")
            continue

        current_price = data["close"].iloc[-1]
        logger.info(f"Current price: ${current_price:.2f}")

        # Get analyst signals
        signals = []

        tech_signal = technical.analyze(symbol, data)
        signals.append(tech_signal)
        logger.info(f"  Technical: {tech_signal.value:.2f} ({tech_signal.signal_type.value})")

        sent_signal = sentiment.analyze(symbol, data)
        signals.append(sent_signal)
        logger.info(f"  Sentiment: {sent_signal.value:.2f} ({sent_signal.signal_type.value})")

        ml_signal = ml.analyze(symbol, data)
        signals.append(ml_signal)
        logger.info(f"  ML Pred:   {ml_signal.value:.2f} ({ml_signal.signal_type.value})")

        # Get CEO decision
        decision = ceo.make_trade_decision(symbol, signals, current_price)

        logger.info(f"\n  CEO Decision: {decision.action.value.upper()}")
        logger.info(f"  Signal: {decision.signal_value:.2f}, Confidence: {decision.confidence:.2f}")

        if decision.approved:
            logger.info(f"  Quantity: {decision.quantity:.2f} shares")
            if decision.stop_loss:
                logger.info(f"  Stop Loss: ${decision.stop_loss:.2f}")
            if decision.take_profit:
                logger.info(f"  Take Profit: ${decision.take_profit:.2f}")

        results[symbol] = {
            "price": current_price,
            "decision": decision,
            "signals": {s.agent_name: s.value for s in signals},
        }

    return results


def run_backtest(symbols: list[str], start: str, end: str):
    """Run historical backtest."""
    logger.info(f"Running backtest: {symbols}")
    logger.info(f"Period: {start} to {end}")

    backtester = Backtester(initial_capital=100000)
    results = backtester.run(symbols, start, end, rebalance_frequency="weekly")

    if "error" in results:
        logger.error(results["error"])
        return

    metrics = results["metrics"]
    logger.info("\n" + metrics.summary())

    # Compare to benchmark
    comparison = backtester.compare_to_benchmark("SPY")
    if "error" not in comparison:
        logger.info(f"\nBenchmark Comparison (vs SPY):")
        logger.info(f"  Strategy Return: {comparison['strategy_return']*100:.2f}%")
        logger.info(f"  Benchmark Return: {comparison['benchmark_return']*100:.2f}%")
        logger.info(f"  Alpha: {comparison['alpha_annual']*100:.2f}%")
        logger.info(f"  Beta: {comparison['beta']:.2f}")

    return results


def run_trading_loop(symbols: list[str]):
    """Run paper trading loop (simulated)."""
    logger.info("Starting paper trading loop...")
    logger.info(f"Symbols: {symbols}")

    paper = PaperTrader()
    order_mgr = OrderManager()

    # Show initial portfolio
    summary = paper.get_portfolio_summary()
    logger.info(f"\nInitial Portfolio:")
    logger.info(f"  Cash: ${summary['cash']:.2f}")
    logger.info(f"  Total Value: ${summary['total_value']:.2f}")

    # Run one analysis cycle
    results = analyze_stocks(symbols)

    logger.info("\nPaper trading loop complete.")
    logger.info("In production, this would run continuously.")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Stock Predictor AI Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --analyze AAPL NVDA TSLA
  python main.py --backtest --start 2024-01-01 --end 2024-12-31
  python main.py --trade
  python main.py --portfolio
        """,
    )

    parser.add_argument("--analyze", nargs="+", metavar="SYMBOL",
                        help="Analyze specific stocks")
    parser.add_argument("--backtest", action="store_true",
                        help="Run backtest mode")
    parser.add_argument("--trade", action="store_true",
                        help="Start paper trading loop")
    parser.add_argument("--portfolio", action="store_true",
                        help="Show current paper portfolio")
    parser.add_argument("--start", default="2024-01-01",
                        help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--symbols", nargs="+",
                        help="Override watchlist symbols")

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  Stock Predictor - AI Trading System")
    logger.info("  Mode: " + ("LIVE" if config.is_live else "PAPER"))
    logger.info("=" * 60)

    # Initialize database
    db = Database()

    # Get symbols
    symbols = args.symbols or config.watchlist

    if args.analyze:
        analyze_stocks(args.analyze)

    elif args.backtest:
        run_backtest(symbols, args.start, args.end)

    elif args.trade:
        run_trading_loop(symbols)

    elif args.portfolio:
        paper = PaperTrader()
        summary = paper.get_portfolio_summary()

        logger.info("\nPaper Portfolio:")
        logger.info(f"  Cash: ${summary['cash']:,.2f}")
        logger.info(f"  Positions Value: ${summary['positions_value']:,.2f}")
        logger.info(f"  Total Value: ${summary['total_value']:,.2f}")
        logger.info(f"  P&L: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:.2f}%)")

        if summary['positions']:
            logger.info("\n  Positions:")
            for pos in summary['positions']:
                logger.info(
                    f"    {pos['symbol']}: {pos['quantity']:.2f} @ ${pos['avg_cost']:.2f} "
                    f"-> ${pos['current_price']:.2f} ({pos['unrealized_pnl_pct']:.1f}%)"
                )

    else:
        # Default: analyze watchlist
        logger.info(f"\nAnalyzing watchlist: {symbols[:3]}...")  # Limit to 3 for demo
        analyze_stocks(symbols[:3])


if __name__ == "__main__":
    main()
