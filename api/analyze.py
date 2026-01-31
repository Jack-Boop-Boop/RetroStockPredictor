"""Analyze stock endpoint for Vercel serverless."""
from http.server import BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf
import pandas as pd
import numpy as np


def calculate_rsi(prices, period=14):
    """Calculate RSI."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices):
    """Calculate MACD."""
    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1], (macd - signal).iloc[-1]


def analyze_stock(symbol):
    """Run simplified analysis on a stock."""
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1y")

    if data.empty:
        return None

    close = data["close"]
    current_price = close.iloc[-1]

    # Technical signals
    rsi = calculate_rsi(close).iloc[-1]
    macd, signal, hist = calculate_macd(close)

    # RSI signal
    if rsi < 30:
        rsi_signal = 0.6
    elif rsi > 70:
        rsi_signal = -0.6
    else:
        rsi_signal = (50 - rsi) / 100

    # MACD signal
    macd_signal = min(0.6, max(-0.6, hist * 10))

    # Momentum
    short_momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]
    momentum_signal = min(0.6, max(-0.6, short_momentum * 5))

    # Aggregate
    tech_signal = (rsi_signal * 0.4 + macd_signal * 0.4 + momentum_signal * 0.2)
    sentiment_signal = momentum_signal * 0.8
    ml_signal = (short_momentum + (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) / 2

    # Final decision
    final_signal = (tech_signal + sentiment_signal + ml_signal) / 3
    confidence = min(0.8, abs(final_signal) + 0.3)

    if final_signal > 0.3:
        action = "buy"
    elif final_signal < -0.3:
        action = "sell"
    else:
        action = "hold"

    return {
        "symbol": symbol,
        "price": float(current_price),
        "signal": float(final_signal),
        "confidence": float(confidence),
        "action": action,
        "approved": abs(final_signal) > 0.2,
        "signals": {
            "technical_analyst": float(tech_signal),
            "sentiment_analyst": float(sentiment_signal),
            "ml_predictor": float(ml_signal),
        },
        "stop_loss": float(current_price * 0.95) if action == "buy" else None,
        "take_profit": float(current_price * 1.15) if action == "buy" else None,
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Extract symbol from path: /api/analyze?symbol=AAPL
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get('symbol', ['AAPL'])[0].upper()

        try:
            result = analyze_stock(symbol)

            if result is None:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"No data for {symbol}"}).encode())
                return

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
