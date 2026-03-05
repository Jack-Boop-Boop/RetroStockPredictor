"""Pydantic schemas for stock search and portfolio import."""

from decimal import Decimal
from pydantic import BaseModel, Field


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    market_cap: str | None = None  # "large", "mid", "small"


class StockSearchResponse(BaseModel):
    results: list[StockSearchResult]
    total: int


class ImportPositionItem(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10, pattern=r"^[A-Z]{1,10}$")
    shares: Decimal = Field(..., gt=0)
    avg_cost: Decimal = Field(..., gt=0)


class PortfolioImportRequest(BaseModel):
    positions: list[ImportPositionItem] = Field(..., min_length=1, max_length=100)


class PortfolioImportResponse(BaseModel):
    imported: int
    skipped: int
    message: str
