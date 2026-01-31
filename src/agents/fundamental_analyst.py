"""Fundamental Analysis Agent."""
import pandas as pd
from typing import Optional

from .base_agent import BaseAgent, AgentSignal
from ..utils import config
from ..data import YahooFetcher


class FundamentalAnalyst(BaseAgent):
    """
    Agent that performs fundamental analysis on stocks.

    Analyzes:
    - Valuation (P/E, PEG, P/B ratios)
    - Profitability (margins, ROE, ROA)
    - Growth (revenue, earnings growth)
    - Financial health (debt ratios, current ratio)
    """

    def __init__(self, weight: float = None):
        weight = weight or config.get("agents.fundamental.weight", 0.25)
        super().__init__("fundamental_analyst", weight)
        self.fetcher = YahooFetcher()

    def analyze(self, symbol: str, data: pd.DataFrame = None) -> AgentSignal:
        """Analyze fundamental metrics for a stock."""
        try:
            fundamentals = self.fetcher.get_fundamentals(symbol)
        except Exception as e:
            self.logger.error(f"Error fetching fundamentals for {symbol}: {e}")
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.1,
                agent_name=self.name,
                reasoning={"error": str(e)}
            )

        signals = {}

        # Valuation analysis
        valuation_signal = self._analyze_valuation(fundamentals)
        signals["valuation"] = valuation_signal

        # Profitability analysis
        profitability_signal = self._analyze_profitability(fundamentals)
        signals["profitability"] = profitability_signal

        # Growth analysis
        growth_signal = self._analyze_growth(fundamentals)
        signals["growth"] = growth_signal

        # Financial health
        health_signal = self._analyze_financial_health(fundamentals)
        signals["financial_health"] = health_signal

        # Price vs moving averages (value indicator)
        ma_signal = self._analyze_price_vs_average(fundamentals)
        signals["price_vs_average"] = ma_signal

        # Weighted combination
        weights = {
            "valuation": 0.25,
            "profitability": 0.20,
            "growth": 0.25,
            "financial_health": 0.15,
            "price_vs_average": 0.15,
        }

        final_value = sum(signals[k] * weights[k] for k in weights)
        confidence = self._calculate_confidence(fundamentals, signals)

        reasoning = {
            "valuation": f"{valuation_signal:.2f}",
            "profitability": f"{profitability_signal:.2f}",
            "growth": f"{growth_signal:.2f}",
            "financial_health": f"{health_signal:.2f}",
            "price_vs_average": f"{ma_signal:.2f}",
            "pe_ratio": fundamentals.get("pe_ratio"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "sector": fundamentals.get("sector"),
        }

        signal = AgentSignal.from_value(
            symbol=symbol,
            value=final_value,
            confidence=confidence,
            agent_name=self.name,
            reasoning=reasoning,
        )

        self.save_signal(signal)
        self.logger.info(f"{symbol}: signal={final_value:.2f}, confidence={confidence:.2f}")

        return signal

    def _analyze_valuation(self, f: dict) -> float:
        """Analyze valuation metrics."""
        signal = 0.0
        count = 0

        # P/E Ratio
        pe = f.get("pe_ratio")
        if pe is not None:
            if pe < 0:
                signal -= 0.3  # Negative earnings
            elif pe < 15:
                signal += 0.5  # Undervalued
            elif pe < 25:
                signal += 0.1  # Fair value
            elif pe < 40:
                signal -= 0.2  # Expensive
            else:
                signal -= 0.5  # Very expensive
            count += 1

        # Forward P/E
        forward_pe = f.get("forward_pe")
        if forward_pe is not None and forward_pe > 0:
            if forward_pe < pe if pe else 0:
                signal += 0.2  # Expected earnings growth
            count += 1

        # PEG Ratio
        peg = f.get("peg_ratio")
        if peg is not None:
            if peg < 1:
                signal += 0.4  # Undervalued relative to growth
            elif peg < 2:
                signal += 0.1  # Fair
            else:
                signal -= 0.3  # Overvalued relative to growth
            count += 1

        return signal / max(count, 1)

    def _analyze_profitability(self, f: dict) -> float:
        """Analyze profitability metrics."""
        signal = 0.0
        count = 0

        # Profit margin
        margin = f.get("profit_margin")
        if margin is not None:
            if margin > 0.20:
                signal += 0.5  # High margin
            elif margin > 0.10:
                signal += 0.2  # Good margin
            elif margin > 0:
                signal -= 0.1  # Low margin
            else:
                signal -= 0.4  # Negative margin
            count += 1

        return signal / max(count, 1)

    def _analyze_growth(self, f: dict) -> float:
        """Analyze growth metrics."""
        signal = 0.0
        count = 0

        # Revenue growth
        rev_growth = f.get("revenue_growth")
        if rev_growth is not None:
            if rev_growth > 0.25:
                signal += 0.6  # High growth
            elif rev_growth > 0.10:
                signal += 0.3  # Good growth
            elif rev_growth > 0:
                signal += 0.1  # Slow growth
            else:
                signal -= 0.3  # Declining revenue
            count += 1

        # Earnings growth
        earn_growth = f.get("earnings_growth")
        if earn_growth is not None:
            if earn_growth > 0.25:
                signal += 0.5
            elif earn_growth > 0.10:
                signal += 0.2
            elif earn_growth > 0:
                signal += 0.1
            else:
                signal -= 0.3
            count += 1

        return signal / max(count, 1)

    def _analyze_financial_health(self, f: dict) -> float:
        """Analyze financial health metrics."""
        signal = 0.0
        count = 0

        # Debt to equity
        dte = f.get("debt_to_equity")
        if dte is not None:
            if dte < 0.5:
                signal += 0.4  # Low debt
            elif dte < 1.0:
                signal += 0.1  # Moderate debt
            elif dte < 2.0:
                signal -= 0.2  # High debt
            else:
                signal -= 0.5  # Very high debt
            count += 1

        # Current ratio
        current = f.get("current_ratio")
        if current is not None:
            if current > 2.0:
                signal += 0.3  # Strong liquidity
            elif current > 1.0:
                signal += 0.1  # Adequate liquidity
            else:
                signal -= 0.4  # Liquidity risk
            count += 1

        return signal / max(count, 1)

    def _analyze_price_vs_average(self, f: dict) -> float:
        """Analyze price relative to moving averages and 52-week range."""
        signal = 0.0

        high_52 = f.get("52_week_high")
        low_52 = f.get("52_week_low")
        avg_50 = f.get("50_day_avg")
        avg_200 = f.get("200_day_avg")

        # Check position in 52-week range
        if high_52 and low_52 and avg_50:
            range_52 = high_52 - low_52
            if range_52 > 0:
                position = (avg_50 - low_52) / range_52
                # Near 52-week low = potential value
                # Near 52-week high = potential overvalued
                signal += (0.5 - position) * 0.4

        # Price vs 200-day average
        if avg_50 and avg_200:
            if avg_50 > avg_200:
                signal += 0.2  # Above 200 MA (uptrend)
            else:
                signal -= 0.2  # Below 200 MA (downtrend)

        return max(-1.0, min(1.0, signal))

    def _calculate_confidence(self, fundamentals: dict, signals: dict) -> float:
        """Calculate confidence based on data availability."""
        # Count available metrics
        key_metrics = ["pe_ratio", "revenue_growth", "profit_margin", "debt_to_equity"]
        available = sum(1 for m in key_metrics if fundamentals.get(m) is not None)

        # More data = higher confidence
        data_confidence = available / len(key_metrics)

        # Signal agreement
        values = list(signals.values())
        agreement = 1 - (max(values) - min(values)) / 2 if values else 0.5

        return (data_confidence * 0.6) + (agreement * 0.4)
