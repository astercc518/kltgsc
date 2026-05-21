"""S2.2 / S2.3 smoke test — customer monitor endpoint + feature gate.

Exercises the new /customer/monitors REST surface end-to-end against a
live backend:
    - reject create when ai_marketing_assistant feature is disabled (402)
    - admin enables the feature
    - create succeeds (default passive)
    - create with reply_mode=private_dm explicitly rejected (400)
    - create with marketing_mode=active + reply_mode=group_reply succeeds,
      and max_replies_per_day is auto-capped if > 20
    - missing target_groups rejected (400)
    - list shows only this customer's rows (cross-tenant isolation)
    - update / delete work

Run inside the backend container:
    docker exec tgsc-backend-1 python3 /app/smoke_customer_monitor.py

Prereq: ADMIN_PASSWORD env var. A throw-away customer is provisioned
inline via /admin/billing/quick-provision; nothing else needs to exist.
"""
import os
import secrets
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

FEATURE_SLUG = "ai_marketing_assistant"

# Throw-away identifiers for this run. Email is unique so re-runs don't
# collide; password is fixed because we generate it locally.
SMOKE_EMAIL = f"smoke-mon-{secrets.token_hex(4)}@x.tg1.ai"
SMOKE_PASSWORD = "SmokeMon-Test1234!"


