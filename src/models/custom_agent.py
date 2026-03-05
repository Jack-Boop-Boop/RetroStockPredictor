"""Custom agent model for user-configurable analysis hierarchies."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Float, Text, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow, new_uuid


class CustomAgent(Base):
    __tablename__ = "custom_agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # technical, fundamental, sentiment, ml, quant, risk, ceo, custom
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("custom_agents.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="custom_agents")
    children = relationship("CustomAgent", backref="parent", remote_side="CustomAgent.id", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CustomAgent {self.name} type={self.agent_type}>"
