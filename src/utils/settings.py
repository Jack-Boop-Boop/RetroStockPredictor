"""Typed environment configuration using Pydantic Settings.

This module handles all environment variables with validation.
The legacy Config class (config.py) still handles config.yaml for
agent weights and trading parameters. This module handles secrets
and infrastructure config that should never be in YAML.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Database ---
    database_url: str = Field(
        default="sqlite:///data/stocks.db",
        description="PostgreSQL (or SQLite fallback) connection string",
    )

    # --- Auth ---
    jwt_secret: str = Field(
        default="",
        description="JWT signing secret (required in production)",
    )
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=1440)  # 24 hours

    # --- Redis / Caching ---
    redis_url: str = Field(default="", description="Redis URL (Upstash)")
    redis_token: str = Field(default="", description="Redis token (Upstash)")

    # --- Market data providers ---
    alpha_vantage_key: str = Field(default="")
    news_api_key: str = Field(default="")

    # --- Robinhood (live trading) ---
    robinhood_username: str = Field(default="")
    robinhood_password: str = Field(default="")
    robinhood_totp: str = Field(default="")

    # --- App ---
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    cors_origins: str = Field(default="*")

    # --- Sentry (optional) ---
    sentry_dsn: str = Field(default="")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("jwt_secret")
    @classmethod
    def warn_empty_jwt_secret(cls, v: str, info) -> str:
        # We allow empty in development; production checks happen at startup
        return v

    def validate_production(self) -> list[str]:
        """Return a list of configuration errors for production readiness."""
        errors = []
        if not self.jwt_secret:
            errors.append("JWT_SECRET is required")
        if not self.is_postgres:
            errors.append("DATABASE_URL must be a PostgreSQL connection string")
        if len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET should be at least 32 characters")
        return errors


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()


settings = get_settings()
