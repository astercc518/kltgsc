"""Account role and tier constants — single source of truth.

`Account.role` records the account's functional position in the system
(allocation / listener / proxy / stats). `Account.tier` records the
permission tier used downstream by shill_dispatcher and
permission_service. Tier is derived from role; the UI no longer
exposes tier directly.

See CONVENTIONS.md §2 "Roles Matrix" for the consumer map.
"""
from typing import Optional


# Values accepted by /accounts role-setting endpoints and import tasks.
# `main` is reserved for customer QR-login binding (Customer.main_account_id)
# and must NOT appear in admin-facing role pickers — but the backend still
# accepts it because import flows can set it programmatically.
VALID_ROLES = frozenset({
    "worker", "master", "support", "sales", "listener", "collector", "main",
})

_TIER1_ROLES = frozenset({"master", "main"})
_TIER2_ROLES = frozenset({"support", "sales", "collector"})


def tier_for_role(role: Optional[str]) -> str:
    """Map a functional role to its permission tier.

    Unknown / falsy / `worker` / `listener` all fall to tier3 (the most
    restricted tier). Keep this aligned with shill_dispatcher.py and
    permission_service.py.
    """
    if role in _TIER1_ROLES:
        return "tier1"
    if role in _TIER2_ROLES:
        return "tier2"
    return "tier3"


# ── Epic 1 — usage-level UI sugar ─────────────────────────────────────
# Admin's "使用等级 1/2/3" is a UX label over a subset of role values.
# DB still stores `role`; this map is purely for translating between
# admin UI selectors and the underlying role string. Roles outside this
# subset (master / sales / collector / main) have no usage_level — those
# are reserved for admin/system flows and never appear in the import
# picker.
USAGE_LEVEL_TO_ROLE: dict[int, str] = {
    1: "worker",     # 高危操作（群发/采集/拉群）
    2: "listener",   # 监听引流
    3: "support",    # 客服交流
}

ROLE_TO_USAGE_LEVEL: dict[str, int] = {
    role: level for level, role in USAGE_LEVEL_TO_ROLE.items()
}

USAGE_LEVEL_LABEL_ZH: dict[int, str] = {
    1: "高危操作（群发/采集/拉群）",
    2: "监听引流",
    3: "客服交流",
}


def role_for_usage_level(level: Optional[int]) -> Optional[str]:
    """Translate UI 等级 1/2/3 to DB role. Returns None for invalid input."""
    if level is None:
        return None
    return USAGE_LEVEL_TO_ROLE.get(level)


def usage_level_for_role(role: Optional[str]) -> Optional[int]:
    """Inverse of role_for_usage_level. Returns None for roles outside the picker subset."""
    if not role:
        return None
    return ROLE_TO_USAGE_LEVEL.get(role)
