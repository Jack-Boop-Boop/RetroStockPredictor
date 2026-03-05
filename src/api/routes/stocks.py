"""Stock search and popular stocks routes."""

import json
from pathlib import Path

from fastapi import APIRouter, Query

from ..schemas.stocks import StockSearchResult, StockSearchResponse

router = APIRouter(prefix="/stocks", tags=["stocks"])

# Load popular stocks from bundled JSON
_POPULAR_STOCKS: list[dict] = []
_data_path = Path(__file__).parent.parent.parent.parent / "data" / "popular_stocks.json"
if _data_path.exists():
    with open(_data_path) as f:
        _POPULAR_STOCKS = json.load(f)


@router.get("/search", response_model=StockSearchResponse)
def search_stocks(
    q: str = Query(..., min_length=1, max_length=20),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Search stocks by symbol or name from the bundled stock list."""
    query = q.upper().strip()
    results = []

    for stock in _POPULAR_STOCKS:
        if query in stock["symbol"].upper() or query.lower() in stock["name"].lower():
            results.append(StockSearchResult(
                symbol=stock["symbol"],
                name=stock["name"],
                sector=stock.get("sector"),
            ))
            if len(results) >= limit:
                break

    # If nothing found in our list, return a bare result for direct symbol lookup
    if not results and len(query) <= 5 and query.isalpha():
        results.append(StockSearchResult(
            symbol=query,
            name=f"{query} (Lookup)",
            sector=None,
        ))

    return StockSearchResponse(results=results, total=len(results))


@router.get("/popular", response_model=StockSearchResponse)
def popular_stocks(
    limit: int = Query(default=50, ge=1, le=100),
    sector: str | None = Query(default=None),
):
    """Get popular/trending stocks, optionally filtered by sector."""
    stocks = _POPULAR_STOCKS

    if sector:
        stocks = [s for s in stocks if s.get("sector", "").lower() == sector.lower()]

    results = [
        StockSearchResult(
            symbol=s["symbol"],
            name=s["name"],
            sector=s.get("sector"),
        )
        for s in stocks[:limit]
    ]

    return StockSearchResponse(results=results, total=len(results))


@router.get("/sectors", response_model=list[str])
def list_sectors():
    """List all available sectors."""
    sectors = sorted(set(s.get("sector", "") for s in _POPULAR_STOCKS if s.get("sector")))
    return sectors
