"""Sentiment Analysis Agent."""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import re

from .base_agent import BaseAgent, AgentSignal
from ..utils import config, get_logger


class SentimentAnalyst(BaseAgent):
    """
    Agent that analyzes market sentiment from various sources.

    Sources:
    - News headlines (via NewsAPI or similar)
    - Basic price action sentiment
    - Volume-based sentiment

    Note: For production, integrate with:
    - NewsAPI for headlines
    - FinBERT for financial sentiment analysis
    - Social media APIs (Twitter, Reddit)
    """

    def __init__(self, weight: float = None):
        weight = weight or config.get("agents.sentiment.weight", 0.25)
        super().__init__("sentiment_analyst", weight)
        self._sentiment_cache = {}

    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """Analyze sentiment for a stock."""
        if len(data) < 10:
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.1,
                agent_name=self.name,
                reasoning={"error": "Insufficient data"}
            )

        signals = {}

        # Price momentum sentiment
        momentum_signal = self._analyze_price_momentum(data)
        signals["momentum"] = momentum_signal

        # Volume sentiment
        volume_signal = self._analyze_volume_sentiment(data)
        signals["volume"] = volume_signal

        # Volatility sentiment
        volatility_signal = self._analyze_volatility(data)
        signals["volatility"] = volatility_signal

        # Gap analysis (overnight sentiment)
        gap_signal = self._analyze_gaps(data)
        signals["gaps"] = gap_signal

        # Weighted combination
        weights = {
            "momentum": 0.35,
            "volume": 0.25,
            "volatility": 0.20,
            "gaps": 0.20,
        }

        final_value = sum(signals[k] * weights[k] for k in weights)
        confidence = self._calculate_confidence(data, signals)

        reasoning = {
            "momentum": f"{momentum_signal:.2f}",
            "volume": f"{volume_signal:.2f}",
            "volatility": f"{volatility_signal:.2f}",
            "gaps": f"{gap_signal:.2f}",
            "note": "Sentiment based on price action (news integration pending)",
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

    def _analyze_price_momentum(self, data: pd.DataFrame) -> float:
        """Analyze recent price momentum as sentiment indicator."""
        closes = data["close"]

        # Short-term momentum (5 days)
        short_return = (closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5]

        # Medium-term momentum (20 days)
        if len(closes) >= 20:
            med_return = (closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]
        else:
            med_return = short_return

        # Streak analysis (consecutive up/down days)
        streak = 0
        for i in range(-1, -min(10, len(closes)), -1):
            if closes.iloc[i] > closes.iloc[i - 1]:
                if streak >= 0:
                    streak += 1
                else:
                    break
            else:
                if streak <= 0:
                    streak -= 1
                else:
                    break

        streak_signal = streak * 0.1  # 10% per day of streak

        # Combine
        signal = (short_return * 2) + (med_return * 1) + streak_signal
        return max(-1.0, min(1.0, signal))

    def _analyze_volume_sentiment(self, data: pd.DataFrame) -> float:
        """Analyze volume patterns as sentiment indicator."""
        if "volume" not in data.columns:
            return 0.0

        closes = data["close"]
        volumes = data["volume"]

        # Up volume vs down volume
        up_vol = 0
        down_vol = 0

        for i in range(-10, 0):
            if i - 1 < -len(closes):
                continue
            if closes.iloc[i] > closes.iloc[i - 1]:
                up_vol += volumes.iloc[i]
            else:
                down_vol += volumes.iloc[i]

        total_vol = up_vol + down_vol
        if total_vol == 0:
            return 0.0

        # Up/down volume ratio
        ratio = (up_vol - down_vol) / total_vol

        # Volume trend
        recent_avg = volumes.iloc[-5:].mean()
        older_avg = volumes.iloc[-20:-5].mean() if len(volumes) >= 20 else recent_avg

        vol_trend = 0.0
        if older_avg > 0:
            vol_change = (recent_avg - older_avg) / older_avg
            # Increasing volume with positive ratio = bullish
            if vol_change > 0.2 and ratio > 0:
                vol_trend = 0.3
            elif vol_change > 0.2 and ratio < 0:
                vol_trend = -0.3

        return max(-1.0, min(1.0, ratio + vol_trend))

    def _analyze_volatility(self, data: pd.DataFrame) -> float:
        """Analyze volatility as sentiment indicator."""
        closes = data["close"]

        # Calculate recent volatility
        returns = closes.pct_change().dropna()

        if len(returns) < 10:
            return 0.0

        recent_vol = returns.iloc[-10:].std()
        historical_vol = returns.std()

        if historical_vol == 0:
            return 0.0

        vol_ratio = recent_vol / historical_vol

        # High volatility = uncertainty (slightly bearish)
        # Low volatility = complacency (neutral to slightly bullish)
        if vol_ratio > 1.5:
            return -0.3  # High recent volatility
        elif vol_ratio < 0.7:
            return 0.2  # Low volatility, calm market
        else:
            return 0.0

    def _analyze_gaps(self, data: pd.DataFrame) -> float:
        """Analyze gap patterns (overnight sentiment)."""
        if "open" not in data.columns:
            return 0.0

        opens = data["open"]
        closes = data["close"]

        # Recent gaps
        gap_signal = 0.0
        weights = [0.4, 0.3, 0.2, 0.1]  # Most recent gaps weighted higher

        for i, w in enumerate(weights):
            idx = -1 - i
            prev_idx = -2 - i

            if prev_idx < -len(closes):
                continue

            gap = (opens.iloc[idx] - closes.iloc[prev_idx]) / closes.iloc[prev_idx]

            if abs(gap) > 0.01:  # Only count significant gaps
                gap_signal += gap * w * 10  # Scale up

        return max(-1.0, min(1.0, gap_signal))

    def _calculate_confidence(self, data: pd.DataFrame, signals: dict) -> float:
        """Calculate confidence in sentiment analysis."""
        # Base confidence on data quality and signal agreement
        base_confidence = 0.4  # Lower base since we lack news data

        # Add if we have good volume data
        if "volume" in data.columns and data["volume"].iloc[-10:].mean() > 0:
            base_confidence += 0.2

        # Check signal agreement
        values = list(signals.values())
        if values:
            same_direction = all(v >= 0 for v in values) or all(v <= 0 for v in values)
            if same_direction:
                base_confidence += 0.2

        return min(0.8, base_confidence)  # Cap at 0.8 without news data

    # Placeholder for news integration
    def analyze_news(self, symbol: str, headlines: List[str]) -> float:
        """
        Analyze news headlines for sentiment.

        TODO: Integrate with FinBERT or similar model:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
        """
        if not headlines:
            return 0.0

        # Basic keyword sentiment (placeholder)
        positive_words = ["surge", "jump", "rally", "gain", "beat", "upgrade", "bullish"]
        negative_words = ["fall", "drop", "crash", "miss", "downgrade", "bearish", "concern"]

        score = 0
        for headline in headlines:
            headline_lower = headline.lower()
            for word in positive_words:
                if word in headline_lower:
                    score += 1
            for word in negative_words:
                if word in headline_lower:
                    score -= 1

        if len(headlines) > 0:
            return max(-1.0, min(1.0, score / len(headlines)))
        return 0.0
