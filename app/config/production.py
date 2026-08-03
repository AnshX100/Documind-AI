"""Production environment configuration for DocuMind AI."""

import os
from app.config.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production configuration enforcing strict security and performance."""

    DEBUG: bool = False
    TESTING: bool = False
    SESSION_COOKIE_SECURE: bool = True
    REMEMBER_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    REMEMBER_COOKIE_HTTPONLY: bool = True

    def __init__(self) -> None:
        super().__init__()
        if self.SECRET_KEY == "default-dev-secret-key-must-be-changed":
            raise ValueError("SECRET_KEY environment variable must be set in Production!")
