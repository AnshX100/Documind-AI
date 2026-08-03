"""Development environment configuration for DocuMind AI."""

from app.config.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development configuration with debugging enabled."""

    DEBUG: bool = True
    TESTING: bool = False
    SQLALCHEMY_ECHO: bool = False
