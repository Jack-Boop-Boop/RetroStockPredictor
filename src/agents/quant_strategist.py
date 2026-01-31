"""Quantitative Strategist Agent."""
from typing import List, Dict
import pandas as pd
import numpy as np

from .base_agent import DecisionAgent, AgentSignal, BaseAgent
from ..utils import config, get_logger


class QuantStrategist(DecisionAgent):
    """
    Quantitative strategist that aggregates and weighs analyst signals.

    Responsibilities:
    - Collect signals from all analyst agents
    - Apply configurable weights
    - Consider signal correlations
    - Generate unified trading recommendation
    """

    def __init__(self, analyst_agents: List[BaseAgent] = None):
        super().__init__("quant_strategist", analyst_agents)

        # Default weights from config
        self.weights = {
            "technical_analyst": config.get("agents.technical.weight", 0.25),
            "fundamental_analyst": config.get("agents.fundamental.weight", 0.25),
            "sentiment_analyst": config.get("agents.sentiment.weight", 0.25),
            "ml_predictor": config.get("agents.ml.weight", 0.25),
        }

    def decide(self, symbol: str, signals: List[AgentSignal]) -> AgentSignal:
        """
        Aggregate analyst signals into a unified recommendation.

        Uses weighted average with dynamic confidence adjustment.
        """
        if not signals:
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.0,
                agent_name=self.name,
                reasoning={"error": "No analyst signals received"}
            )

        # Organize signals by agent
        signal_map = {s.agent_name: s for s in signals}

        # Calculate weighted signal
        weighted_sum = 0.0
        weight_total = 0.0
        contributions = {}

        for agent_name, signal in signal_map.items():
            weight = self.weights.get(agent_name, 0.25)
            contribution = signal.value * signal.confidence * weight
            weighted_sum += contribution
            weight_total += weight * signal.confidence
            contributions[agent_name] = {
                "signal": signal.value,
                "confidence": signal.confidence,
                "weight": weight,
                "contribution": contribution,
            }

        # Normalized weighted average
        if weight_total > 0:
            final_value = weighted_sum / weight_total
        else:
            final_value = 0.0

        # Calculate aggregate confidence
        # Higher when signals agree, lower when they diverge
        signal_values = [s.value for s in signals]
        signal_std = np.std(signal_values) if len(signal_values) > 1 else 0

        # Agreement factor: 1 when all agree, lower when they diverge
        agreement = max(0, 1 - signal_std)

        # Average confidence of analysts
        avg_confidence = np.mean([s.confidence for s in signals])

        # Final confidence
        final_confidence = avg_confidence * agreement

        # Determine consensus type
        bullish = sum(1 for s in signals if s.value > 0.1)
        bearish = sum(1 for s in signals if s.value < -0.1)
        neutral = len(signals) - bullish - bearish

        if bullish > bearish and bullish > neutral:
            consensus = "bullish"
        elif bearish > bullish and bearish > neutral:
            consensus = "bearish"
        else:
            consensus = "mixed"

        reasoning = {
            "weighted_signal": f"{final_value:.3f}",
            "agreement_factor": f"{agreement:.3f}",
            "consensus": consensus,
            "votes": {"bullish": bullish, "bearish": bearish, "neutral": neutral},
            "contributions": contributions,
        }

        signal = AgentSignal.from_value(
            symbol=symbol,
            value=final_value,
            confidence=final_confidence,
            agent_name=self.name,
            reasoning=reasoning,
        )

        self.save_signal(signal)
        self.logger.info(
            f"{symbol}: consensus={consensus}, signal={final_value:.2f}, "
            f"confidence={final_confidence:.2f}"
        )

        return signal

    def set_weights(self, weights: Dict[str, float]):
        """Update agent weights."""
        self.weights.update(weights)
        self.logger.info(f"Updated weights: {self.weights}")

    def get_signal_breakdown(self, symbol: str, signals: List[AgentSignal]) -> Dict:
        """Get detailed breakdown of signals for reporting."""
        breakdown = {
            "symbol": symbol,
            "timestamp": signals[0].timestamp.isoformat() if signals else None,
            "agents": {},
            "summary": {},
        }

        for signal in signals:
            breakdown["agents"][signal.agent_name] = {
                "value": signal.value,
                "confidence": signal.confidence,
                "type": signal.signal_type.value,
                "reasoning": signal.reasoning,
            }

        # Calculate summary stats
        values = [s.value for s in signals]
        breakdown["summary"] = {
            "mean": np.mean(values),
            "std": np.std(values),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
        }

        return breakdown
