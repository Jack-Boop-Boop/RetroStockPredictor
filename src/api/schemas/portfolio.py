"""Pydantic schemas for portfolio and trading endpoints."""

from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Z]{1,10}$")
    side: str = Field(..., pattern=r"^(buy|sell)$")
    quantity: Decimal = Field(..., gt=0, le=1_000_000)
    order_type: str = Field(default="market", pattern=r"^(market|limit)$")
    limit_price: Decimal | None = Field(None, gt=0)


class OrderResponse(BaseModel):
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal
    limit_price: Decimal | None
    status: str
    filled_quantity: Decimal
    filled_avg_price: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FillResponse(BaseModel):
    id: str
    quantity: Decimal
    price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionResponse(BaseModel):
    id: str
    symbol: str
    quantity: Decimal
    avg_cost: Decimal
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None

    model_config = {"from_attributes": True}


class PortfolioResponse(BaseModel):
    id: str
    name: str
    cash: Decimal
    initial_cash: Decimal
    positions: list[PositionResponse]
    positions_value: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
