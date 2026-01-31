"""Technical Analysis Agent."""
import pandas as pd
import numpy as np
from typing import Optional

from .base_agent import BaseAgent, AgentSignal
from ..utils import config


class TechnicalAnalyst(BaseAgent):
    """
    Agent that performs technical analysis on price data.

    Uses indicators:
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Bollinger Bands
    - Moving Average Crossovers
    - Volume analysis
    """

    def __init__(self, weight: float = None):
        weight = weight or config.get("agents.technical.weight", 0.25)
        super().__init__("technical_analyst", weight)

    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """Analyze price data using technical indicators."""
        if len(data) < 50:
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.1,
                agent_name=self.name,
                reasoning={"error": "Insufficient data for analysis"}
            )

        # Calculate all indicators
        indicators = {}

        # RSI
        rsi = self._calculate_rsi(data["close"], period=14)
        rsi_signal = self._interpret_rsi(rsi)
        indicators["rsi"] = {"value": rsi, "signal": rsi_signal}

        # MACD
        macd, signal_line, histogram = self._calculate_macd(data["close"])
        macd_signal = self._interpret_macd(macd, signal_line, histogram)
        indicators["macd"] = {
            "macd": macd, "signal": signal_line,
            "histogram": histogram, "signal_value": macd_signal
        }

        # Bollinger Bands
        upper, middle, lower = self._calculate_bollinger(data["close"])
        bb_signal = self._interpret_bollinger(data["close"].iloc[-1], upper, middle, lower)
        indicators["bollinger"] = {
            "upper": upper, "middle": middle, "lower": lower, "signal": bb_signal
        }

        # Moving Average Crossover
        sma_20 = data["close"].rolling(20).mean().iloc[-1]
        sma_50 = data["close"].rolling(50).mean().iloc[-1]
        ma_signal = self._interpret_ma_crossover(data["close"].iloc[-1], sma_20, sma_50)
        indicators["ma_crossover"] = {
            "sma_20": sma_20, "sma_50": sma_50, "signal": ma_signal
        }

        # Volume analysis
        vol_signal = self._analyze_volume(data)
        indicators["volume"] = {"signal": vol_signal}

        # Aggregate signals
        signals = [
            rsi_signal * 0.25,
            macd_signal * 0.25,
            bb_signal * 0.2,
            ma_signal * 0.2,
            vol_signal * 0.1,
        ]

        final_value = sum(signals)
        confidence = self._calculate_confidence(indicators)

        reasoning = {
            "rsi": f"{rsi:.1f} -> {rsi_signal:.2f}",
            "macd": f"histogram={histogram:.4f} -> {macd_signal:.2f}",
            "bollinger": f"{bb_signal:.2f}",
            "ma_crossover": f"price vs SMA20/50 -> {ma_signal:.2f}",
            "volume": f"{vol_signal:.2f}",
            "final": f"{final_value:.2f}",
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

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _interpret_rsi(self, rsi: float) -> float:
        """
        Interpret RSI value.
        RSI > 70: Overbought (sell signal)
        RSI < 30: Oversold (buy signal)
        """
        if rsi >= 80:
            return -0.8  # Strong sell
        elif rsi >= 70:
            return -0.4  # Sell
        elif rsi <= 20:
            return 0.8  # Strong buy
        elif rsi <= 30:
            return 0.4  # Buy
        else:
            # Neutral zone - slight bias based on position
            return (50 - rsi) / 100  # Slight signal toward oversold/overbought

    def _calculate_macd(self, prices: pd.Series,
                        fast: int = 12, slow: int = 26, signal: int = 9):
        """Calculate MACD, signal line, and histogram."""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line

        return macd.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

    def _interpret_macd(self, macd: float, signal_line: float, histogram: float) -> float:
        """Interpret MACD values."""
        # Histogram direction is key
        if histogram > 0:
            if macd > signal_line:
                return min(0.6, histogram * 10)  # Bullish
            return 0.2
        else:
            if macd < signal_line:
                return max(-0.6, histogram * 10)  # Bearish
            return -0.2

    def _calculate_bollinger(self, prices: pd.Series, period: int = 20, std_dev: int = 2):
        """Calculate Bollinger Bands."""
        middle = prices.rolling(period).mean().iloc[-1]
        std = prices.rolling(period).std().iloc[-1]
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        return upper, middle, lower

    def _interpret_bollinger(self, price: float, upper: float,
                            middle: float, lower: float) -> float:
        """Interpret price position relative to Bollinger Bands."""
        band_width = upper - lower
        if band_width == 0:
            return 0.0

        # Position within bands (-1 to 1)
        position = (price - middle) / (band_width / 2)

        # Near lower band = buy, near upper = sell
        if price <= lower:
            return 0.6  # Below lower band - strong buy
        elif price >= upper:
            return -0.6  # Above upper band - strong sell
        else:
            return -position * 0.4  # Scale signal

    def _interpret_ma_crossover(self, price: float, sma_20: float, sma_50: float) -> float:
        """Interpret moving average crossover."""
        signal = 0.0

        # Price vs short-term MA
        if price > sma_20:
            signal += 0.3
        else:
            signal -= 0.3

        # Short vs long-term MA (golden/death cross)
        if sma_20 > sma_50:
            signal += 0.4  # Golden cross territory
        else:
            signal -= 0.4  # Death cross territory

        return max(-1.0, min(1.0, signal))

    def _analyze_volume(self, data: pd.DataFrame) -> float:
        """Analyze volume patterns."""
        if "volume" not in data.columns:
            return 0.0

        recent_vol = data["volume"].iloc[-5:].mean()
        avg_vol = data["volume"].iloc[-20:].mean()

        if avg_vol == 0:
            return 0.0

        vol_ratio = recent_vol / avg_vol

        # High volume with price increase = bullish
        # High volume with price decrease = bearish
        price_change = (data["close"].iloc[-1] - data["close"].iloc[-5]) / data["close"].iloc[-5]

        if vol_ratio > 1.5:  # High volume
            return 0.3 if price_change > 0 else -0.3
        elif vol_ratio < 0.5:  # Low volume
            return 0.0  # Low conviction either way

        return price_change * 0.2

    def _calculate_confidence(self, indicators: dict) -> float:
        """Calculate confidence based on indicator agreement."""
        signals = [
            indicators["rsi"]["signal"],
            indicators["macd"]["signal_value"],
            indicators["bollinger"]["signal"],
            indicators["ma_crossover"]["signal"],
        ]

        # Check if signals agree
        positive = sum(1 for s in signals if s > 0.1)
        negative = sum(1 for s in signals if s < -0.1)

        # Higher agreement = higher confidence
        agreement = max(positive, negative) / len(signals)

        # Also factor in signal strength
        avg_strength = np.mean([abs(s) for s in signals])

        return min(1.0, (agreement * 0.6) + (avg_strength * 0.4))
