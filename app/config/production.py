"""Production environment configuration for DocuMind AI."""

from app.config.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production configuration with secure defaults."""

    DEBUG = False
    TESTING = False

    # Production secrets and shared infrastructure are mandatory.
    # create_app() loads and validates these dynamically at startup.
    SECRET_KEY = None
    RATELIMIT_STORAGE_URI = None

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    PREFERRED_URL_SCHEME = "https"
