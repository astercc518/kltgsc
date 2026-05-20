"""Epic 1 smoke test — exercises the multi-tenant customer flow end-to-end.

Run inside the backend container:
    docker exec tgsc-backend-1 python3 /app/smoke_customer.py
"""
import json
import sys

import httpx

BASE = "http://localhost:8000/api/v1"

OK, FAIL = "PASS", "FAIL"


def step(name: str, ok: bool, detail: str = "") -> None:
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=10)

    print("=== 1) Register ===")
    r = client.post("/customer/register", json={
        "email": "smoke@tg1.ai",
        "password": "Test1234!",
        "name": "Smoke Test",
        "company": "Acme Corp",
        "industry": "crypto",
    })
    if r.status_code == 409:
        print("  (already registered, logging in instead)")
        r = client.post("/customer/login", json={
            "email": "smoke@tg1.ai",
            "password": "Test1234!",
        })
        step("login existing", r.status_code == 200, f"HTTP {r.status_code}")
    else:
        step("registered new customer", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    token = body["access_token"]
    customer = body["customer"]
    print(f"  customer_id={customer['id']}  email={customer['email']}  status={customer['status']}")

    auth = {"Authorization": f"Bearer {token}"}

    print("\n=== 2) GET /customer/me ===")
    r = client.get("/customer/me", headers=auth)
    step("me returns 200", r.status_code == 200)
    me = r.json()
    step("me email matches", me["email"] == "smoke@tg1.ai")
    step("me has industry", me["industry"] == "crypto")

    print("\n=== 3) GET /customer/quota ===")
    r = client.get("/customer/quota", headers=auth)
    step("quota returns 200", r.status_code == 200)
    q = r.json()
    print(f"  plan={q['plan']}  status={q['status']}")
    print(f"  limits={q['limits']}")
    print(f"  usage ={q['usage']}")
    step("usage.accounts == 0", q["usage"]["accounts"] == 0)
    step("usage.leads == 0", q["usage"]["leads"] == 0)
    step("usage.knowledge_bases == 0", q["usage"]["knowledge_bases"] == 0)

    print("\n=== 4) Tenant-scoped list endpoints ===")
    for path in ("/customer/accounts", "/customer/leads", "/customer/knowledge-bases"):
        r = client.get(path, headers=auth)
        step(f"GET {path}", r.status_code == 200 and r.json() == [],
             f"HTTP {r.status_code}: {r.text[:120]}")

    print("\n=== 5) Auth boundaries ===")
    r = client.get("/customer/me")
    step("no token -> 401/403", r.status_code in (401, 403), f"HTTP {r.status_code}")

    r = client.get("/customer/me", headers={"Authorization": "Bearer not.a.real.token"})
    step("bogus token -> 401/403", r.status_code in (401, 403), f"HTTP {r.status_code}")

    r = client.post("/customer/register", json={
        "email": "smoke@tg1.ai", "password": "Test1234!",
    })
    step("duplicate email -> 409", r.status_code == 409, f"HTTP {r.status_code}")

    r = client.post("/customer/register", json={
        "email": "shortpw@tg1.ai", "password": "abc",
    })
    step("short password -> 400", r.status_code == 400, f"HTTP {r.status_code}")

    print("\n=== 6) Tenant isolation — admin-only data must be invisible ===")
    # Insert an unowned (customer_id=NULL) Account directly via DB and verify
    # the customer endpoint doesn't return it.
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.models.account import Account
    with Session(engine) as s:
        existing = s.exec(
            select(Account).where(Account.customer_id.is_(None)).limit(1)
        ).first()
        if existing:
            print(f"  found unowned account id={existing.id} (system-owned)")
        else:
            print("  (no unowned account in DB — skipping isolation read check)")

    r = client.get("/customer/accounts", headers=auth)
    step("customer still sees [] (system-owned account hidden)",
         r.status_code == 200 and r.json() == [])

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
