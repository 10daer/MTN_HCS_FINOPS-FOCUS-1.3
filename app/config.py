"""
Application settings loaded from environment variables.

Uses pydantic-settings to validate and type-cast env vars at startup.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────
    app_name: str = "MTN_HCS_FINOPS_FOCUS"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_version: str = "1.0.0"

    # ── Server ────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── HCS ManageOne — IAM (Authentication) ────────────────────────
    iam_domain: str = "https://iam.example.huaweicloud.com"
    iam_username: str = ""
    iam_password: str = ""
    iam_auth_domain: str = "mo_bss_admin"

    # ── HCS ManageOne — SC Northbound Interface ───────────────────────
    sc_domain: str = "https://sc.example.huaweicloud.com"
    sc_api_timeout: int = 30

    # ── Logging ───────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── CORS ──────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Cached singleton — settings are read once and reused.
    """
    return Settings()
