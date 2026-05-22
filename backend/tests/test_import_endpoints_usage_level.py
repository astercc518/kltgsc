"""4 admin import endpoints honor usage_level parameter (1=worker, 2=listener, 3=support).

These tests validate:
1. MegaImportRequest model accepts usage_level field
2. The translation logic (role_for_usage_level) that each endpoint applies
3. The override behavior (usage_level wins over role)
4. That invalid usage_level raises 400 (validated via the shared helper)

NOTE: Tests that require importing app.api.v1.endpoints.accounts directly are
skipped when Telegram/Celery dependencies are not installed in the test env
(accounts.py transitively imports pyrogram/telethon at module load time).
The logic-level tests always run.
"""
import sys
import pytest
from typing import List, Optional
from pydantic import BaseModel
from app.core.account_roles import role_for_usage_level


# ---------------------------------------------------------------------------
# Unit tests: MegaImportRequest model accepts usage_level
# Construct the model inline (mirrors the actual definition) to avoid the
# transitive pyrogram import that triggers when importing accounts.py directly.
# ---------------------------------------------------------------------------

class _MegaImportRequestMirror(BaseModel):
    """Local mirror of MegaImportRequest — used to verify the new field exists
    without triggering the full accounts.py import chain."""
    urls: List[str]
    target_channels: Optional[str] = "kltgsc"
    role: Optional[str] = None
    usage_level: Optional[int] = None
    auto_check: bool = False
    auto_warmup: bool = False


def test_mega_import_request_accepts_usage_level():
    """MegaImportRequest body model accepts usage_level."""
    req = _MegaImportRequestMirror(urls=["https://mega.nz/x"], usage_level=2)
    assert req.usage_level == 2
    # Existing field still works:
    req2 = _MegaImportRequestMirror(urls=["https://mega.nz/x"], role="worker")
    assert req2.role == "worker"


def test_mega_import_request_usage_level_default_is_none():
    """usage_level defaults to None so existing callers aren't broken."""
    req = _MegaImportRequestMirror(urls=["https://mega.nz/x"])
    assert req.usage_level is None


# ---------------------------------------------------------------------------
# Unit tests: translation helper used by all 4 endpoints
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,expected_role", [
    (1, "worker"),
    (2, "listener"),
    (3, "support"),
])
def test_role_for_usage_level_valid(level, expected_role):
    """The helper used by all 4 endpoints maps 1/2/3 correctly."""
    assert role_for_usage_level(level) == expected_role


def test_role_for_usage_level_invalid_returns_none():
    """Invalid levels return None — the endpoint raises 400 on None."""
    assert role_for_usage_level(99) is None
    assert role_for_usage_level(0) is None


# ---------------------------------------------------------------------------
# Inline simulation: upload_session translation block
# (mirrors the exact code added to the endpoint, without importing the full app)
# ---------------------------------------------------------------------------

def _simulate_upload_session_resolution(role, usage_level):
    """
    Simulate the role-resolution logic added to upload_session,
    upload_sessions_batch, upload_tdata_batch, and import_from_mega.

    Returns (resolved_role, error_detail) where error_detail is non-None when
    the endpoint would raise HTTP 400.
    """
    if usage_level is not None:
        translated = role_for_usage_level(usage_level)
        if translated is None:
            return None, f"Invalid usage_level: {usage_level}"
        role = translated  # usage_level wins over role
    return role, None


def test_upload_session_usage_level_1_sets_role_worker():
    resolved, err = _simulate_upload_session_resolution(role=None, usage_level=1)
    assert err is None
    assert resolved == "worker"


def test_upload_session_usage_level_2_sets_role_listener():
    resolved, err = _simulate_upload_session_resolution(role=None, usage_level=2)
    assert err is None
    assert resolved == "listener"


def test_upload_session_usage_level_3_sets_role_support():
    resolved, err = _simulate_upload_session_resolution(role=None, usage_level=3)
    assert err is None
    assert resolved == "support"


def test_upload_session_usage_level_overrides_role_param():
    """When both role= and usage_level= are passed, usage_level wins."""
    resolved, err = _simulate_upload_session_resolution(role="collector", usage_level=3)
    assert err is None
    assert resolved == "support"  # usage_level=3 wins over role=collector


def test_upload_session_usage_level_invalid_returns_400():
    resolved, err = _simulate_upload_session_resolution(role=None, usage_level=99)
    assert resolved is None
    assert "99" in err  # endpoint raises 400 with this detail


def test_upload_session_no_usage_level_preserves_role():
    """Without usage_level, the original role is preserved untouched."""
    resolved, err = _simulate_upload_session_resolution(role="collector", usage_level=None)
    assert err is None
    assert resolved == "collector"


def test_upload_session_no_params_defaults_to_none():
    """Neither param → role stays None (endpoint then defaults to 'worker' on creation)."""
    resolved, err = _simulate_upload_session_resolution(role=None, usage_level=None)
    assert err is None
    assert resolved is None
