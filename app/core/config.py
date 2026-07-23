"""
app/core/config.py
──────────────────
Centralised settings loaded once from .env / environment variables.
Pydantic-settings validates types at startup — if a required var is missing
you get a clear error immediately, not at request time.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "NIZAM-RUS"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5500"

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite by default; swap for PostgreSQL URL with zero code changes.
    database_url: str = "sqlite+aiosqlite:///./nizam_rus.db"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── Email Verification ────────────────────────────────────────────────────
    verification_token_expire_hours: int = 24

    # ── Resend (primary email provider) ───────────────────────────────────────
    resend_api_key: str = ""
    email_from: str = "noreply@yourdomain.com"
    email_from_name: str = "NIZAM-RUS"

    # ── SMTP fallback ─────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True

    # Pydantic-settings config: read from .env file automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# lru_cache means we parse .env only once per process lifetime
@lru_cache
def get_settings() -> Settings:
    return Settings()
