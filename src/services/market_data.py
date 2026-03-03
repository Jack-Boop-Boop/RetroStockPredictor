"""Market data service: fetch quotes/candles with Redis caching + rate limiting."""

import json
import time
import hashlib
from typing import Optional

import yfinance as yf
import pandas as pd

from ..utils.settings import settings
from ..utils import get_logger

logger = get_logger(__name__)

# Optional Redis — gracefully degrade if not configured
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if settings.redis_url:
        try:
            import redis
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            _redis_client.ping()
            logger.info("Redis connected for market data caching")
            return _redis_client
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            _redis_client = False  # sentinel: don't retry
    return None


def _cache_get(key: str) -> Optional[str]:
    r = _get_redis()
    if r:
        try:
            return r.get(key)
        except Exception:
            return None
    return None


def _cache_set(key: str, value: str, ttl_seconds: int = 60):
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl_seconds, value)
        except Exception:
            pass


def _check_rate_limit(user_key: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
    """Return True if within rate limit, False if exceeded."""
    r = _get_redis()
    if not r:
        return True  # no Redis = no rate limiting
    rk = f"ratelimit:{user_key}"
    try:
        current = r.incr(rk)
        if current == 1:
            r.expire(rk, window_seconds)
        return current <= max_requests
    except Exception:
        return True


def get_quote(symbol: str) -> dict:
    """Get a real-time quote, cached for 30 seconds."""
    cache_key = f"quote:{symbol}"
    cached = _cache_get(cache_key)
    if cached:
        return json.loads(cached)

    ticker = yf.Ticker(symbol)
    info = ticker.info

    result = {
        "symbol": symbol,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "previous_close": info.get("previousClose"),
        "change_pct": info.get("regularMarketChangePercent"),
    }

    _cache_set(cache_key, json.dumps(result), ttl_seconds=30)
    return result


def get_candles(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Get historical OHLCV data, cached for 5 minutes."""
    cache_key = f"candles:{symbol}:{period}:{interval}"
    cached = _cache_get(cache_key)
    if cached:
        return pd.read_json(cached)

    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period, interval=interval)
    if data.empty:
        return data

    # Normalize column names
    data.columns = [c.lower() for c in data.columns]

    _cache_set(cache_key, data.to_json(), ttl_seconds=300)
    return data


def check_rate_limit_or_raise(user_id: str):
    """Raise HTTPException if rate limit exceeded."""
    if not _check_rate_limit(f"user:{user_id}"):
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again in a minute.")
