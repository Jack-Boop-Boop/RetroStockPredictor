"""Quote endpoint for Vercel serverless."""
import json
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yfinance as yf

# In-memory cache (persists across warm invocations)
_cache = {}
CACHE_TTL = 60  # seconds


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get("symbol", ["AAPL"])[0].upper().strip()

        now = time.time()

        # Check cache
        if symbol in _cache:
            ts, data = _cache[symbol]
            if now - ts < CACHE_TTL:
                self._respond(200, data)
                return

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
            _cache[symbol] = (now, data)
            self._respond(200, data)

        except Exception as e:
            self._respond(502, {"error": f"Quote fetch failed: {str(e)}"})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
