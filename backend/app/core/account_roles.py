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
