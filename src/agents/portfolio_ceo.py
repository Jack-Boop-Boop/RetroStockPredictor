"""Portfolio CEO Agent - Final Decision Maker."""
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import pandas as pd

from .base_agent import DecisionAgent, AgentSignal, BaseAgent
from .risk_manager import RiskManager, RiskAssessment
from .quant_strategist import QuantStrategist
from ..utils import config, get_logger, log_trade


class TradeAction(Enum):
    """Possible trade actions."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"  # Close existing position


@dataclass
class TradeDecision:
    """Final trade decision from Portfolio CEO."""
    symbol: str
    action: TradeAction
    quantity: float
    confidence: float
    signal_value: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: Dict
    approved: bool


class PortfolioCEO(DecisionAgent):
    """
    Portfolio CEO - The final decision maker in the agent hierarchy.

    Responsibilities:
    - Receive aggregated signals from Quant Strategist
    - Apply risk management from Risk Manager
    - Make final trade/no-trade decisions
    - Manage overall portfolio strategy
    - Override or veto signals when necessary
    """

    def __init__(self, quant: QuantStrategist = None, risk: RiskManager = None):
        super().__init__("portfolio_ceo")
        self.quant_strategist = quant or QuantStrategist()
        self.risk_manager = risk or RiskManager()

        # CEO parameters
        self.min_confidence_to_trade = 0.4
        self.max_concurrent_positions = 10
        self.min_signal_for_action = 0.2

        # Track decisions
        self._pending_decisions: Dict[str, TradeDecision] = {}
        self._decision_history: List[TradeDecision] = []

    def decide(self, symbol: str, signals: List[AgentSignal]) -> AgentSignal:
        """
        Make final decision based on quant and risk assessments.

        This is the top of the decision hierarchy.
        """
        # Get quant aggregation
        quant_signal = self.quant_strategist.decide(symbol, signals)

        # Get risk assessment
        risk_signal = self.risk_manager.decide(symbol, signals)

        # CEO decision logic
        ceo_value = self._make_ceo_decision(quant_signal, risk_signal)

        reasoning = {
            "quant_signal": quant_signal.value,
            "quant_confidence": quant_signal.confidence,
            "risk_adjusted_signal": risk_signal.value,
            "risk_warnings": risk_signal.reasoning.get("warnings", []),
            "ceo_decision": ceo_value,
            "analyst_breakdown": quant_signal.reasoning.get("contributions", {}),
        }

        # Final confidence is product of quant confidence and risk approval
        risk_approved = risk_signal.reasoning.get("approved", True)
        final_confidence = quant_signal.confidence * (1.0 if risk_approved else 0.5)

        signal = AgentSignal.from_value(
            symbol=symbol,
            value=ceo_value,
            confidence=final_confidence,
            agent_name=self.name,
            reasoning=reasoning,
        )

        self.save_signal(signal)
        self.logger.info(
            f"{symbol}: CEO decision={ceo_value:.2f}, confidence={final_confidence:.2f}"
        )

        return signal

    def _make_ceo_decision(self, quant: AgentSignal, risk: AgentSignal) -> float:
        """
        CEO's decision logic combining quant and risk signals.

        The CEO can:
        - Approve the signal as-is
        - Reduce the signal (more conservative)
        - Reject the signal entirely
        - Override in exceptional circumstances
        """
        # Start with risk-adjusted signal
        base_signal = risk.value

        # Apply CEO judgment
        quant_confidence = quant.confidence
        risk_approved = risk.reasoning.get("approved", True)

        if not risk_approved:
            # Risk manager rejected - CEO can override but applies penalty
            if quant_confidence > 0.8 and abs(quant.value) > 0.7:
                # Strong conviction - allow reduced signal
                self.logger.warning(f"CEO override: Risk rejected but quant confidence high")
                return base_signal * 0.5
            else:
                # Respect risk manager's judgment
                return 0.0

        # Check for conflicting signals
        quant_direction = 1 if quant.value > 0 else -1
        risk_direction = 1 if risk.value > 0 else -1

        if quant_direction != risk_direction and abs(quant.value) > 0.1 and abs(risk.value) > 0.1:
            # Conflicting directions - be conservative
            self.logger.info("Quant and risk signals conflict - reducing position")
            return base_signal * 0.5

        # Normal case - use risk-adjusted signal with confidence scaling
        confidence_factor = min(1.0, quant_confidence + 0.2)  # Slight boost for reaching CEO
        return base_signal * confidence_factor

    def make_trade_decision(
        self,
        symbol: str,
        analyst_signals: List[AgentSignal],
        current_price: float,
        current_position: float = 0,
    ) -> TradeDecision:
        """
        Make a complete trade decision with position sizing.

        This is the main entry point for the trading system.
        """
        # Get CEO signal
        ceo_signal = self.decide(symbol, analyst_signals)

        # Get risk assessment for position sizing
        risk_assessment = self.risk_manager.assess_trade(
            symbol, ceo_signal, current_price
        )

        # Determine action
        action, quantity = self._determine_action(
            ceo_signal, risk_assessment, current_position
        )

        decision = TradeDecision(
            symbol=symbol,
            action=action,
            quantity=quantity,
            confidence=ceo_signal.confidence,
            signal_value=ceo_signal.value,
            stop_loss=risk_assessment.stop_loss_price if action != TradeAction.HOLD else None,
            take_profit=risk_assessment.take_profit_price if action != TradeAction.HOLD else None,
            reasoning=ceo_signal.reasoning,
            approved=risk_assessment.approved and action != TradeAction.HOLD,
        )

        # Log and track
        self._pending_decisions[symbol] = decision
        self._decision_history.append(decision)

        if decision.approved:
            log_trade(
                f"DECISION: {action.value.upper()} {quantity:.2f} {symbol} @ ${current_price:.2f} "
                f"(signal={ceo_signal.value:.2f}, conf={ceo_signal.confidence:.2f})"
            )
        else:
            self.logger.info(f"{symbol}: HOLD - no action taken")

        return decision

    def _determine_action(
        self,
        signal: AgentSignal,
        risk: RiskAssessment,
        current_position: float,
    ) -> tuple[TradeAction, float]:
        """Determine the trade action and quantity."""
        signal_value = signal.value
        confidence = signal.confidence

        # Check minimum thresholds
        if abs(signal_value) < self.min_signal_for_action:
            return TradeAction.HOLD, 0.0

        if confidence < self.min_confidence_to_trade:
            return TradeAction.HOLD, 0.0

        if not risk.approved:
            return TradeAction.HOLD, 0.0

        # Determine direction
        if signal_value > 0:
            # Bullish signal
            if current_position < 0:
                # Close short first
                return TradeAction.CLOSE, abs(current_position)
            elif current_position > 0:
                # Already long - could add but be careful
                if signal_value > 0.6 and confidence > 0.6:
                    return TradeAction.BUY, risk.max_position_size * 0.5
                return TradeAction.HOLD, 0.0
            else:
                # No position - open long
                return TradeAction.BUY, risk.max_position_size

        else:
            # Bearish signal
            if current_position > 0:
                # Close long first
                return TradeAction.CLOSE, current_position
            elif current_position < 0:
                # Already short
                return TradeAction.HOLD, 0.0
            else:
                # No position - could short (if enabled)
                return TradeAction.SELL, risk.max_position_size

    def get_pending_decisions(self) -> Dict[str, TradeDecision]:
        """Get all pending decisions awaiting execution."""
        return self._pending_decisions.copy()

    def clear_decision(self, symbol: str):
        """Clear a pending decision after execution."""
        if symbol in self._pending_decisions:
            del self._pending_decisions[symbol]

    def get_decision_history(self, limit: int = 100) -> List[TradeDecision]:
        """Get recent decision history."""
        return self._decision_history[-limit:]
