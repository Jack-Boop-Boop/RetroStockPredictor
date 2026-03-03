"""Analysis run and agent output models."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, ForeignKey, Numeric, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow, new_uuid


class AnalysisRun(Base):
    """A single analysis run for a symbol, containing outputs from all agents."""
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    portfolio_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="SET NULL"), index=True,
    )
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )  # pending, running, completed, failed
    final_signal: Mapped[Optional[str]] = mapped_column(String(10))  # buy, sell, hold
    final_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    final_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column()
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="analysis_runs")
    agent_outputs = relationship("AnalysisAgentOutput", back_populates="run", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AnalysisRun {self.symbol} status={self.status} signal={self.final_signal}>"


class AnalysisAgentOutput(Base):
    """Output from a single agent within an analysis run."""
    __tablename__ = "analysis_agent_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )  # technical, fundamental, sentiment, ml, quant, risk, ceo
    signal: Mapped[str] = mapped_column(String(10), nullable=False)  # buy, sell, hold
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    reasoning: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

    # Relationships
    run = relationship("AnalysisRun", back_populates="agent_outputs")

    def __repr__(self) -> str:
        return f"<AgentOutput {self.agent_type} signal={self.signal} conf={self.confidence}>"
