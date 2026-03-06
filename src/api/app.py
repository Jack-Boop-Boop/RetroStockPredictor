"""FastAPI application — slim MVP with 2 market-data endpoints.

Run locally:  uvicorn src.api.app:app --reload --port 5000
"""

import time
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

import yfinance as yf

PROJECT_ROOT = Path(__file__).parent.parent.parent

app = FastAPI(title="Stock Predictor API", version="1.0.0", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------- In-memory cache ---------------
_quote_cache: dict[str, tuple[float, dict]] = {}
_history_cache: dict[str, tuple[float, dict]] = {}

QUOTE_TTL = 60        # seconds
HISTORY_TTL = 300     # seconds
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y"}


# --------------- Endpoints ---------------

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/quote")
def quote(symbol: str = Query(..., min_length=1, max_length=10)):
    symbol = symbol.upper().strip()
    now = time.time()

    # Check cache
    if symbol in _quote_cache:
        ts, data = _quote_cache[symbol]
        if now - ts < QUOTE_TTL:
            return data

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose")
        change = round(price - prev, 2) if price and prev else None
        change_pct = round((change / prev) * 100, 2) if change and prev else None

        data = {
            "symbol": symbol,
            "price": price,
            "previous_close": prev,
            "change": change,
            "change_pct": change_pct,
        }
        _quote_cache[symbol] = (now, data)
        return data

    except Exception as e:
        return JSONResponse(status_code=502, content={"error": f"Quote fetch failed: {str(e)}"})


@app.get("/api/history")
def history(
    symbol: str = Query(..., min_length=1, max_length=10),
    period: str = Query("3mo"),
):
    symbol = symbol.upper().strip()
    if period not in VALID_PERIODS:
        return JSONResponse(status_code=400, content={"error": f"Invalid period. Use: {', '.join(sorted(VALID_PERIODS))}"})

    cache_key = f"{symbol}_{period}"
    now = time.time()

    if cache_key in _history_cache:
        ts, data = _history_cache[cache_key]
        if now - ts < HISTORY_TTL:
            return data

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            return JSONResponse(status_code=404, content={"error": f"No history for {symbol}"})

        closes = []
        for idx, row in hist.iterrows():
            ts_ms = int(idx.timestamp() * 1000)
            closes.append([ts_ms, round(row["Close"], 2)])

        data = {"symbol": symbol, "period": period, "closes": closes}
        _history_cache[cache_key] = (now, data)
        return data

    except Exception as e:
        return JSONResponse(status_code=502, content={"error": f"History fetch failed: {str(e)}"})


# --------------- Static files ---------------
static_dir = PROJECT_ROOT / "public" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    return FileResponse(str(PROJECT_ROOT / "public" / "index.html"))
