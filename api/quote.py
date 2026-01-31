"""Quote endpoint for Vercel serverless."""
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs
import yfinance as yf


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get('symbol', ['AAPL'])[0].upper()

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            result = {
                "symbol": symbol,
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "previous_close": info.get("previousClose"),
                "change_pct": info.get("regularMarketChangePercent"),
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
