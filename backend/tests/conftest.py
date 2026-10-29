"""Tests do not depend on backend/.env: the answer prompt is the measured v2 unless a test sets another one (monkeypatch after this)."""
import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-deployment")  # before app.core.config is imported: it has no default

import pytest


@pytest.fixture(autouse=True)
def _measured_prompt(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v2")
