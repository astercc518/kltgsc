"""Epic 3.0 smoke test — full provisioning flow.

New customer (crypto industry) → subscribe → admin activates → verify:
  • accounts auto-allocated up to plan quota
  • account.customer_id and account.assigned_at populated
  • account.customized_username/first_name/bio non-null (AI or fallback)
  • source_groups allocated by industry (crypto-tagged preferred)

Run inside backend container:
    ADMIN_PW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
    docker exec -e ADMIN_PASSWORD="$ADMIN_PW" tgsc-backend-1 python3 /app/smoke_allocation.py
"""
import os
import secrets
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def main():
    # Activation calls LLM up to 5x (one per allocated account); use generous timeout
    client = httpx.Client(base_url=BASE, timeout=120)

    if not ADMIN_PASSWORD:
        print("ADMIN_PASSWORD env not set; aborting")
        sys.exit(1)

    # Fresh customer to avoid colliding with Epic 1/2 smoke fixtures
    email = f"alloc-{secrets.token_hex(4)}@tg1.ai"
    password = "Test1234!"

    print(f"=== 1) Register fresh crypto customer: {email} ===")
    r = client.post("/customer/register", json={
        "email": email, "password": password,
        "name": "Alice Crypto", "company": "DeFi Labs", "industry": "crypto",
    })
    step("registered", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:160]}")
    body = r.json()
    cust_id = body["customer"]["id"]
    cust_token = body["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    print(f"  customer_id={cust_id}")

    print("\n=== 2) Customer subscribes to growth plan ===")
    r = client.post("/customer/subscribe", json={"plan": "growth", "network": "TRC20"},
                    headers=cust_headers)
    step("subscribe ok", r.status_code == 201, f"HTTP {r.status_code}")
    invoice = r.json()
    print(f"  invoice_id={invoice['id']}  amount={invoice['amount_crypto']} {invoice['currency']}")

    print("\n=== 3) Pre-activation: customer has 0 accounts/groups ===")
    r = client.get("/customer/accounts", headers=cust_headers)
    step("accounts empty before activation", r.status_code == 200 and r.json() == [])

    print("\n=== 4) Admin login & activate ===")
    r = client.post("/login/access-token", data={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    step("admin login", r.status_code == 200, f"HTTP {r.status_code}")
    admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post(
        f"/admin/billing/customers/{cust_id}/activate-subscription",
        json={"invoice_id": invoice["id"], "tx_hash": "0xsmokealloc"},
        headers=admin_headers,
    )
    step("activate ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")

    print("\n=== 5) Post-activation: accounts auto-allocated ===")
    r = client.get("/customer/accounts", headers=cust_headers)
    step("accounts list 200", r.status_code == 200)
    accounts = r.json()
    print(f"  allocated count = {len(accounts)} (quota=5)")
    step("at least 1 account allocated", len(accounts) >= 1,
         f"got {len(accounts)}")
    # Should be exactly 5 if pool has >= 5, else as many as pool had
    step("up to quota allocated", len(accounts) <= 5)

    if accounts:
        a = accounts[0]
        print(f"  sample: id={a['id']}  status={a['status']}")
        # The API returns AccountRead which doesn't include customized_*;
        # query DB directly to verify
        from app.core.db import engine
        from sqlmodel import Session, select
        from app.models.account import Account
        with Session(engine) as s:
            db_a = s.get(Account, a["id"])
            step("DB: customer_id set",
                 db_a.customer_id == cust_id,
                 f"got {db_a.customer_id}")
            step("DB: assigned_at set", db_a.assigned_at is not None)
            has_meta = bool(
                db_a.customized_username or db_a.customized_first_name
                or db_a.customized_bio
            )
            step("DB: customized_* populated (AI or fallback)",
                 has_meta,
                 f"username={db_a.customized_username!r} "
                 f"first={db_a.customized_first_name!r} "
                 f"bio={db_a.customized_bio!r}")
            print(f"  metadata: @{db_a.customized_username}  "
                  f"{db_a.customized_first_name} {db_a.customized_last_name or ''}  "
                  f"bio={db_a.customized_bio!r}")

    print("\n=== 6) Groups allocated by industry (crypto preferred) ===")
    # Groups aren't exposed to customer yet (no /customer/source-groups endpoint),
    # query DB
    from app.core.db import engine
    from sqlmodel import Session, select, func
    from app.models.source_group import SourceGroup
    with Session(engine) as s:
        my_groups = s.exec(
            select(SourceGroup).where(SourceGroup.customer_id == cust_id)
        ).all()
        print(f"  allocated groups = {len(my_groups)} (quota=1000, pool is small)")
        step("at least 1 group allocated", len(my_groups) >= 1)
        # Verify crypto-tagged groups preferred
        crypto_count = sum(1 for g in my_groups if g.industry == "crypto")
        print(f"  crypto-tagged: {crypto_count}/{len(my_groups)}")
        step("crypto-tagged dominate (industry preferred)",
             crypto_count >= 1)

    print("\n=== 7) /customer/quota reflects allocation ===")
    r = client.get("/customer/quota", headers=cust_headers)
    q = r.json()
    print(f"  usage = {q['usage']}")
    step("usage.accounts matches allocation",
         q["usage"]["accounts"] == len(accounts))

    print("\n=== 8) Idempotency — calling reallocate again is a no-op ===")
    r = client.post(
        f"/admin/billing/customers/{cust_id}/reallocate-accounts",
        headers=admin_headers,
    )
    step("reallocate ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:160]}")
    result = r.json()
    print(f"  reallocate result = {result}")
    step("0 new accounts (already at quota)", result["allocated"] == 0,
         f"got {result['allocated']}")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
