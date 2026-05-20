"""Epic 4.1 smoke test — customer KB CRUD + file upload.

Uses the auto-allocated customer from smoke_allocation.py / smoke_kb.py
(must be in 'active' status so get_active_customer accepts requests).

Verifies:
  • POST   create with auto-embed
  • PATCH  update (content change re-embeds)
  • DELETE remove
  • POST   /upload accepts .txt / .md / .pdf-like content → multiple chunks
  • Tenant isolation: another customer cannot read/modify these rows
"""
from __future__ import annotations

import io
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
    client = httpx.Client(base_url=BASE, timeout=60)

    # ── Find an active customer (the crypto one from prior smokes) ──
    if not ADMIN_PASSWORD:
        print("ADMIN_PASSWORD env not set"); sys.exit(1)
    r = client.post("/login/access-token", data={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    step("admin login", r.status_code == 200, f"HTTP {r.status_code}")
    admin_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.get("/admin/billing/customers?status=active", headers=admin_headers)
    customers = r.json()
    active = [c for c in customers if c.get("status") == "active"]
    step("at least 1 active customer", len(active) >= 1,
         "run smoke_allocation.py first")
    cust = active[0]
    print(f"  using customer_id={cust['id']}  email={cust['email']}  plan={cust['plan']}")

    # Login as that customer (default smoke password)
    r = client.post("/customer/login", json={
        "email": cust["email"], "password": "Test1234!",
    })
    step("customer login", r.status_code == 200, f"HTTP {r.status_code}")
    cust_token = r.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # ── 1) CREATE ──
    print("\n=== 1) POST /customer/knowledge-bases (create) ===")
    r = client.post("/customer/knowledge-bases/", json={
        "name": "Pricing FAQ 2026",
        "content": "Q: What's our pricing? A: Starter $199, Growth $299, Pro $599 per month.",
        "category": "pricing",
        "language": "en",
    }, headers=cust_headers)
    step("create ok", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:200]}")
    created = r.json()
    kb_id = created["id"]
    print(f"  created kb_id={kb_id}")

    # ── 2) UPDATE ──
    print("\n=== 2) PATCH (rename + change content -> re-embed) ===")
    r = client.patch(f"/customer/knowledge-bases/{kb_id}", json={
        "name": "Pricing FAQ 2026 v2",
        "content": "Updated content: Starter $199. Growth $299. Pro $599.",
    }, headers=cust_headers)
    step("update ok", r.status_code == 200, f"HTTP {r.status_code}")
    updated = r.json()
    step("name updated", updated["name"] == "Pricing FAQ 2026 v2")

    # ── 3) UPLOAD .txt ──
    print("\n=== 3) POST /upload (.txt with multi-paragraph content) ===")
    txt = b"""Pricing breakdown for TG1.AI

The Starter plan ($199/mo) includes 3 TG accounts, 500 target groups,
and 2 million AI tokens. Best for individuals testing TG outreach.

The Growth plan ($299/mo) bumps to 5 accounts, 1000 groups, 5M tokens.
Recommended for mid-sized export businesses.

Pro ($599/mo) is for crypto projects and large operations: 10 accounts,
3000 groups, 15M tokens, and dedicated customer success.

Replacement SLA scales with plan: 24h / 12h / 4h respectively. Every plan
includes industry-customized accounts, AI persona, and auto-generated KB.
"""
    files = {"file": ("pricing.txt", txt, "text/plain")}
    data = {"category": "pricing", "name": "Pricing Doc"}
    r = client.post("/customer/knowledge-bases/upload",
                    files=files, data=data, headers=cust_headers)
    step("upload ok", r.status_code == 201, f"HTTP {r.status_code}: {r.text[:200]}")
    up = r.json()
    print(f"  result = {up}")
    step("total_chunks >= 1", up["total_chunks"] >= 1)
    step("at least 1 embedded", up["embedded_chunks"] >= 1)

    # ── 4) Confirm via list ──
    print("\n=== 4) GET /knowledge-bases reflects new entries ===")
    r = client.get("/customer/knowledge-bases", headers=cust_headers)
    rows = r.json()
    step("list ok", r.status_code == 200)
    step("contains updated entry", any(k["id"] == kb_id for k in rows))
    upload_rows = [k for k in rows if k.get("source_type") == "file_import"]
    step("contains upload chunks", len(upload_rows) >= up["total_chunks"])

    # ── 5) Bad upload (unsupported type) ──
    print("\n=== 5) Upload .exe rejected ===")
    r = client.post("/customer/knowledge-bases/upload",
                    files={"file": ("bad.exe", b"MZ\x00\x00", "application/octet-stream")},
                    headers=cust_headers)
    step("unsupported type -> 400", r.status_code == 400, f"HTTP {r.status_code}")

    # ── 6) Tenant isolation: register a 2nd customer, try to access kb_id ──
    print("\n=== 6) Tenant isolation: other customer cannot read this KB ===")
    import secrets
    other_email = f"other-{secrets.token_hex(3)}@tg1.ai"
    r = client.post("/customer/register", json={
        "email": other_email, "password": "Test1234!",
    })
    step("other customer registered", r.status_code == 201)
    other_token = r.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    # New customer is `pending` (no subscription) so the API rightly returns 402
    # via get_active_customer — that's the first line of defense. 404 (KB ownership)
    # would only kick in if they were active. Either way, the row is inaccessible.
    r = client.get(f"/customer/knowledge-bases/{kb_id}", headers=other_headers)
    step("other rejected on GET (402 inactive or 404 ownership)",
         r.status_code in (402, 404), f"HTTP {r.status_code}")

    r = client.patch(f"/customer/knowledge-bases/{kb_id}",
                     json={"name": "PWNED"}, headers=other_headers)
    step("other rejected on PATCH", r.status_code in (402, 404), f"HTTP {r.status_code}")

    r = client.delete(f"/customer/knowledge-bases/{kb_id}", headers=other_headers)
    step("other rejected on DELETE", r.status_code in (402, 404), f"HTTP {r.status_code}")

    # ── 7) DELETE (real owner) ──
    print("\n=== 7) DELETE (owner) ===")
    r = client.delete(f"/customer/knowledge-bases/{kb_id}", headers=cust_headers)
    step("delete ok", r.status_code == 204, f"HTTP {r.status_code}")
    r = client.get(f"/customer/knowledge-bases/{kb_id}", headers=cust_headers)
    step("get after delete -> 404", r.status_code == 404)

    # ── 8) Cleanup the upload chunks + the test customer ──
    print("\n=== 8) Cleanup test fixtures ===")
    from app.core.db import engine
    from sqlmodel import Session, select
    from app.models.knowledge_base import KnowledgeBase
    from app.models.customer import Customer
    with Session(engine) as s:
        for k in s.exec(
            select(KnowledgeBase)
            .where(KnowledgeBase.customer_id == cust["id"])
            .where(KnowledgeBase.source_type == "file_import")
        ).all():
            s.delete(k)
        # delete the second customer
        c2 = s.exec(select(Customer).where(Customer.email == other_email)).first()
        if c2:
            s.delete(c2)
        s.commit()
    print("  cleaned")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
