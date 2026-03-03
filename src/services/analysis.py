"""Analysis pipeline service: run agent hierarchy and store results."""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import AnalysisRun, AnalysisAgentOutput, Portfolio
from ..models.base import new_uuid
from ..utils import get_logger
from . import market_data

logger = get_logger(__name__)

# Agent names in execution order
AGENT_ORDER = [
    "technical_analyst",
    "fundamental_analyst",
    "sentiment_analyst",
    "ml_predictor",
]


def _run_technical(symbol: str, data) -> dict:
    """Technical analysis: RSI, MACD, momentum."""
    import numpy as np

    close = data["close"]

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    if rsi < 30:
        rsi_signal = 0.6
    elif rsi > 70:
        rsi_signal = -0.6
    else:
        rsi_signal = (50 - rsi) / 100

    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    hist = (exp1 - exp2 - (exp1 - exp2).ewm(span=9, adjust=False).mean()).iloc[-1]
    macd_signal = float(min(0.6, max(-0.6, hist * 10)))

    # Momentum
    short_mom = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5])
    mom_signal = float(min(0.6, max(-0.6, short_mom * 5)))

    value = rsi_signal * 0.4 + macd_signal * 0.4 + mom_signal * 0.2
    signal = "buy" if value > 0.1 else "sell" if value < -0.1 else "hold"
    confidence = min(0.9, abs(value) + 0.3)

    return {
        "signal": signal,
        "confidence": round(float(confidence), 4),
        "reasoning": {"rsi": round(float(rsi), 2), "macd_hist": round(float(hist), 4), "momentum": round(short_mom, 4), "value": round(float(value), 4)},
    }


def _run_fundamental(symbol: str, data) -> dict:
    """Fundamental analysis stub: P/E ratio comparison."""
    import yfinance as yf

    try:
        info = yf.Ticker(symbol).info
        pe = info.get("trailingPE")
        if pe and pe > 0:
            value = float(min(0.6, max(-0.6, (20 - pe) / 40)))
        else:
            value = 0.0
    except Exception:
        value = 0.0

    signal = "buy" if value > 0.1 else "sell" if value < -0.1 else "hold"
    return {
        "signal": signal,
        "confidence": round(min(0.7, abs(value) + 0.3), 4),
        "reasoning": {"pe_ratio": pe if 'pe' in dir() else None, "value": round(value, 4)},
    }


def _run_sentiment(symbol: str, data) -> dict:
    """Sentiment stub: price-action-based."""
    close = data["close"]
    momentum = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5])
    value = momentum * 0.8
    signal = "buy" if value > 0.05 else "sell" if value < -0.05 else "hold"
    return {
        "signal": signal,
        "confidence": round(min(0.6, abs(value) + 0.2), 4),
        "reasoning": {"momentum": round(momentum, 4), "value": round(value, 4)},
    }


def _run_ml(symbol: str, data) -> dict:
    """ML stub: simple momentum average."""
    close = data["close"]
    short = float((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5])
    medium = float((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20])
    value = (short + medium) / 2
    signal = "buy" if value > 0.02 else "sell" if value < -0.02 else "hold"
    return {
        "signal": signal,
        "confidence": round(min(0.6, abs(value) + 0.2), 4),
        "reasoning": {"short_momentum": round(short, 4), "medium_momentum": round(medium, 4), "value": round(value, 4)},
    }


AGENT_RUNNERS = {
    "technical_analyst": _run_technical,
    "fundamental_analyst": _run_fundamental,
    "sentiment_analyst": _run_sentiment,
    "ml_predictor": _run_ml,
}


def start_analysis(db: Session, user_id: str, symbol: str, portfolio_id: str | None = None) -> AnalysisRun:
    """Create a pending analysis run."""
    run = AnalysisRun(
        id=new_uuid(),
        user_id=user_id,
        portfolio_id=portfolio_id,
        symbol=symbol,
        status="pending",
    )
    db.add(run)
    db.flush()
    return run


def execute_analysis(db: Session, run: AnalysisRun) -> AnalysisRun:
    """Execute all agents for an analysis run (synchronous).

    In production, call this from a background task/worker.
    """
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    db.flush()

    try:
        data = market_data.get_candles(run.symbol, period="1y")
        if data.empty:
            run.status = "failed"
            run.error_message = f"No market data for {run.symbol}"
            db.flush()
            return run

        signal_values = []

        for agent_type in AGENT_ORDER:
            runner = AGENT_RUNNERS[agent_type]
            t0 = time.time()
            try:
                result = runner(run.symbol, data)
            except Exception as e:
                result = {"signal": "hold", "confidence": 0.0, "reasoning": {"error": str(e)}}
            elapsed_ms = int((time.time() - t0) * 1000)

            output = AnalysisAgentOutput(
                id=new_uuid(),
                run_id=run.id,
                agent_type=agent_type,
                signal=result["signal"],
                confidence=result["confidence"],
                reasoning=result.get("reasoning", {}),
                execution_time_ms=elapsed_ms,
            )
            db.add(output)

            # Map signal to numeric for aggregation
            sig_map = {"buy": 1, "hold": 0, "sell": -1}
            signal_values.append(sig_map.get(result["signal"], 0) * result["confidence"])

        # Aggregate: weighted average of agent signals
        if signal_values:
            avg_signal = sum(signal_values) / len(signal_values)
        else:
            avg_signal = 0

        if avg_signal > 0.15:
            run.final_signal = "buy"
        elif avg_signal < -0.15:
            run.final_signal = "sell"
        else:
            run.final_signal = "hold"

        run.final_confidence = round(min(0.95, abs(avg_signal) + 0.3), 4)
        run.final_reasoning = f"Aggregate signal: {avg_signal:.4f} from {len(AGENT_ORDER)} agents"
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Analysis failed for {run.symbol}: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)

    db.flush()
    return run
