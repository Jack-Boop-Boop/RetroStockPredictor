"""Risk Management Agent."""
from dataclasses import dataclass
from typing import Optional, Dict, List
import pandas as pd

from .base_agent import DecisionAgent, AgentSignal
from ..utils import config, get_logger
from ..data import Database


@dataclass
class RiskAssessment:
    """Risk assessment for a potential trade."""
    symbol: str
    approved: bool
    original_signal: float
    adjusted_signal: float
    max_position_size: float
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]
    risk_factors: Dict[str, str]
    warnings: List[str]


class RiskManager(DecisionAgent):
    """
    Risk management agent that evaluates and adjusts trading signals.

    Responsibilities:
    - Position size limits
    - Stop-loss enforcement
    - Correlation checks
    - Drawdown limits
    - Volatility adjustment
    """

    def __init__(self):
        super().__init__("risk_manager")
        self.max_position_pct = config.get("trading.max_position_pct", 0.1)
        self.stop_loss_pct = config.get("trading.stop_loss_pct", 0.05)
        self.take_profit_pct = config.get("trading.take_profit_pct", 0.15)
        self.max_portfolio_risk = config.get("risk.max_portfolio_risk", 0.02)
        self.min_signal_strength = config.get("risk.min_signal_strength", 0.3)

        # Track current positions (in production, fetch from broker)
        self._positions: Dict[str, float] = {}
        self._portfolio_value: float = 100000  # Default paper portfolio

    def decide(self, symbol: str, signals: List[AgentSignal]) -> AgentSignal:
        """Make risk-adjusted decision based on analyst signals."""
        if not signals:
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.0,
                agent_name=self.name,
                reasoning={"error": "No signals to evaluate"}
            )

        # Aggregate incoming signals
        total_weight = sum(s.confidence for s in signals)
        if total_weight == 0:
            aggregated_value = 0.0
        else:
            aggregated_value = sum(s.value * s.confidence for s in signals) / total_weight

        aggregated_confidence = sum(s.confidence for s in signals) / len(signals)

        # Perform risk checks
        risk_factors = {}
        warnings = []
        approved = True
        adjusted_value = aggregated_value

        # Check 1: Signal strength threshold
        if abs(aggregated_value) < self.min_signal_strength:
            risk_factors["signal_strength"] = f"Below threshold ({self.min_signal_strength})"
            adjusted_value = 0.0  # Don't trade on weak signals

        # Check 2: Confidence threshold
        if aggregated_confidence < 0.3:
            risk_factors["low_confidence"] = f"Confidence {aggregated_confidence:.2f} < 0.3"
            adjusted_value *= 0.5  # Reduce signal on low confidence
            warnings.append("Low confidence - position reduced")

        # Check 3: Existing position check
        current_position = self._positions.get(symbol, 0)
        if current_position != 0:
            if (current_position > 0 and aggregated_value > 0) or \
               (current_position < 0 and aggregated_value < 0):
                risk_factors["existing_position"] = "Already have position in same direction"
                warnings.append("Consider adding to existing position carefully")

        # Check 4: Signal agreement
        positive_signals = sum(1 for s in signals if s.value > 0)
        negative_signals = sum(1 for s in signals if s.value < 0)

        if positive_signals > 0 and negative_signals > 0:
            agreement = abs(positive_signals - negative_signals) / len(signals)
            if agreement < 0.5:
                risk_factors["mixed_signals"] = f"Analyst disagreement: {positive_signals} bullish, {negative_signals} bearish"
                adjusted_value *= 0.7
                warnings.append("Mixed analyst signals - proceed with caution")

        reasoning = {
            "original_signal": f"{aggregated_value:.2f}",
            "adjusted_signal": f"{adjusted_value:.2f}",
            "confidence": f"{aggregated_confidence:.2f}",
            "risk_factors": risk_factors,
            "warnings": warnings,
            "approved": abs(adjusted_value) >= self.min_signal_strength,
            "analyst_signals": {s.agent_name: s.value for s in signals},
        }

        signal = AgentSignal.from_value(
            symbol=symbol,
            value=adjusted_value,
            confidence=aggregated_confidence * 0.9,  # Slight confidence reduction
            agent_name=self.name,
            reasoning=reasoning,
        )

        self.save_signal(signal)
        return signal

    def assess_trade(self, symbol: str, signal: AgentSignal,
                     current_price: float) -> RiskAssessment:
        """
        Perform full risk assessment for a trade.

        Returns detailed RiskAssessment with position sizing and stops.
        """
        warnings = []
        risk_factors = {}
        approved = True

        # Calculate position size based on signal strength and risk
        max_risk_amount = self._portfolio_value * self.max_portfolio_risk
        stop_distance = current_price * self.stop_loss_pct

        # Position size = risk amount / stop distance
        base_position_size = max_risk_amount / stop_distance

        # Adjust by signal strength
        position_size = base_position_size * abs(signal.value)

        # Cap at max position percentage
        max_position_value = self._portfolio_value * self.max_position_pct
        max_shares = max_position_value / current_price

        if position_size > max_shares:
            position_size = max_shares
            risk_factors["position_capped"] = f"Capped at {self.max_position_pct * 100}% of portfolio"

        # Calculate stops
        if signal.value > 0:  # Long position
            stop_loss = current_price * (1 - self.stop_loss_pct)
            take_profit = current_price * (1 + self.take_profit_pct)
        else:  # Short position (if supported)
            stop_loss = current_price * (1 + self.stop_loss_pct)
            take_profit = current_price * (1 - self.take_profit_pct)

        # Final approval check
        if abs(signal.value) < self.min_signal_strength:
            approved = False
            warnings.append(f"Signal {signal.value:.2f} below minimum {self.min_signal_strength}")

        return RiskAssessment(
            symbol=symbol,
            approved=approved,
            original_signal=signal.value,
            adjusted_signal=signal.value,
            max_position_size=position_size,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_factors=risk_factors,
            warnings=warnings,
        )

    def update_position(self, symbol: str, quantity: float):
        """Update tracked position for a symbol."""
        self._positions[symbol] = self._positions.get(symbol, 0) + quantity

    def set_portfolio_value(self, value: float):
        """Update portfolio value for position sizing."""
        self._portfolio_value = value

    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """Analyze is not directly used - use decide() instead."""
        return AgentSignal.from_value(
            symbol=symbol, value=0.0, confidence=0.0,
            agent_name=self.name,
            reasoning={"note": "Use decide() method with analyst signals"}
        )
