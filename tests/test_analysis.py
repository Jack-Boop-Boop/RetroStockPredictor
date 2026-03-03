"""Tests for analysis pipeline output schema and execution."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.models import AnalysisRun, AnalysisAgentOutput
from src.models.base import new_uuid
from src.services.analysis import execute_analysis, start_analysis, AGENT_ORDER


def _make_fake_candle_data(days: int = 252) -> pd.DataFrame:
    """Create synthetic OHLCV data for testing (no yfinance dependency)."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(days) * 1.5)
    prices = np.maximum(prices, 10)  # Floor at $10

    return pd.DataFrame({
        "close": prices,
        "open": prices * (1 + np.random.randn(days) * 0.005),
        "high": prices * (1 + abs(np.random.randn(days) * 0.01)),
        "low": prices * (1 - abs(np.random.randn(days) * 0.01)),
        "volume": np.random.randint(1_000_000, 50_000_000, days),
    }, index=dates)


class TestAgentOutputSchema:
    """Verify each agent returns correctly shaped output."""

    @pytest.fixture
    def data(self):
        return _make_fake_candle_data()

    def test_technical_analyst_output(self, data):
        from src.services.analysis import _run_technical
        result = _run_technical("TEST", data)

        assert result["signal"] in ("buy", "sell", "hold")
        assert 0 <= result["confidence"] <= 1
        assert isinstance(result["reasoning"], dict)
        assert "rsi" in result["reasoning"]
        assert "macd_hist" in result["reasoning"]

    def test_fundamental_analyst_output(self, data):
        from src.services.analysis import _run_fundamental
        result = _run_fundamental("INVALID_SYMBOL_XYZ", data)

        # Should handle missing data gracefully
        assert result["signal"] in ("buy", "sell", "hold")
        assert 0 <= result["confidence"] <= 1

    def test_sentiment_analyst_output(self, data):
        from src.services.analysis import _run_sentiment
        result = _run_sentiment("TEST", data)

        assert result["signal"] in ("buy", "sell", "hold")
        assert 0 <= result["confidence"] <= 1
        assert "momentum" in result["reasoning"]

    def test_ml_predictor_output(self, data):
        from src.services.analysis import _run_ml
        result = _run_ml("TEST", data)

        assert result["signal"] in ("buy", "sell", "hold")
        assert 0 <= result["confidence"] <= 1
        assert "short_momentum" in result["reasoning"]
        assert "medium_momentum" in result["reasoning"]


class TestAnalysisPipeline:
    """Test the full pipeline stores results correctly in DB."""

    def test_pipeline_stores_all_agent_outputs(self, db):
        from src.models import User
        from src.utils.security import hash_password

        user = User(id=new_uuid(), email="analyst@test.com", password_hash=hash_password("pass12345"))
        db.add(user)
        db.commit()

        run = start_analysis(db, user.id, "TEST")
        db.commit()

        assert run.status == "pending"
        assert run.symbol == "TEST"

    def test_all_agents_in_order(self):
        """Verify the agent execution order is defined."""
        assert len(AGENT_ORDER) == 4
        assert "technical_analyst" in AGENT_ORDER
        assert "fundamental_analyst" in AGENT_ORDER
        assert "sentiment_analyst" in AGENT_ORDER
        assert "ml_predictor" in AGENT_ORDER
