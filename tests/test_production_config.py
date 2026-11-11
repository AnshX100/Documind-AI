"""Regression tests for production-only security configuration."""

import pytest

from app import create_app


def _set_production_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///production-config-test.db")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "rediss://localhost:6379/0")


def test_production_rejects_missing_secret(monkeypatch):
    _set_production_environment(monkeypatch)
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ValueError, match="SECRET_KEY"):
        create_app("production")


def test_production_rejects_short_secret(monkeypatch):
    _set_production_environment(monkeypatch)
    monkeypatch.setenv("SECRET_KEY", "too-short")

    with pytest.raises(ValueError, match="at least 32 characters"):
        create_app("production")


def test_production_rejects_memory_rate_limit_storage(monkeypatch):
    _set_production_environment(monkeypatch)
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")

    with pytest.raises(ValueError, match="Redis"):
        create_app("production")


def test_production_accepts_required_configuration(monkeypatch):
    _set_production_environment(monkeypatch)

    app = create_app("production")

    assert app.config["SECRET_KEY"] == "a" * 48
    assert app.config["RATELIMIT_STORAGE_URI"] == "rediss://localhost:6379/0"
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
