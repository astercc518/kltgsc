"""Epic 2 smoke test — subscribe (customer) → activate (admin) → quota refreshed.

Run inside the backend container:
    docker exec tgsc-backend-1 python3 /app/smoke_billing.py

Prereqs:
    - Epic 1 customer 'smoke@tg1.ai' exists (created by smoke_customer.py)
    - Admin user exists with ADMIN_USERNAME / ADMIN_PASSWORD from env
    - USDT_ADDRESS_TRC20 is set in .env (placeholder OK for the smoke test)
"""
import os
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def step(name: str, ok: bool, detail: str = "") -> None:
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=10)

    # ── Customer login (created by Epic 1 smoke) ─────────────────────
    print("=== 1) Login customer ===")
    r = client.post("/customer/login", json={
        "email": "smoke@tg1.ai", "password": "Test1234!"
    })
    step("login ok", r.status_code == 200, f"HTTP {r.status_code}")
    body = r.json()
    cust_token = body["access_token"]
    customer = body["customer"]
    print(f"  customer_id={customer['id']}  status={customer['status']}  plan={customer['plan']}")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # ── Subscribe to growth plan ─────────────────────────────────────
    print("\n=== 2) POST /customer/subscribe (growth/TRC20) ===")
    r = client.post("/customer/subscribe",
                    json={"plan": "growth", "network": "TRC20"},
                    headers=cust_headers)
    step("subscribe ok", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:200]}")
    invoice = r.json()
    print(f"  invoice_id={invoice['id']}  amount={invoice['amount_crypto']} USDT  "
          f"net={invoice['network']}  addr={invoice['payment_address'][:18]}...")
    step("amount_usd == 299", invoice["amount_usd"] == 299.0)
    step("amount_crypto in [299.01, 299.99]",
         299.0 < invoice["amount_crypto"] <= 299.99,
         f"amount={invoice['amount_crypto']}")
    step("status pending", invoice["status"] == "pending")
    step("has address", len(invoice["payment_address"]) > 5)

    # ── Idempotency: second subscribe with same plan returns same invoice ──
    print("\n=== 3) Subscribe again — idempotent ===")
    r2 = client.post("/customer/subscribe",
                     json={"plan": "growth", "network": "TRC20"},
                     headers=cust_headers)
    step("returns same invoice", r2.json()["id"] == invoice["id"],
         f"first={invoice['id']} second={r2.json().get('id')}")

    # ── List + fetch ──────────────────────────────────────────────────
    print("\n=== 4) List + fetch invoice ===")
    r = client.get("/customer/invoices", headers=cust_headers)
    step("list invoices ok", r.status_code == 200 and len(r.json()) >= 1)
    r = client.get(f"/customer/invoices/{invoice['id']}", headers=cust_headers)
    step("fetch one ok", r.status_code == 200 and r.json()["id"] == invoice["id"])

    # ── Subscription endpoint: 404 because not yet activated ──────────
    print("\n=== 5) GET /customer/subscription before activation ===")
    r = client.get("/customer/subscription", headers=cust_headers)
    step("no active sub -> 404", r.status_code == 404, f"HTTP {r.status_code}")

    # ── Admin login ──────────────────────────────────────────────────
    print("\n=== 6) Admin login ===")
    if not ADMIN_PASSWORD:
        print(f"  [skip] ADMIN_PASSWORD env not set; skipping activation steps")
        print("\n[PARTIAL PASS — set ADMIN_PASSWORD to run full E2E]")
        return

    r = client.post("/login/access-token", data={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    step("admin login ok", r.status_code == 200,
         f"HTTP {r.status_code}: {r.text[:200]}")
    admin_token = r.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # ── Admin sees pending invoice ────────────────────────────────────
    print("\n=== 7) Admin: list pending invoices ===")
    r = client.get("/admin/billing/invoices?status=pending", headers=admin_headers)
    step("admin sees pending invoices", r.status_code == 200 and len(r.json()) >= 1,
         f"HTTP {r.status_code}: {r.text[:200]}")

    # ── Admin activates ──────────────────────────────────────────────
    print("\n=== 8) Admin: activate subscription ===")
    r = client.post(
        f"/admin/billing/customers/{customer['id']}/activate-subscription",
        json={"invoice_id": invoice["id"], "tx_hash": "0xtestsmoketxhash"},
        headers=admin_headers,
    )
    step("activate ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
    sub = r.json()
    print(f"  sub_id={sub['id']}  status={sub['status']}  plan={sub['plan']}")
    step("sub.status == active", sub["status"] == "active")
    step("sub.plan == growth", sub["plan"] == "growth")

    # ── Customer sees updated plan + quota ───────────────────────────
    print("\n=== 9) Customer /me + /quota reflect activation ===")
    r = client.get("/customer/me", headers=cust_headers)
    me = r.json()
    step("me.status == active", me["status"] == "active", f"status={me['status']}")
    step("me.plan == growth", me["plan"] == "growth")
    step("me.account_quota == 5", me["account_quota"] == 5)
    step("me.group_quota == 1000", me["group_quota"] == 1000)
    step("me.token_quota == 5M", me["token_quota"] == 5_000_000)

    r = client.get("/customer/quota", headers=cust_headers)
    q = r.json()
    step("quota.limits.account_quota == 5", q["limits"]["account_quota"] == 5)
    step("quota.usage.accounts == 0", q["usage"]["accounts"] == 0)

    # ── Subscription endpoint now returns the active sub ─────────────
    r = client.get("/customer/subscription", headers=cust_headers)
    step("active sub fetch ok", r.status_code == 200 and r.json()["status"] == "active")

    # ── Invoice now paid ─────────────────────────────────────────────
    r = client.get(f"/customer/invoices/{invoice['id']}", headers=cust_headers)
    inv = r.json()
    step("invoice.status == paid", inv["status"] == "paid")
    step("invoice.tx_hash recorded", inv["tx_hash"] == "0xtestsmoketxhash")

    # ── Idempotent re-activation ─────────────────────────────────────
    print("\n=== 10) Re-activate same invoice (idempotent) ===")
    r = client.post(
        f"/admin/billing/customers/{customer['id']}/activate-subscription",
        json={"invoice_id": invoice["id"], "tx_hash": "0xtestsmoketxhash"},
        headers=admin_headers,
    )
    step("re-activate returns 200 (idempotent)", r.status_code == 200)

    # ── Wrong customer for invoice -> 400 ────────────────────────────
    print("\n=== 11) Mismatched customer/invoice -> 400 ===")
    r = client.post(
        f"/admin/billing/customers/9999/activate-subscription",
        json={"invoice_id": invoice["id"], "tx_hash": "x"},
        headers=admin_headers,
    )
    step("mismatch -> 400", r.status_code == 400, f"HTTP {r.status_code}")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
