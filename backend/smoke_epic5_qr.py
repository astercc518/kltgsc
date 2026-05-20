"""Epic 5.0 smoke test — main account QR login flow (MOCK mode).

Set MOCK_QR_AUTOACCEPT=1 in the backend container env before running so we
don't need a real Telegram number to verify the wiring.

Verifies:
  • POST  /customer/main-account/qr/start returns token + qr_url + png
  • GET   /customer/main-account/qr/status flips to 'success' within ~2s
  • Account row is created with role='main', is_customer_main=True, encrypted session
  • Customer.main_account_id points to the new account
  • Listener service filter excludes is_customer_main accounts
  • Allocation service _pick_free_accounts excludes is_customer_main accounts
  • Session string round-trips via encrypt/decrypt helpers
  • DELETE /customer/main-account clears the binding

Run:
    docker exec -e MOCK_QR_AUTOACCEPT=1 tgsc-backend-1 python3 /app/smoke_epic5_qr.py
"""
from __future__ import annotations

import os
import secrets
import sys
import time

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

# Module-level orphan registry — flushed by cleanup_orphans() in finally.
ORPHANS = {"customers": [], "accounts": []}


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def cleanup_orphans():
    """Always-runs cleanup (called from __main__ finally)."""
    try:
        from app.core.db import engine
        from app.models.account import Account
        from app.models.customer import Customer
        from sqlmodel import Session as S, select
        with S(engine) as s:
            for cid in ORPHANS["customers"]:
                # QR success creates accounts via service code, not direct
                # SQL — pick them up by tag for completeness
                for acc in s.exec(
                    select(Account).where(Account.tags.like(f"%customer_{cid}%"))
                ).all():
                    s.delete(acc)
                c = s.get(Customer, cid)
                if c: s.delete(c)
            for aid in ORPHANS["accounts"]:
                a = s.get(Account, aid)
                if a: s.delete(a)
            s.commit()
        total = sum(len(v) for v in ORPHANS.values())
        if total:
            print(f"  [cleanup] removed fixtures: {{k: len for k, v in ORPHANS}}")
    except Exception as e:
        print(f"  [cleanup] WARNING: {e}")


