"""Logging configuration for Stock Predictor."""
import sys
from pathlib import Path

from loguru import logger

from .config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Console handler - INFO and above
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# File handler - DEBUG and above
logger.add(
    LOG_DIR / "stock_predictor_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    compression="zip",
)

# Trade log - separate file for all trades
logger.add(
    LOG_DIR / "trades_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
    level="INFO",
    filter=lambda record: "trade" in record["extra"],
    rotation="1 day",
    retention="365 days",
)


def get_logger(name: str):
    """Get a logger with the specified name."""
    return logger.bind(name=name)


def log_trade(message: str):
    """Log a trade message to the dedicated trade log."""
    logger.bind(trade=True).info(message)
