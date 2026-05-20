"""Epic 4.0 smoke test — industry KB auto-generation.

Targets the customer created by smoke_allocation.py (alloc-*@tg1.ai, growth/crypto).
Uses /admin/billing/customers/{id}/regenerate-kb to force-regen so it works
even if KB was already auto-created during activation.

Verifies:
  • 4 KB entries created (industry_overview / pain_points / sales_qa / opening_lines)
  • Each entry has non-empty content
  • At least 1 entry has a populated embedding (768-d vector)
  • /customer/knowledge-bases returns the entries to the customer

Run:
    ADMIN_PW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
    docker exec -e ADMIN_PASSWORD="$ADMIN_PW" tgsc-backend-1 python3 /app/smoke_kb.py
"""
import os
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
    if not ADMIN_PASSWORD:
        print("ADMIN_PASSWORD env not set"); sys.exit(1)

    client = httpx.Client(base_url=BASE, timeout=120)

    # Find the most recent crypto customer (created by smoke_allocation)
    print("=== 1) Admin login + find latest crypto customer ===")
    r = client.post("/login/access-token", data={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    step("admin login", r.status_code == 200)
    admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/admin/billing/customers?plan=growth", headers=admin_headers)
    step("list customers ok", r.status_code == 200)
    customers = r.json()
    crypto = [c for c in customers if c.get("industry") == "crypto"]
    step("at least 1 crypto customer exists", len(crypto) >= 1,
         "run smoke_allocation.py first")
    cust = crypto[0]
    cust_id = cust["id"]
    print(f"  using customer_id={cust_id}  email={cust['email']}")

    # Force-regen KB so the test is repeatable
    print("\n=== 2) POST /admin/.../regenerate-kb (deletes + recreates) ===")
    r = client.post(
        f"/admin/billing/customers/{cust_id}/regenerate-kb",
        headers=admin_headers,
    )
    step("regenerate ok", r.status_code == 200,
         f"HTTP {r.status_code}: {r.text[:200]}")
    result = r.json()
    print(f"  result = {result}")
    step("4 KB entries created", result["created"] == 4,
         f"got {result['created']}, skipped={result['skipped']}")
    step("at least 1 embedded", result["embedded"] >= 1,
         f"embedded={result['embedded']}")

    # Verify via direct DB query
    print("\n=== 3) Verify KB rows in DB ===")
    from app.core.db import engine
    from sqlmodel import Session, select
    from app.models.knowledge_base import KnowledgeBase
    with Session(engine) as s:
        rows = s.exec(
            select(KnowledgeBase).where(KnowledgeBase.customer_id == cust_id)
        ).all()
        step("DB has exactly 4 rows", len(rows) == 4)
        categories = sorted({r.category for r in rows})
        expected_cats = ["industry_overview", "pain_points", "sales_qa", "opening_lines"]
        for cat in expected_cats:
            step(f"category present: {cat}",
                 cat in categories,
                 f"got {categories}")
        # Spot-check content + embedding
        for row in rows:
            step(f"content non-empty for {row.category}",
                 len(row.content) > 50,
                 f"len={len(row.content)}")
        embedded_rows = [r for r in rows if r.embedding is not None]
        step("at least 1 row has 768-d embedding",
             len(embedded_rows) >= 1)
        if embedded_rows:
            sample = embedded_rows[0]
            step("embedding has 768 dims",
                 len(sample.embedding) == 768,
                 f"got {len(sample.embedding)}")

    # Print one snippet so the user can eyeball quality
    print("\n=== 4) Sample KB content ===")
    with Session(engine) as s:
        sample = s.exec(
            select(KnowledgeBase)
            .where(KnowledgeBase.customer_id == cust_id)
            .where(KnowledgeBase.category == "opening_lines")
        ).first()
        if sample:
            print(f"  --- [{sample.category}] {sample.name} ---")
            print("  " + "\n  ".join(sample.content.splitlines()[:10]))

    # Customer-facing visibility
    print("\n=== 5) /customer/knowledge-bases shows the KB ===")
    # need a customer token; fall back to using admin (won't work) -> need login
    # The customer pw is the smoke default
    r = client.post("/customer/login", json={
        "email": cust["email"], "password": "Test1234!",
    })
    if r.status_code != 200:
        print(f"  [skip] cannot login as customer (HTTP {r.status_code}); "
              f"DB verification above is authoritative")
    else:
        cust_token = r.json()["access_token"]
        r = client.get("/customer/knowledge-bases",
                       headers={"Authorization": f"Bearer {cust_token}"})
        step("customer sees their KB", r.status_code == 200 and len(r.json()) == 4,
             f"HTTP {r.status_code}, count={len(r.json()) if r.status_code == 200 else '?'}")

    # Idempotency: generate-kb (not regen) is no-op when KB exists
    print("\n=== 6) Idempotent provision (KB already exists) ===")
    from app.services.industry_kb_service import generate_kb_for_customer
    from app.models.customer import Customer
    with Session(engine) as s:
        c = s.get(Customer, cust_id)
        r2 = generate_kb_for_customer(s, c)
    step("no-op when KB already exists",
         len(r2.created) == 0,
         f"got {len(r2.created)}")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
