"""Tests do not depend on backend/.env: the answer prompt is the measured v2 unless a test sets another one (monkeypatch after this),
and the intent router, the output policy and the guard are off unless a test turns them on (the router needs the embedding model: tests give it a fake one;
the guard calls the language model: tests give it a fake verdict)."""
import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-deployment")  # before app.core.config is imported: it has no default

import pytest


@pytest.fixture(autouse=True)
def _measured_prompt(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v2")
    monkeypatch.setattr(settings, "INTENT_ROUTER_ENABLED", False)
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", False)
    monkeypatch.setattr(settings, "GUARD_ENABLED", False)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """The login / reset-code limits live in memory: every test starts with none used."""
    from app.shared.rate_limit import limiter

    limiter.reset()
