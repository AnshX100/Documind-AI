"""Configuration package for DocuMind AI."""

from app.config.base import BaseConfig
from app.config.development import DevelopmentConfig
from app.config.production import ProductionConfig

__all__ = ["BaseConfig", "DevelopmentConfig", "ProductionConfig", "config_by_name"]

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
