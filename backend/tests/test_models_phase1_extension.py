"""验证 Phase 1 model 扩展字段读写"""
import os
import pytest
from sqlmodel import Session, select
from app.models.customer import Customer
from app.models.keyword_monitor import KeywordMonitor, KeywordMonitorBase


def _get_postgres_url() -> str:
    """Return the DATABASE_URL only when it points at Postgres; else empty string."""
    db = os.environ.get("DATABASE_URL", "")
    if db.startswith(("postgresql", "postgres")):
        return db
    return ""


def _skip_if_not_postgres():
    if not _get_postgres_url():
        pytest.skip("requires Postgres")


# ---------------------------------------------------------------------------
# Import-time smoke tests — run even on SQLite / no-DB envs
# ---------------------------------------------------------------------------

def test_customer_model_has_icp_fields():
    """Model class must declare the new ICP fields (import-time check, no DB)."""
    assert hasattr(Customer, "icp_profile_text"), "missing icp_profile_text"
    assert hasattr(Customer, "icp_profile_embedding"), "missing icp_profile_embedding"
    assert hasattr(Customer, "lead_detector_thresholds"), "missing lead_detector_thresholds"
    assert hasattr(Customer, "param_version"), "missing param_version"


def test_keyword_monitor_base_has_keyword_filters():
    """KeywordMonitorBase must declare keyword_filters (import-time check, no DB).

    Non-table SQLModel base classes hold fields in model_fields (not as class
    attributes), so we check there rather than via hasattr().
    """
    assert "keyword_filters" in KeywordMonitorBase.model_fields, \
        "missing keyword_filters in KeywordMonitorBase.model_fields"
    assert hasattr(KeywordMonitor, "keyword_filters"), "missing keyword_filters on KeywordMonitor"


def test_customer_instantiation_defaults():
    """Customer() can be instantiated and default values are correct (no DB)."""
    c = Customer(email="test@example.com", hashed_password="x")
    assert c.icp_profile_text is None
    assert c.icp_profile_embedding is None
    thresholds = c.lead_detector_thresholds
    assert isinstance(thresholds, dict)
    assert "layer2_sim" in thresholds
    assert thresholds["layer2_sim"] == 0.55
    assert "layer3_score" in thresholds
    assert "layer3_confidence" in thresholds
    assert c.param_version == "v1"


def test_keyword_monitor_instantiation_default():
    """KeywordMonitor() can be instantiated and keyword_filters defaults to None."""
    km = KeywordMonitor(keyword="test", match_type="partial")
    assert km.keyword_filters is None


# ---------------------------------------------------------------------------
# DB round-trip tests — require Postgres with the phase1 migration applied
# ---------------------------------------------------------------------------

def test_customer_icp_fields_readable():
    # The conftest session fixture uses SQLite which doesn't support JSONB/pgvector.
    # These tests only run meaningfully against Postgres with the phase1 migration applied.
    # We open our own Postgres session to avoid triggering SQLite create_all with JSONB.
    pg_url = _get_postgres_url()
    if not pg_url:
        pytest.skip("requires Postgres DATABASE_URL with phase1 migration applied")
    from sqlalchemy import create_engine as _create_engine
    _engine = _create_engine(pg_url)
    with Session(_engine) as s:
        c = s.exec(select(Customer).limit(1)).first()
        if c is None:
            pytest.skip("no customer rows in test DB")
        # New fields should be accessible without AttributeError
        assert c.icp_profile_text is None or isinstance(c.icp_profile_text, str)
        assert isinstance(c.lead_detector_thresholds, dict)
        assert "layer2_sim" in c.lead_detector_thresholds
        assert c.param_version == "v1" or isinstance(c.param_version, str)


def test_customer_icp_write_roundtrip():
    pg_url = _get_postgres_url()
    if not pg_url:
        pytest.skip("requires Postgres DATABASE_URL with phase1 migration applied")
    from sqlalchemy import create_engine as _create_engine
    _engine = _create_engine(pg_url)
    with Session(_engine) as s:
        c = s.exec(select(Customer).limit(1)).first()
        if c is None:
            pytest.skip("no customer rows")
        original = c.icp_profile_text
        c.icp_profile_text = "test ICP value 2026"
        s.add(c)
        s.commit()
        s.refresh(c)
        assert c.icp_profile_text == "test ICP value 2026"
        # cleanup
        c.icp_profile_text = original
        s.add(c)
        s.commit()