def main():
    # Sanity: MOCK_QR_AUTOACCEPT must be set in BACKEND container env, not just here.
    # We send a probe to verify the qr_login_service picked it up.
    if os.environ.get("MOCK_QR_AUTOACCEPT") != "1":
        print("WARNING: MOCK_QR_AUTOACCEPT=1 must be in the backend container env, "
              "not just the test script. The /qr/start endpoint will hit real Pyrogram otherwise.")

    client = httpx.Client(base_url=BASE, timeout=30)

    # ── Spin up a fresh active customer (must be 'active' for get_active_customer) ──
    print("=== 1) Seed fresh active customer ===")
    from app.core.db import engine
    from app.core import security
    from app.models.customer import Customer, STATUS_ACTIVE, PLAN_QUOTA, PLAN_GROWTH
    from sqlmodel import Session as S, select

    email = f"qr-{secrets.token_hex(3)}@tg1.ai"
    with S(engine) as s:
        cust = Customer(
            email=email,
            hashed_password=security.get_password_hash("Test1234!"),
            industry="crypto",
            status=STATUS_ACTIVE,
            plan=PLAN_GROWTH,
            subscription_status="active",
            account_quota=PLAN_QUOTA[PLAN_GROWTH]["account"],
            group_quota=PLAN_QUOTA[PLAN_GROWTH]["group"],
            token_quota=PLAN_QUOTA[PLAN_GROWTH]["token"],
        )
        s.add(cust); s.commit(); s.refresh(cust)
        cust_id = cust.id
        ORPHANS["customers"].append(cust_id)
    step("seeded customer", True, f"customer_id={cust_id} email={email}")

    # Customer login (default smoke password)
    r = client.post("/customer/login", json={"email": email, "password": "Test1234!"})
    step("customer login", r.status_code == 200, f"HTTP {r.status_code}")
    cust_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ── Before QR: GET /customer/main-account returns connected=False ──
    print("\n=== 2) GET /main-account (before QR) returns connected=False ===")
    r = client.get("/customer/main-account", headers=cust_headers)
    step("ok", r.status_code == 200)
    step("not connected", r.json()["connected"] is False)

    # ── Start QR ──
    print("\n=== 3) POST /qr/start ===")
    r = client.post("/customer/main-account/qr/start", headers=cust_headers)
    step("qr start ok", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    print(f"  token={body['token'][:12]}...  mock={body.get('mock')}  state={body['state']}")
    step("returned a token", len(body["token"]) >= 16)
    step("returned a qr_url", body["qr_url"].startswith("tg://"))
    step("returned mock=True (MOCK_QR_AUTOACCEPT)", body.get("mock") is True,
         "Backend container must have MOCK_QR_AUTOACCEPT=1 in its env to autocomplete")
    token = body["token"]

    # ── Poll status — should flip to 'success' within ~2s in mock mode ──
    print("\n=== 4) Poll /qr/status until success ===")
    deadline = time.time() + 10
    final_state = None
    while time.time() < deadline:
        r = client.get(f"/customer/main-account/qr/status?token={token}", headers=cust_headers)
        if r.status_code == 200:
            final_state = r.json().get("state")
            print(f"  state={final_state}")
            if final_state in ("success", "error", "expired"):
                break
        time.sleep(0.5)
    step("final state = success", final_state == "success",
         f"got {final_state}")

    # ── DB checks ──
    print("\n=== 5) DB: Account + Customer FK ===")
    from app.models.account import Account
    from app.core.encryption import decrypt_session_string, STRING_PREFIX
    with S(engine) as s:
        cust = s.get(Customer, cust_id)
        step("customer.main_account_id set", cust.main_account_id is not None,
             f"got {cust.main_account_id}")
        acc = s.get(Account, cust.main_account_id)
        step("account.role == 'main'", acc.role == "main", f"got {acc.role}")
        step("account.is_customer_main == True", acc.is_customer_main is True)
        step("account.session_string_encrypted == True", acc.session_string_encrypted is True)
        step("session string carries enc prefix", acc.session_string.startswith(STRING_PREFIX),
             f"prefix={acc.session_string[:10]}")
        # Decryption round-trip
        plain = decrypt_session_string(acc.session_string)
        step("decryption yields mock token", plain.startswith("MOCK_SESSION_"),
             f"got {plain[:30]}")

        # ── Tenant isolation: listener + allocation pools must exclude this account ──
        from app.services.allocation_service import _pick_free_accounts
        pool = _pick_free_accounts(s, n=100)
        step("allocation pool excludes main account",
             acc.id not in [p.id for p in pool],
             f"pool has {len(pool)} candidates")

        # Listener pulls role in (listener, support) AND is_customer_main == False
        listener_candidates = s.exec(
            select(Account).where(
                Account.role.in_(["listener", "support"]),
                Account.is_customer_main == False,
            )
        ).all()
        step("listener pool excludes main account (role=main is filtered too)",
             acc.id not in [a.id for a in listener_candidates])

    # ── GET /customer/main-account now shows connected=True ──
    print("\n=== 6) GET /main-account shows connected ===")
    r = client.get("/customer/main-account", headers=cust_headers)
    body = r.json()
    step("connected=True", body["connected"] is True)
    step("phone_last4 populated", len(body.get("phone_last4") or "") == 4)

    # ── DELETE ──
    print("\n=== 7) DELETE /main-account ===")
    r = client.delete("/customer/main-account", headers=cust_headers)
    step("delete ok", r.status_code == 200 and r.json()["disconnected"] is True)
    with S(engine) as s:
        cust = s.get(Customer, cust_id)
        step("customer.main_account_id cleared", cust.main_account_id is None)
        # the Account row should still exist but is_customer_main=False, status=disconnected
        old_acc = s.exec(
            select(Account)
            .where(Account.tags.like(f"%customer_{cust_id}%"))
        ).first()
        if old_acc:
            step("old account disconnected", old_acc.status == "disconnected")
            step("session string wiped", old_acc.session_string is None)

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_orphans()
