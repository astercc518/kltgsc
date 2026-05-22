"""4 admin import endpoints honor usage_level parameter (1=worker, 2=listener, 3=support)."""
import io
import pytest
from unittest.mock import patch

from sqlmodel import select
from app.models.account import Account


@pytest.fixture
def admin_client(client, session):
    """A TestClient pre-authenticated as admin."""
    from app.core.security import create_access_token
    token = create_access_token("admin")
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_upload_session_usage_level_1_sets_role_worker(admin_client, session, monkeypatch):
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990001"

    def fake_parse(*args, **kwargs):
        return (fake_phone, {})

    monkeypatch.setattr(accounts_mod, "parse_session_file", fake_parse)

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=1", files=files)
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc is not None
    assert acc.role == "worker"


def test_upload_session_usage_level_2_sets_role_listener(admin_client, session, monkeypatch):
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990002"
    monkeypatch.setattr(
        accounts_mod, "parse_session_file",
        lambda *a, **k: (fake_phone, {}),
    )

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=2", files=files)
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc.role == "listener"


def test_upload_session_usage_level_overrides_role_param(admin_client, session, monkeypatch):
    """When both role= and usage_level= are passed, usage_level wins."""
    from app.api.v1.endpoints import accounts as accounts_mod
    fake_phone = "+19999990003"
    monkeypatch.setattr(
        accounts_mod, "parse_session_file",
        lambda *a, **k: (fake_phone, {}),
    )

    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post(
        "/api/v1/accounts/upload?role=collector&usage_level=3",
        files=files,
    )
    assert resp.status_code in (200, 201), resp.text

    acc = session.exec(select(Account).where(Account.phone_number == fake_phone)).first()
    assert acc.role == "support"  # usage_level=3 wins over role=collector


def test_upload_session_usage_level_invalid_returns_400(admin_client):
    files = {"file": ("test.session", io.BytesIO(b"\x00" * 64), "application/octet-stream")}
    resp = admin_client.post("/api/v1/accounts/upload?usage_level=99", files=files)
    assert resp.status_code == 400


def test_mega_import_request_accepts_usage_level():
    """MegaImportRequest body model accepts usage_level."""
    from app.api.v1.endpoints.accounts import MegaImportRequest
    req = MegaImportRequest(urls=["https://mega.nz/x"], usage_level=2)
    assert req.usage_level == 2
    req2 = MegaImportRequest(urls=["https://mega.nz/x"], role="worker")
    assert req2.role == "worker"
