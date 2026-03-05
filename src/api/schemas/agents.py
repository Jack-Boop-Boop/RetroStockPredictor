"""Pydantic schemas for custom agent CRUD endpoints."""

from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    agent_type: str = Field(..., pattern=r"^(technical|fundamental|sentiment|ml|quant|risk|ceo|custom)$")
    parent_id: str | None = None
    prompt: str | None = None
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
    enabled: bool = True
    sort_order: int = 0
    config: dict | None = None


class AgentUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    prompt: str | None = None
    weight: float | None = Field(None, ge=0.0, le=5.0)
    enabled: bool | None = None
    parent_id: str | None = None
    sort_order: int | None = None
    config: dict | None = None


class AgentResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    parent_id: str | None
    prompt: str | None
    weight: float
    enabled: bool
    sort_order: int
    config: dict | None

    model_config = {"from_attributes": True}


class AgentTreeResponse(BaseModel):
    agents: list[AgentResponse]
