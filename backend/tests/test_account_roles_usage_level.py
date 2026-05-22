"""usage_level <-> role bidirectional mapping for Epic 1 UI sugar."""
import pytest

from app.core.account_roles import (
    USAGE_LEVEL_TO_ROLE,
    ROLE_TO_USAGE_LEVEL,
    USAGE_LEVEL_LABEL_ZH,
    role_for_usage_level,
    usage_level_for_role,
)


def test_forward_map_covers_levels_1_2_3():
    assert USAGE_LEVEL_TO_ROLE == {1: "worker", 2: "listener", 3: "support"}


def test_reverse_map_is_consistent():
    for lvl, role in USAGE_LEVEL_TO_ROLE.items():
        assert ROLE_TO_USAGE_LEVEL[role] == lvl


def test_labels_present_for_each_level():
    for lvl in (1, 2, 3):
        assert lvl in USAGE_LEVEL_LABEL_ZH
        assert USAGE_LEVEL_LABEL_ZH[lvl]


def test_role_for_usage_level_valid():
    assert role_for_usage_level(1) == "worker"
    assert role_for_usage_level(2) == "listener"
    assert role_for_usage_level(3) == "support"


def test_role_for_usage_level_none_or_invalid_returns_none():
    assert role_for_usage_level(None) is None
    assert role_for_usage_level(0) is None
    assert role_for_usage_level(4) is None
    assert role_for_usage_level(99) is None


def test_usage_level_for_role_known():
    assert usage_level_for_role("worker") == 1
    assert usage_level_for_role("listener") == 2
    assert usage_level_for_role("support") == 3


def test_usage_level_for_role_unmapped_returns_none():
    # master / sales / collector / main have no usage-level concept
    assert usage_level_for_role("master") is None
    assert usage_level_for_role("collector") is None
    assert usage_level_for_role("main") is None
    assert usage_level_for_role(None) is None
    assert usage_level_for_role("nonsense") is None