def step(name: str, ok: bool, detail: str = "") -> None:
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def login_admin(client: httpx.Client) -> dict:
    if not ADMIN_PASSWORD:
        print("  ADMIN_PASSWORD env not set; aborting (admin token required)")
        sys.exit(2)
    r = client.post(
        "/login/access-token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    step("admin login ok", r.status_code == 200, f"HTTP {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def provision_smoke_customer(client: httpx.Client, admin_h: dict) -> int:
    """Create a fresh customer + activate growth plan in one admin call."""
    r = client.post(
        "/admin/billing/quick-provision",
        json={
            "new_customer_email": SMOKE_EMAIL,
            "new_customer_password": SMOKE_PASSWORD,
            "new_customer_name": "Smoke Monitor",
            "plan": "growth",
            "wallet_credit_cents": 50_000,  # $500 buffer
            "note": "smoke_customer_monitor.py",
        },
        headers=admin_h,
    )
    step("quick-provision ok", r.status_code in (200, 201),
         f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["customer_id"]


def login_customer(client: httpx.Client) -> dict:
    r = client.post("/customer/login", json={
        "email": SMOKE_EMAIL, "password": SMOKE_PASSWORD,
    })
    step("customer login ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def set_feature(client: httpx.Client, admin_h: dict, cid: int, enabled: bool):
    r = client.put(
        f"/admin/customers/{cid}/features/{FEATURE_SLUG}",
        json={"enabled": enabled},
        headers=admin_h,
    )
    step(f"admin {'enable' if enabled else 'disable'} {FEATURE_SLUG} ok",
         r.status_code == 200, f"HTTP {r.status_code}: {r.text[:150]}")


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=10)

    print("=== Setup ===")
    admin_h = login_admin(client)
    cust_id = provision_smoke_customer(client, admin_h)
    cust_h = login_customer(client)
    print(f"  customer_id={cust_id}  email={SMOKE_EMAIL}")

    # ── 1) Feature gate ──────────────────────────────────────────────
    print("\n=== 1) Disable feature → POST should 402 ===")
    set_feature(client, admin_h, cust_id, enabled=False)
    r = client.post(
        "/customer/monitors",
        json={
            "keyword": "smoke-feature-gate",
            "target_groups": "@smoke_group_a",
            "marketing_mode": "passive",
        },
        headers=cust_h,
    )
    step("disabled feature → 402", r.status_code == 402,
         f"HTTP {r.status_code}: {r.text[:150]}")

    # ── 2) Enable feature, create passive monitor ────────────────────
    print("\n=== 2) Enable feature, create passive monitor ===")
    set_feature(client, admin_h, cust_id, enabled=True)
    r = client.post(
        "/customer/monitors",
        json={
            "keyword": "smoke-passive-001",
            "target_groups": "@smoke_group_a, @smoke_group_b",
            "marketing_mode": "passive",
        },
        headers=cust_h,
    )
    step("create passive ok", r.status_code == 201,
         f"HTTP {r.status_code}: {r.text[:200]}")
    mon = r.json()
    passive_id = mon["id"]
    step("customer_id pinned to caller", mon["customer_id"] == cust_id,
         f"got {mon['customer_id']}")
    step("created_by_sales_user_id stays NULL", mon["created_by_sales_user_id"] is None)

    # ── 3) Active + private_dm rejected ──────────────────────────────
    print("\n=== 3) active + private_dm → 400 ===")
    r = client.post(
        "/customer/monitors",
        json={
            "keyword": "smoke-dm-reject",
            "target_groups": "@smoke_group_a",
            "marketing_mode": "active",
            "reply_mode": "private_dm",
        },
        headers=cust_h,
    )
    step("active+private_dm rejected", r.status_code == 400,
         f"HTTP {r.status_code}: {r.text[:200]}")

    # ── 4) Active + group_reply OK, daily cap auto-applied ──────────
    print("\n=== 4) active + group_reply → 201, max_replies_per_day capped ===")
    r = client.post(
        "/customer/monitors",
        json={
            "keyword": "smoke-active-001",
            "target_groups": "@smoke_group_a",
            "marketing_mode": "active",
            "reply_mode": "group_reply",
            "max_replies_per_day": 500,  # request well above the cap
        },
        headers=cust_h,
    )
    step("create active ok", r.status_code == 201,
         f"HTTP {r.status_code}: {r.text[:200]}")
    active_mon = r.json()
    active_id = active_mon["id"]
    step("max_replies_per_day capped to 20", active_mon["max_replies_per_day"] == 20,
         f"got {active_mon['max_replies_per_day']}")
    step("reply_mode == group_reply", active_mon["reply_mode"] == "group_reply")

    # ── 5) Missing target_groups rejected ────────────────────────────
    print("\n=== 5) Missing target_groups → 400 ===")
    r = client.post(
        "/customer/monitors",
        json={"keyword": "smoke-no-targets"},
        headers=cust_h,
    )
    step("no target_groups rejected", r.status_code == 400,
         f"HTTP {r.status_code}: {r.text[:200]}")

    # ── 6) Listing shows only my rules ───────────────────────────────
    print("\n=== 6) List shows both smoke rows ===")
    r = client.get("/customer/monitors", headers=cust_h)
    step("list ok", r.status_code == 200)
    mine = r.json()
    step("two smoke rules visible",
         any(m["id"] == passive_id for m in mine) and any(m["id"] == active_id for m in mine),
         f"saw {len(mine)} rows")
    step("all rows scoped to me",
         all(m["customer_id"] == cust_id for m in mine))

    # ── 7) Update — try to flip to active+private_dm via PUT → 400 ──
    print("\n=== 7) PUT to active+private_dm → 400 ===")
    r = client.put(
        f"/customer/monitors/{passive_id}",
        json={"marketing_mode": "active", "reply_mode": "private_dm"},
        headers=cust_h,
    )
    step("update active+private_dm rejected", r.status_code == 400,
         f"HTTP {r.status_code}: {r.text[:200]}")

    # ── 8) Update — flip passive monitor to active+group_reply ──────
    print("\n=== 8) PUT to active+group_reply → 200, cap applied ===")
    r = client.put(
        f"/customer/monitors/{passive_id}",
        json={"marketing_mode": "active"},  # reply_mode stays group_reply
        headers=cust_h,
    )
    step("update ok", r.status_code == 200,
         f"HTTP {r.status_code}: {r.text[:200]}")
    step("flipped to active", r.json()["marketing_mode"] == "active")
    step("daily cap enforced (≤20)", r.json()["max_replies_per_day"] <= 20,
         f"got {r.json()['max_replies_per_day']}")

    # ── 9) Delete both ──────────────────────────────────────────────
    print("\n=== 9) Delete both smoke monitors ===")
    for mid in (passive_id, active_id):
        r = client.delete(f"/customer/monitors/{mid}", headers=cust_h)
        step(f"delete #{mid} ok", r.status_code == 200,
             f"HTTP {r.status_code}: {r.text[:200]}")

    r = client.get("/customer/monitors", headers=cust_h)
    remaining = [m for m in r.json() if m["keyword"].startswith("smoke-")]
    step("no smoke rows remain", len(remaining) == 0)

    print("\n[PASS] smoke_customer_monitor")


if __name__ == "__main__":
    main()
