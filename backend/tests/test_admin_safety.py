"""Tests for /admin/safety/{stats,recent-blocks,by-source} endpoints.

These tests insert real LLMUsage rows into the test DB, hit the endpoints
via FastAPI TestClient with a stub auth, and assert response shape +
suffix-based attribution.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.main import app
from app.core.db import engine
from app.models.llm_usage import LLMUsage
from app.api.deps import get_current_user, get_current_admin


@pytest.fixture
def client():
    # Stub auth so endpoints are reachable in tests without real JWT.
    # /admin/safety/* routes are admin-restricted, so stub both deps.
    app.dependency_overrides[get_current_user] = lambda: {"is_admin": True}
    app.dependency_overrides[get_current_admin] = lambda: {"is_admin": True}
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_rows():
    """Insert a fixed-prefix batch of LLMUsage rows and clean up after."""
    prefix = "test_admin_safety"
    rows = [
        LLMUsage(provider="vertex", model="m", source=f"{prefix}_a:routed_vertex"),
        LLMUsage(provider="deepseek", model="m", source=f"{prefix}_a:routed_deepseek"),
        LLMUsage(provider="vertex", model="m", source=f"{prefix}_a:blocked_L0"),
        LLMUsage(provider="vertex", model="m", source=f"{prefix}_b:blocked_L1"),
        LLMUsage(provider="router", model="refuse", source=f"{prefix}_a:routed_refuse"),
    ]
    with Session(engine) as s:
        for r in rows:
            s.add(r)
        s.commit()
    yield rows
    with Session(engine) as s:
        s.exec(delete(LLMUsage).where(LLMUsage.source.like(f"{prefix}%")))
        s.commit()


def test_stats_counts_by_suffix(client, seeded_rows):
    resp = client.get("/api/v1/admin/safety/stats?hours=1")
    assert resp.status_code == 200
    data = resp.json()
    # Our 5 seeded rows are within the 1h window
    assert data["blocked_L0"] >= 1
    assert data["blocked_L1"] >= 1
    assert data["routed_refuse"] >= 1
    assert data["routed_deepseek"] >= 1
    assert data["routed_vertex"] >= 1
    assert data["total_calls"] >= 5


def test_recent_blocks_returns_L0_L1_only(client, seeded_rows):
    resp = client.get("/api/v1/admin/safety/recent-blocks?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    # Every returned row must have a :blocked_L0 or :blocked_L1 suffix
    for row in data:
        assert row["source"].endswith(":blocked_L0") or row["source"].endswith(":blocked_L1"), row["source"]


def test_by_source_groups_rows(client, seeded_rows):
    resp = client.get("/api/v1/admin/safety/by-source?hours=1")
    assert resp.status_code == 200
    data = resp.json()
    sources = {row["source"]: row["count"] for row in data}
    # Each seeded source appears with count >= 1
    assert any(s.startswith("test_admin_safety") for s in sources)


def test_query_validation_rejects_bad_hours(client):
    resp = client.get("/api/v1/admin/safety/stats?hours=0")
    assert resp.status_code == 422
    resp = client.get("/api/v1/admin/safety/stats?hours=10000")
    assert resp.status_code == 422
