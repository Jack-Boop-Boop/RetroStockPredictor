"""Pydantic schemas for analysis endpoints."""

from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Z]{1,10}$")
    portfolio_id: str | None = None


class AgentOutputResponse(BaseModel):
    agent_type: str
    signal: str
    confidence: float
    reasoning: dict
    execution_time_ms: int | None

    model_config = {"from_attributes": True}


class AnalysisRunResponse(BaseModel):
    id: str
    symbol: str
    status: str
    final_signal: str | None
    final_confidence: float | None
    final_reasoning: str | None
    agent_outputs: list[AgentOutputResponse]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisStartResponse(BaseModel):
    run_id: str
    status: str
