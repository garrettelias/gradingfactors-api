"""
Shared pytest configuration and fixtures.

Environment variables must be set before any api.* imports because api/db.py
calls supabase.create_client() at module load time and raises RuntimeError if
they are absent. create_client() is lazy (no network connection at
construction time), so dummy values are sufficient to satisfy the check.
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from api.dependencies import verify_api_key
from api.main import app

# Key accepted by the standard test client auth stub.
TEST_KEY = "gf_live_testkey0000000000000000"


def _stub_strict(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Accept only TEST_KEY; reject everything else with 401."""
    if x_api_key != TEST_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key


def _stub_permissive(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Accept any non-None key; used for rate-limit testing."""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return x_api_key


@pytest.fixture
def client():
    """TestClient with strict auth: only TEST_KEY is accepted."""
    app.dependency_overrides[verify_api_key] = _stub_strict
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)


@pytest.fixture
def rate_limit_client():
    """TestClient with permissive auth for rate-limit testing.

    Uses a separate auth stub so tests can send arbitrary keys without
    polluting TEST_KEY's rate-limit window, which is shared in-process.
    """
    app.dependency_overrides[verify_api_key] = _stub_permissive
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(verify_api_key, None)
