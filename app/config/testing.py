"""Testing environment configuration for DocuMind AI."""

from app.config.base import BaseConfig


class TestingConfig(BaseConfig):
    """Testing configuration with SQLite in-memory database."""

    DEBUG: bool = True
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    WTF_CSRF_ENABLED: bool = False
    RATELIMIT_ENABLED: bool = False
    SQLALCHEMY_ECHO: bool = False
