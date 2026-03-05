"""Analysis pipeline service: run agent hierarchy and store results."""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import AnalysisRun, AnalysisAgentOutput, CustomAgent
from ..models.base import new_uuid
from ..utils import get_logger
from . import market_data

logger = get_logger(__name__)

# Map agent_type to runner function name
AGENT_TYPE_TO_RUNNER = {
    "technical": "technical_analyst",
    "fundamental": "fundamental_analyst",
    "sentiment": "sentiment_analyst",
    "ml": "ml_predictor",
}

# Default agent order (fallback if no custom agents)
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
    "technical": _run_technical,
    "fundamental_analyst": _run_fundamental,
    "fundamental": _run_fundamental,
    "sentiment_analyst": _run_sentiment,
    "sentiment": _run_sentiment,
    "ml_predictor": _run_ml,
    "ml": _run_ml,
}


def _get_leaf_agents(db: Session, user_id: str) -> list[dict]:
    """Get the user's custom leaf agents (those that actually run analysis).

    Returns a list of dicts with keys: agent_type, weight, name, prompt.
    Falls back to default agents if no custom agents exist.
    """
    custom_agents = (
        db.query(CustomAgent)
        .filter_by(user_id=user_id, enabled=True)
        .all()
    )

    if not custom_agents:
        # Fallback: default 4 agents with equal weight
        return [
            {"agent_type": "technical_analyst", "weight": 1.0, "name": "Technical Analyst", "prompt": None},
            {"agent_type": "fundamental_analyst", "weight": 1.0, "name": "Fundamental Analyst", "prompt": None},
            {"agent_type": "sentiment_analyst", "weight": 1.0, "name": "Sentiment Analyst", "prompt": None},
            {"agent_type": "ml_predictor", "weight": 1.0, "name": "ML Predictor", "prompt": None},
        ]

    # Find leaf agents (those with a runner function)
    leaf_types = {"technical", "fundamental", "sentiment", "ml"}
    leaves = []
    for agent in custom_agents:
        if agent.agent_type in leaf_types:
            leaves.append({
                "agent_type": agent.agent_type,
                "weight": agent.weight,
                "name": agent.name,
                "prompt": agent.prompt,
            })

    # If no leaf agents found in custom hierarchy, fallback
    if not leaves:
        return [
            {"agent_type": "technical_analyst", "weight": 1.0, "name": "Technical Analyst", "prompt": None},
            {"agent_type": "fundamental_analyst", "weight": 1.0, "name": "Fundamental Analyst", "prompt": None},
            {"agent_type": "sentiment_analyst", "weight": 1.0, "name": "Sentiment Analyst", "prompt": None},
            {"agent_type": "ml_predictor", "weight": 1.0, "name": "ML Predictor", "prompt": None},
        ]

    return leaves


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

    Uses the user's custom agent hierarchy with weights.
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

        # Get user's configured agents
        agents = _get_leaf_agents(db, run.user_id)

        signal_values = []
        weight_total = 0

        for agent_info in agents:
            agent_type = agent_info["agent_type"]
            weight = agent_info["weight"]

            runner = AGENT_RUNNERS.get(agent_type)
            if not runner:
                continue

            t0 = time.time()
            try:
                result = runner(run.symbol, data)
            except Exception as e:
                result = {"signal": "hold", "confidence": 0.0, "reasoning": {"error": str(e)}}
            elapsed_ms = int((time.time() - t0) * 1000)

            # Store agent name for display (use custom name if available)
            display_type = AGENT_TYPE_TO_RUNNER.get(agent_type, agent_type)

            output = AnalysisAgentOutput(
                id=new_uuid(),
                run_id=run.id,
                agent_type=display_type,
                signal=result["signal"],
                confidence=result["confidence"],
                reasoning=result.get("reasoning", {}),
                execution_time_ms=elapsed_ms,
            )
            db.add(output)

            # Map signal to numeric for weighted aggregation
            sig_map = {"buy": 1, "hold": 0, "sell": -1}
            signal_values.append(sig_map.get(result["signal"], 0) * result["confidence"] * weight)
            weight_total += weight

        # Aggregate: weighted average of agent signals
        if signal_values and weight_total > 0:
            avg_signal = sum(signal_values) / weight_total
        else:
            avg_signal = 0

        if avg_signal > 0.15:
            run.final_signal = "buy"
        elif avg_signal < -0.15:
            run.final_signal = "sell"
        else:
            run.final_signal = "hold"

        run.final_confidence = round(min(0.95, abs(avg_signal) + 0.3), 4)
        run.final_reasoning = f"Aggregate signal: {avg_signal:.4f} from {len(agents)} agents"
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Analysis failed for {run.symbol}: {e}")
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = datetime.now(timezone.utc)

    db.flush()
    return run
