"""Base agent class for the trading system."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any

import pandas as pd

from ..utils import get_logger, config
from ..data import Database


class SignalType(Enum):
    """Type of trading signal."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class AgentSignal:
    """
    Trading signal produced by an agent.

    Attributes:
        symbol: Stock ticker
        value: Signal strength from -1.0 (strong sell) to 1.0 (strong buy)
        confidence: How confident the agent is (0.0 to 1.0)
        signal_type: Categorical signal type
        agent_name: Name of the agent that produced the signal
        timestamp: When the signal was generated
        reasoning: Detailed breakdown of why this signal was generated
        metadata: Additional data specific to the agent type
    """
    symbol: str
    value: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    signal_type: SignalType
    agent_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reasoning: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # Clamp values to valid ranges
        self.value = max(-1.0, min(1.0, self.value))
        self.confidence = max(0.0, min(1.0, self.confidence))

    @classmethod
    def from_value(cls, symbol: str, value: float, confidence: float,
                   agent_name: str, reasoning: dict = None) -> "AgentSignal":
        """Create a signal from a numeric value."""
        if value >= 0.6:
            signal_type = SignalType.STRONG_BUY
        elif value >= 0.2:
            signal_type = SignalType.BUY
        elif value <= -0.6:
            signal_type = SignalType.STRONG_SELL
        elif value <= -0.2:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.HOLD

        return cls(
            symbol=symbol,
            value=value,
            confidence=confidence,
            signal_type=signal_type,
            agent_name=agent_name,
            reasoning=reasoning or {},
        )

    @property
    def weighted_value(self) -> float:
        """Signal value weighted by confidence."""
        return self.value * self.confidence

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "value": self.value,
            "confidence": self.confidence,
            "signal_type": self.signal_type.value,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp.isoformat(),
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all trading agents.

    Agents analyze data and produce trading signals. They can be:
    - Analyst agents (technical, fundamental, sentiment, ML)
    - Decision agents (risk manager, quant strategist, portfolio CEO)
    """

    def __init__(self, name: str, weight: float = 1.0):
        """
        Initialize the agent.

        Args:
            name: Unique name for this agent
            weight: Weight of this agent's signals (0.0 to 1.0)
        """
        self.name = name
        self.weight = weight
        self.logger = get_logger(f"agent.{name}")
        self.db = Database()
        self._last_signals: dict[str, AgentSignal] = {}

    @abstractmethod
    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """
        Analyze data and produce a trading signal.

        Args:
            symbol: Stock ticker symbol
            data: Historical price data (OHLCV)

        Returns:
            AgentSignal with the analysis result
        """
        pass

    def analyze_multiple(self, symbols: list[str],
                         data: dict[str, pd.DataFrame]) -> dict[str, AgentSignal]:
        """Analyze multiple symbols."""
        signals = {}
        for symbol in symbols:
            if symbol in data and not data[symbol].empty:
                try:
                    signals[symbol] = self.analyze(symbol, data[symbol])
                except Exception as e:
                    self.logger.error(f"Error analyzing {symbol}: {e}")
        return signals

    def save_signal(self, signal: AgentSignal):
        """Save a signal to the database."""
        self.db.save_signal(
            symbol=signal.symbol,
            agent_type=self.name,
            signal_value=signal.value,
            confidence=signal.confidence,
            reasoning=signal.reasoning,
        )
        self._last_signals[signal.symbol] = signal

    def get_last_signal(self, symbol: str) -> Optional[AgentSignal]:
        """Get the last signal for a symbol."""
        return self._last_signals.get(symbol)


class DecisionAgent(BaseAgent):
    """
    Base class for decision-making agents.

    Decision agents take signals from analyst agents and make
    higher-level decisions about trading.
    """

    def __init__(self, name: str, subordinate_agents: list[BaseAgent] = None):
        super().__init__(name)
        self.subordinates = subordinate_agents or []

    @abstractmethod
    def decide(self, symbol: str, signals: list[AgentSignal]) -> AgentSignal:
        """
        Make a decision based on subordinate agent signals.

        Args:
            symbol: Stock ticker
            signals: List of signals from subordinate agents

        Returns:
            Final decision signal
        """
        pass

    def collect_signals(self, symbol: str, data: pd.DataFrame) -> list[AgentSignal]:
        """Collect signals from all subordinate agents."""
        signals = []
        for agent in self.subordinates:
            try:
                signal = agent.analyze(symbol, data)
                signals.append(signal)
            except Exception as e:
                self.logger.error(f"Error getting signal from {agent.name}: {e}")
        return signals

    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """Collect subordinate signals and make a decision."""
        signals = self.collect_signals(symbol, data)
        return self.decide(symbol, signals)
