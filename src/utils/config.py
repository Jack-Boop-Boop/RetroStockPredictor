"""Configuration management for Stock Predictor."""
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class Config:
    """Configuration singleton for the application."""

    _instance = None
    _config: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as f:
                self._config = yaml.safe_load(f)
        else:
            self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def robinhood_username(self) -> str:
        return os.getenv("ROBINHOOD_USERNAME", "")

    @property
    def robinhood_password(self) -> str:
        return os.getenv("ROBINHOOD_PASSWORD", "")

    @property
    def robinhood_totp(self) -> str:
        return os.getenv("ROBINHOOD_TOTP", "")

    @property
    def trading_mode(self) -> str:
        return self.get("trading.mode", "paper")

    @property
    def is_live(self) -> bool:
        return self.trading_mode == "live"

    @property
    def watchlist(self) -> list[str]:
        return self.get("watchlist", [])

    @property
    def database_path(self) -> Path:
        return PROJECT_ROOT / self.get("data.database.path", "data/stocks.db")


config = Config()
