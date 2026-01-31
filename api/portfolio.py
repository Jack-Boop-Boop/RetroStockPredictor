"""Portfolio endpoint for Vercel serverless."""
from http.server import BaseHTTPRequestHandler
import json

# Simulated paper portfolio (stateless for serverless)
PAPER_PORTFOLIO = {
    "cash": 100000.0,
    "positions_value": 0.0,
    "total_value": 100000.0,
    "initial_value": 100000.0,
    "total_pnl": 0.0,
    "total_pnl_pct": 0.0,
    "positions": [],
    "num_positions": 0
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(PAPER_PORTFOLIO).encode())
