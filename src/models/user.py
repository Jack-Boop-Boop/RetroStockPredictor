"""User model for authentication."""

from datetime import datetime

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, utcnow, new_uuid


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="user", lazy="selectin")
    watchlists = relationship("Watchlist", back_populates="user", lazy="selectin")
    analysis_runs = relationship("AnalysisRun", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
