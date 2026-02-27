"""
Stock Predictor Web Application
Retro 80s Macintosh UI
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

from src.utils import config, get_logger
from src.data import Database, YahooFetcher
from src.agents import (
    TechnicalAnalyst, FundamentalAnalyst, SentimentAnalyst, MLPredictor,
    QuantStrategist, RiskManager, PortfolioCEO
)
from src.execution import PaperTrader

logger = get_logger("web")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stock-predictor-secret'
socketio = SocketIO(app)

# Initialize components
db = Database()
fetcher = YahooFetcher()
paper_trader = PaperTrader()

# Initialize agent hierarchy
technical = TechnicalAnalyst()
fundamental = FundamentalAnalyst()
sentiment = SentimentAnalyst()
ml = MLPredictor()
quant = QuantStrategist([technical, fundamental, sentiment, ml])
risk = RiskManager()
ceo = PortfolioCEO(quant, risk)


@app.route('/')
def index():
    """Serve the main UI."""
    return render_template('index.html')


@app.route('/api/portfolio')
def get_portfolio():
    """Get paper portfolio status."""
    summary = paper_trader.get_portfolio_summary()
    return jsonify(summary)


@app.route('/api/quote')
def get_quote():
    """Get current quote for a symbol."""
    symbol = request.args.get('symbol', '').upper()
    if not symbol:
        return jsonify({'error': 'Missing symbol parameter'}), 400
    try:
        data = fetcher.get_realtime_price(symbol)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/analyze')
def analyze_symbol():
    """Run full agent analysis on a symbol."""
    symbol = request.args.get('symbol', '').upper()
    if not symbol:
        return jsonify({'error': 'Missing symbol parameter'}), 400
    logger.info(f"Web: Analyzing {symbol}")

    try:
        # Fetch data
        data = fetcher.get_stock_data(symbol, period="1y")
        if data.empty:
            return jsonify({'error': f'No data for {symbol}'}), 400

        current_price = data["close"].iloc[-1]

        # Get analyst signals
        signals = []

        tech_signal = technical.analyze(symbol, data)
        signals.append(tech_signal)

        fund_signal = fundamental.analyze(symbol, data)
        signals.append(fund_signal)

        sent_signal = sentiment.analyze(symbol, data)
        signals.append(sent_signal)

        ml_signal = ml.analyze(symbol, data)
        signals.append(ml_signal)

        # Get CEO decision
        decision = ceo.make_trade_decision(symbol, signals, current_price)

        result = {
            'symbol': symbol,
            'price': float(current_price),
            'signal': float(decision.signal_value),
            'confidence': float(decision.confidence),
            'action': decision.action.value,
            'approved': decision.approved,
            'signals': {
                'technical_analyst': float(tech_signal.value),
                'fundamental_analyst': float(fund_signal.value),
                'sentiment_analyst': float(sent_signal.value),
                'ml_predictor': float(ml_signal.value),
            },
            'stop_loss': decision.stop_loss,
            'take_profit': decision.take_profit,
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trade/<symbol>/<action>')
def execute_trade(symbol, action):
    """Execute a paper trade."""
    symbol = symbol.upper()
    action = action.lower()

    try:
        # Get current price
        quote = fetcher.get_realtime_price(symbol)
        price = quote.get('price')

        if not price:
            return jsonify({'error': 'Could not get price'}), 400

        # Default quantity (simplified)
        quantity = 10

        if action == 'buy':
            success = paper_trader.buy(symbol, quantity, price)
        elif action == 'sell':
            success = paper_trader.sell(symbol, quantity, price)
        else:
            return jsonify({'error': 'Invalid action'}), 400

        if success:
            return jsonify({
                'success': True,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'price': price,
            })
        else:
            return jsonify({'error': 'Trade failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history')
def get_history():
    """Get trade history."""
    history = paper_trader.get_trade_history(50)
    return jsonify(history)


@app.route('/api/watchlist')
def get_watchlist():
    """Get watchlist with current signals."""
    symbols = config.watchlist[:5]  # Limit to 5
    results = []

    for symbol in symbols:
        try:
            quote = fetcher.get_realtime_price(symbol)
            results.append({
                'symbol': symbol,
                'price': quote.get('price'),
            })
        except Exception:
            results.append({
                'symbol': symbol,
                'price': None,
            })

    return jsonify(results)


def main():
    """Run the web application."""
    print("=" * 50)
    print("  Stock Predictor - Retro Mac UI")
    print("  http://localhost:5000")
    print("=" * 50)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    main()
