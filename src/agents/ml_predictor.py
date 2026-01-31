"""Machine Learning Prediction Agent."""
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple
import pickle

from .base_agent import BaseAgent, AgentSignal
from ..utils import config, get_logger

logger = get_logger(__name__)

# Check if PyTorch is available
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available - ML predictions will use fallback")


if TORCH_AVAILABLE:
    class LSTMModel(nn.Module):
        """LSTM model for price prediction."""

        def __init__(self, input_size: int = 5, hidden_size: int = 64,
                     num_layers: int = 2, output_size: int = 1):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.2,
            )

            self.fc = nn.Sequential(
                nn.Linear(hidden_size, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, output_size),
            )

        def forward(self, x):
            # x shape: (batch, seq_len, features)
            lstm_out, _ = self.lstm(x)
            # Take output from last time step
            last_out = lstm_out[:, -1, :]
            return self.fc(last_out)


class MLPredictor(BaseAgent):
    """
    Machine Learning prediction agent.

    Uses LSTM neural network to predict price direction.
    Falls back to simple statistical prediction if PyTorch unavailable.
    """

    def __init__(self, weight: float = None, lookback_days: int = None):
        weight = weight or config.get("agents.ml.weight", 0.25)
        super().__init__("ml_predictor", weight)

        self.lookback = lookback_days or config.get("agents.ml.lookback_days", 60)
        self.model = None
        self.scaler_params = {}
        self.model_path = Path("models/lstm_model.pt")

        if TORCH_AVAILABLE:
            self._initialize_model()

    def _initialize_model(self):
        """Initialize or load the LSTM model."""
        self.model = LSTMModel(input_size=5, hidden_size=64, num_layers=2)

        if self.model_path.exists():
            try:
                self.model.load_state_dict(torch.load(self.model_path))
                self.logger.info("Loaded pre-trained model")
            except Exception as e:
                self.logger.warning(f"Could not load model: {e}")

        self.model.eval()

    def analyze(self, symbol: str, data: pd.DataFrame) -> AgentSignal:
        """Generate prediction signal."""
        if len(data) < self.lookback:
            return AgentSignal.from_value(
                symbol=symbol, value=0.0, confidence=0.1,
                agent_name=self.name,
                reasoning={"error": f"Need at least {self.lookback} days of data"}
            )

        if TORCH_AVAILABLE and self.model is not None:
            signal_value, confidence, reasoning = self._predict_with_lstm(data)
        else:
            signal_value, confidence, reasoning = self._predict_statistical(data)

        signal = AgentSignal.from_value(
            symbol=symbol,
            value=signal_value,
            confidence=confidence,
            agent_name=self.name,
            reasoning=reasoning,
        )

        self.save_signal(signal)
        self.logger.info(f"{symbol}: signal={signal_value:.2f}, confidence={confidence:.2f}")

        return signal

    def _prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """Prepare feature matrix from OHLCV data."""
        df = data.copy()

        # Basic features
        df["returns"] = df["close"].pct_change()
        df["volatility"] = df["returns"].rolling(10).std()
        df["volume_change"] = df["volume"].pct_change() if "volume" in df else 0

        # Normalize price to returns
        df["price_norm"] = df["close"].pct_change()
        df["high_low_range"] = (df["high"] - df["low"]) / df["close"]

        # Fill NaN
        df = df.fillna(0)

        # Select features
        features = df[["price_norm", "returns", "volatility", "volume_change", "high_low_range"]]

        return features.values

    def _predict_with_lstm(self, data: pd.DataFrame) -> Tuple[float, float, dict]:
        """Make prediction using LSTM model."""
        features = self._prepare_features(data)

        # Use last lookback days
        seq = features[-self.lookback:]

        # Normalize
        mean = seq.mean(axis=0)
        std = seq.std(axis=0) + 1e-8
        seq_norm = (seq - mean) / std

        # Convert to tensor
        x = torch.FloatTensor(seq_norm).unsqueeze(0)  # Add batch dimension

        with torch.no_grad():
            prediction = self.model(x).item()

        # Convert prediction to signal (-1 to 1)
        # Model predicts next day return, scale to signal
        signal_value = np.tanh(prediction * 10)  # Scale and bound

        # Confidence based on recent model performance (placeholder)
        confidence = 0.5  # Base confidence for untrained model

        reasoning = {
            "method": "LSTM",
            "raw_prediction": f"{prediction:.4f}",
            "lookback_days": self.lookback,
            "note": "Model requires training on historical data for better accuracy",
        }

        return signal_value, confidence, reasoning

    def _predict_statistical(self, data: pd.DataFrame) -> Tuple[float, float, dict]:
        """Fallback statistical prediction without ML."""
        closes = data["close"]

        # Simple momentum prediction
        short_momentum = (closes.iloc[-1] - closes.iloc[-5]) / closes.iloc[-5]
        med_momentum = (closes.iloc[-1] - closes.iloc[-20]) / closes.iloc[-20]

        # Mean reversion factor
        sma_20 = closes.rolling(20).mean().iloc[-1]
        deviation = (closes.iloc[-1] - sma_20) / sma_20

        # Trend following + mean reversion blend
        trend_signal = (short_momentum + med_momentum) / 2
        reversion_signal = -deviation * 0.5

        # Combine (60% trend, 40% reversion)
        signal_value = (trend_signal * 0.6) + (reversion_signal * 0.4)
        signal_value = max(-1.0, min(1.0, signal_value * 5))  # Scale up

        # Confidence based on trend clarity
        confidence = min(0.6, abs(short_momentum) * 5 + 0.3)

        reasoning = {
            "method": "statistical",
            "short_momentum": f"{short_momentum:.4f}",
            "med_momentum": f"{med_momentum:.4f}",
            "mean_reversion": f"{reversion_signal:.4f}",
            "note": "Using statistical fallback (PyTorch not available)",
        }

        return signal_value, confidence, reasoning

    def train(self, data: pd.DataFrame, epochs: int = 100, lr: float = 0.001):
        """
        Train the LSTM model on historical data.

        Args:
            data: Historical OHLCV data
            epochs: Number of training epochs
            lr: Learning rate
        """
        if not TORCH_AVAILABLE:
            self.logger.error("PyTorch required for training")
            return

        self.logger.info(f"Training model with {len(data)} samples")

        features = self._prepare_features(data)

        # Create sequences and targets
        X, y = [], []
        for i in range(len(features) - self.lookback - 1):
            X.append(features[i:i + self.lookback])
            # Target: next day return
            y.append(features[i + self.lookback, 0])  # price_norm is at index 0

        X = np.array(X)
        y = np.array(y)

        # Normalize
        mean = X.mean(axis=(0, 1))
        std = X.std(axis=(0, 1)) + 1e-8
        X = (X - mean) / std

        # Convert to tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y).unsqueeze(1)

        # Training
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = self.model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()

            if (epoch + 1) % 20 == 0:
                self.logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {loss.item():.6f}")

        self.model.eval()

        # Save model
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        self.logger.info(f"Model saved to {self.model_path}")

        # Save scaler params
        self.scaler_params = {"mean": mean.tolist(), "std": std.tolist()}
