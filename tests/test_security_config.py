import pytest

from server.core.config import settings, validate_security_settings


def test_development_allows_empty_auth_key(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")

    validate_security_settings()


def test_production_rejects_missing_auth_key(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")

    with pytest.raises(RuntimeError, match="API_AUTH_KEY"):
        validate_security_settings()


def test_production_accepts_strong_auth_key(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "x" * 32)

    validate_security_settings()
