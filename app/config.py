"""Application configuration management."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "FlyRank Metering & Billing Engine"
    app_env: str = "development"
    debug: bool = True
    workers: int = 4

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Stripe (Test Mode Only)
    stripe_api_key: str
    stripe_webhook_secret: str
    stripe_publishable_key: str = ""

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()