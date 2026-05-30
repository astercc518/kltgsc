"""
Common test fixtures for the TGSC backend test suite.

Provides:
- In-memory SQLite database session
- FastAPI TestClient with DB override
- Helper fixtures for creating test accounts and proxies
"""
import os
import sys
import types

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

# ---------------------------------------------------------------------------
# Stub out celery + kombu so the test environment doesn't need them installed.
# The actual tasks are never executed in tests — callers mock .delay().
# ---------------------------------------------------------------------------
def _make_celery_stub():
    """Return a minimal Celery stub sufficient to let app.worker import cleanly."""

    class _FakeConf:
        def update(self, **kwargs):
            pass

    class Task:
        """Minimal stub for celery.Task base class."""
        name = ""
        autoretry_for = ()
        retry_backoff = False
        retry_backoff_max = 600
        retry_jitter = False

        def on_failure(self, exc, task_id, args, kwargs, einfo):
            pass

        def on_retry(self, exc, task_id, args, kwargs, einfo):
            pass

        def on_success(self, retval, task_id, args, kwargs):
            pass

    class _FakeCelery:
        def __init__(self, *a, **kw):
            self.conf = _FakeConf()
            self.Task = Task

        def task(self, *a, **kw):
            def decorator(fn):
                fn.delay = lambda *a, **kw: type("R", (), {"id": "fake-task-id"})()
                fn.apply_async = lambda *a, **kw: type("R", (), {"id": "fake-task-id"})()
                return fn
            return decorator

        def config_from_object(self, *a, **kw):
            pass

        def autodiscover_tasks(self, *a, **kw):
            pass

    mod = types.ModuleType("celery")
    mod.Celery = _FakeCelery
    mod.Task = Task
    return mod


def _make_kombu_stub():
    class _FakeQueue:
        def __init__(self, *a, **kw):
            pass

    mod = types.ModuleType("kombu")
    mod.Queue = _FakeQueue
    return mod


if "celery" not in sys.modules:
    _celery_mod = _make_celery_stub()
    sys.modules["celery"] = _celery_mod

    # celery.exceptions  — SoftTimeLimitExceeded used in many task files
    _exc_mod = types.ModuleType("celery.exceptions")

    class SoftTimeLimitExceeded(Exception):
        pass

    _exc_mod.SoftTimeLimitExceeded = SoftTimeLimitExceeded
    sys.modules["celery.exceptions"] = _exc_mod

    # celery.schedules  — crontab used in celery_app.py beat_schedule
    _sched_mod = types.ModuleType("celery.schedules")

    class _FakeCrontab:
        """Minimal crontab stub — never executed in unit tests."""
        def __init__(self, *a, **kw):
            pass

    _sched_mod.crontab = _FakeCrontab
    sys.modules["celery.schedules"] = _sched_mod

    # celery.result  — AsyncResult used in task status endpoints
    _result_mod = types.ModuleType("celery.result")

    class AsyncResult:
        def __init__(self, task_id, *a, **kw):
            self.id = task_id
            self.status = "PENDING"
            self.result = None

        def get(self, *a, **kw):
            return None

    _result_mod.AsyncResult = AsyncResult
    sys.modules["celery.result"] = _result_mod

    # shared_task decorator (used by billing_tasks)
    def shared_task(*a, **kw):
        def decorator(fn):
            fn.delay = lambda *a, **kw: type("R", (), {"id": "fake-task-id"})()
            fn.apply_async = lambda *a, **kw: type("R", (), {"id": "fake-task-id"})()
            return fn
        # If called with no arguments (bare @shared_task), the first arg is the fn
        if len(a) == 1 and callable(a[0]) and not kw:
            return decorator(a[0])
        return decorator

    _celery_mod.shared_task = shared_task

if "kombu" not in sys.modules:
    sys.modules["kombu"] = _make_kombu_stub()

# ---------------------------------------------------------------------------
# Pre-stub heavy native deps that aren't installed in the test env.
# Must run BEFORE any `import app.*` because telegram_client imports them
# at module load time.
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock

for _mod_name in (
    "pyrogram",
    "pyrogram.errors",
    "pyrogram.types",
    "pyrogram.client",
    "pyrogram.enums",
    "telethon",
    "telethon.sessions",
    "telethon.tl",
    "telethon.tl.types",
    "telethon.errors",
    "aiohttp",
    "openai",
):
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

# Eagerly import every model so SQLModel.metadata sees every table
# before create_all runs. Without this, only the models that get
# imported by individual fixtures end up in the metadata, and any FK
# referencing one of the unimported tables (e.g. account.customer_id →
# customer) fails to resolve at create_all time.
import app.models  # noqa: F401


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
