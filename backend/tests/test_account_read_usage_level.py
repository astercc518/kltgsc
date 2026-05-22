"""AccountRead serializes a derived `usage_level` field from role."""
from datetime import datetime

from app.models.account import Account, AccountRead


def _make_account(role: str | None) -> Account:
    return Account(
        id=1,
        phone_number="+10000000000",
        role=role,
        created_at=datetime.utcnow(),
    )


def test_account_read_usage_level_worker():
    ar = AccountRead.model_validate(_make_account("worker"))
    assert ar.usage_level == 1


def test_account_read_usage_level_listener():
    ar = AccountRead.model_validate(_make_account("listener"))
    assert ar.usage_level == 2


def test_account_read_usage_level_support():
    ar = AccountRead.model_validate(_make_account("support"))
    assert ar.usage_level == 3


def test_account_read_usage_level_other_role_is_none():
    for role in ("master", "sales", "collector", "main"):
        ar = AccountRead.model_validate(_make_account(role))
        assert ar.usage_level is None, f"role={role} should yield None"


def test_account_read_usage_level_no_role_is_none():
    ar = AccountRead.model_validate(_make_account(None))
    assert ar.usage_level is None
