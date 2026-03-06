"""History endpoint for Vercel serverless — returns daily closes."""
import json
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yfinance as yf

# In-memory cache (persists across warm invocations)
_cache = {}
CACHE_TTL = 300  # 5 minutes
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get("symbol", ["AAPL"])[0].upper().strip()
        period = params.get("period", ["3mo"])[0]

        if period not in VALID_PERIODS:
            self._respond(400, {"error": f"Invalid period. Use: {', '.join(sorted(VALID_PERIODS))}"})
            return

        cache_key = f"{symbol}_{period}"
        now = time.time()

        if cache_key in _cache:
            ts, data = _cache[cache_key]
            if now - ts < CACHE_TTL:
                self._respond(200, data)
                return

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                self._respond(404, {"error": f"No history for {symbol}"})
                return

            closes = []
            for idx, row in hist.iterrows():
                ts_ms = int(idx.timestamp() * 1000)
                closes.append([ts_ms, round(row["Close"], 2)])

            data = {"symbol": symbol, "period": period, "closes": closes}
            _cache[cache_key] = (now, data)
            self._respond(200, data)

        except Exception as e:
            self._respond(502, {"error": f"History fetch failed: {str(e)}"})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
