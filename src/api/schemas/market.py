"""Pydantic schemas for market data endpoints."""

from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    symbol: str
    price: float | None
    previous_close: float | None
    change_pct: float | None


class WatchlistResponse(BaseModel):
    id: str
    name: str
    symbols: list[str]

    model_config = {"from_attributes": True}


class WatchlistUpdateRequest(BaseModel):
    symbols: list[str] = Field(..., max_length=50)
