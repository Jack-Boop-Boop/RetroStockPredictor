"""Yahoo Finance data fetcher."""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from ..utils import config, get_logger
from .database import Database, StockPrice

logger = get_logger(__name__)


class YahooFetcher:
    """Fetch stock data from Yahoo Finance."""

    def __init__(self):
        self.db = Database()

    def get_stock_data(
        self,
        symbol: str,
        period: str = None,
        interval: str = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical stock data.

        Args:
            symbol: Stock ticker symbol
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
            start: Start date (alternative to period)
            end: End date (alternative to period)

        Returns:
            DataFrame with OHLCV data
        """
        period = period or config.get("data.yahoo.default_period", "1y")
        interval = interval or config.get("data.yahoo.default_interval", "1d")

        logger.info(f"Fetching {symbol} data: period={period}, interval={interval}")

        ticker = yf.Ticker(symbol)

        if start and end:
            df = ticker.history(start=start, end=end, interval=interval)
        else:
            df = ticker.history(period=period, interval=interval)

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return df

        # Standardize column names
        df.columns = [col.lower().replace(" ", "_") for col in df.columns]

        # Add symbol column
        df["symbol"] = symbol

        logger.info(f"Fetched {len(df)} records for {symbol}")
        return df

    def get_fundamentals(self, symbol: str) -> dict:
        """
        Fetch fundamental data for a stock.

        Returns dict with keys:
        - pe_ratio, forward_pe, peg_ratio
        - market_cap, enterprise_value
        - profit_margin, revenue_growth
        - debt_to_equity, current_ratio
        - dividend_yield, beta
        """
        logger.info(f"Fetching fundamentals for {symbol}")
        ticker = yf.Ticker(symbol)
        info = ticker.info

        fundamentals = {
            "symbol": symbol,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "profit_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "50_day_avg": info.get("fiftyDayAverage"),
            "200_day_avg": info.get("twoHundredDayAverage"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

        return fundamentals

    def get_realtime_price(self, symbol: str) -> dict:
        """Get current price and basic info."""
        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            "symbol": symbol,
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "previous_close": info.get("previousClose"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "day_low": info.get("dayLow") or info.get("regularMarketDayLow"),
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "market_cap": info.get("marketCap"),
            "change_pct": info.get("regularMarketChangePercent"),
        }

    def save_to_db(self, df: pd.DataFrame, symbol: str):
        """Save price data to database."""
        for idx, row in df.iterrows():
            self.db.save_price(
                symbol=symbol,
                date=idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx,
                open_=row.get("open"),
                high=row.get("high"),
                low=row.get("low"),
                close=row.get("close"),
                volume=int(row.get("volume", 0)),
                adj_close=row.get("adj_close", row.get("close")),
            )
        logger.info(f"Saved {len(df)} records for {symbol} to database")

    def fetch_and_save(self, symbol: str, **kwargs) -> pd.DataFrame:
        """Fetch data and save to database."""
        df = self.get_stock_data(symbol, **kwargs)
        if not df.empty:
            self.save_to_db(df, symbol)
        return df

    def get_multiple(self, symbols: list[str], **kwargs) -> dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols."""
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.get_stock_data(symbol, **kwargs)
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                results[symbol] = pd.DataFrame()
        return results
