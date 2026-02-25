"""
Common test fixtures for the TGSC backend test suite.

Provides:
- In-memory SQLite database session
- FastAPI TestClient with DB override
- Helper fixtures for creating test accounts and proxies
"""
import os
import sys

# Ensure settings are test-friendly before any app imports.
# These must be set before importing anything from app.core.config
# because `settings` is created at module level.
os.environ.setdefault("SECRET_KEY", "a" * 64)
os.environ.setdefault("SESSION_ENCRYPTION_KEY", "b" * 32)
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword1234")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECURITY_ENABLED", "false")

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with all tables."""
    _engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(_engine)
    return _engine


@pytest.fixture
def session(engine):
    """Provide a transactional database session for tests."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    """
    FastAPI TestClient with the DB session dependency overridden
    to use the in-memory test database.
    """
    from app.main import app
    from app.core.db import get_session

    def _override_get_session():
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_account(session):
    """Create and return a single test Account persisted in the DB."""
    from app.models.account import Account

    account = Account(
        phone_number="+1234567890",
        session_string="test_session",
        session_file_path="sessions/test.session",
        status="active",
        api_id=12345,
        api_hash="abcdef1234567890",
        created_at=datetime.utcnow() - timedelta(days=15),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@pytest.fixture
def sample_proxy(session):
    """Create and return a single test Proxy persisted in the DB."""
    from app.models.proxy import Proxy

    proxy = Proxy(
        ip="127.0.0.1",
        port=1080,
        protocol="socks5",
        status="active",
        category="static",
        provider_type="datacenter",
    )
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    return proxy


@pytest.fixture
def new_account(session):
    """Create an account that is less than 7 days old (new account)."""
    from app.models.account import Account

    account = Account(
        phone_number="+1111111111",
        session_string="",
        status="active",
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@pytest.fixture
def trusted_account(session):
    """Create an account that is more than 30 days old (trusted account)."""
    from app.models.account import Account

    account = Account(
        phone_number="+2222222222",
        session_string="",
        status="active",
        created_at=datetime.utcnow() - timedelta(days=60),
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account
