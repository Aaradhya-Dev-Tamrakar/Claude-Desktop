from __future__ import annotations

import os
import pytest
from server.core.config import settings

@pytest.fixture(autouse=True)
def default_test_settings(monkeypatch):
    """Ensure test runs default to development mode with no API_AUTH_KEY unless explicitly set."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")
