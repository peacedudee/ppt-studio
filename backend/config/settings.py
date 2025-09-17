"""Central application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


class Settings:
    """Container for environment-driven configuration."""

    def __init__(self) -> None:
        raw_env = (os.getenv("APP_ENV") or "development").strip().lower()
        self.app_env = raw_env or "development"

        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.celery_broker_url = os.getenv("CELERY_BROKER_URL", self.redis_url)
        self._celery_result_backend_url = os.getenv("CELERY_RESULT_BACKEND_URL")

        self.enable_result_backend = _env_bool(
            "CELERY_ENABLE_RESULT_BACKEND", self.app_env == "development"
        )

        default_expiry = 3600 if self.is_development else 300
        self.celery_result_expires = int(
            os.getenv("CELERY_RESULT_EXPIRES", str(default_expiry))
        )

        self.gcs_bucket_name = os.getenv("GCS_BUCKET_NAME")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.service_account_email = os.getenv("SERVICE_ACCOUNT_EMAIL")

        self.port = int(os.getenv("PORT", "8080"))

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def celery_backend_url(self) -> Optional[str]:
        if not self.enable_result_backend:
            return None
        return self._celery_result_backend_url or self.redis_url


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
