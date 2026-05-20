"""Epic 5.1 smoke test — chat-history → personal KB pipeline.

Verifies the wiring without actually running a real Pyrogram scrape (that
requires a real TG number — covered separately by integration tests):

  1. kb_retrieval.retrieve_relevant_kb raises ValueError if customer_id_filter
     is omitted (P0 guard against cross-tenant leak)
  2. Tenant isolation: KB rows for customer A are not returned to customer B
  3. POST /customer/kb/import-history without a bound main account → 400
  4. POST /customer/kb/import-history with main account → 202 + task IDs +
     ScrapingTask DB row created with the right config payload
  5. GET /customer/kb/import-history/{id}/status returns DB-side state
  6. Cross-customer ownership check: customer B cannot poll customer A's task

Run:
    docker exec -e MOCK_QR_AUTOACCEPT=1 tgsc-backend-1 python3 /app/smoke_epic5_kb_import.py
"""
from __future__ import annotations

import asyncio
import json
import secrets
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

ORPHANS = {"customers": [], "accounts": [], "knowledge_bases": [], "scraping_tasks": []}


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def cleanup_orphans():
    """Always-runs cleanup. ORPHANS["customers"] entries also flush any
    Accounts / KB rows owned by that customer (catch-all for service-side
    inserts like QR-login account creation)."""
    try:
        from app.core.db import engine
        from app.models.account import Account
        from app.models.customer import Customer
        from app.models.knowledge_base import KnowledgeBase
        from app.models.scraping_task import ScrapingTask
        from sqlmodel import Session as S, select
        with S(engine) as s:
            for kbid in ORPHANS["knowledge_bases"]:
                k = s.get(KnowledgeBase, kbid)
                if k: s.delete(k)
            for cid in ORPHANS["customers"]:
                for kb in s.exec(select(KnowledgeBase).where(KnowledgeBase.customer_id == cid)).all():
                    s.delete(kb)
                for acc in s.exec(select(Account).where(Account.customer_id == cid)).all():
                    s.delete(acc)
                c = s.get(Customer, cid)
                if c: s.delete(c)
            for stid in ORPHANS["scraping_tasks"]:
                st = s.get(ScrapingTask, stid)
                if st: s.delete(st)
            for aid in ORPHANS["accounts"]:
                a = s.get(Account, aid)
                if a: s.delete(a)
            s.commit()
        total = sum(len(v) for v in ORPHANS.values())
        if total:
            print(f"  [cleanup] flushed {total} explicit fixture rows + cascade")
    except Exception as e:
        print(f"  [cleanup] WARNING: {e}")


def _make_active_customer(industry="crypto"):
    from app.core.db import engine
    from app.core import security
    from app.models.customer import Customer, STATUS_ACTIVE, PLAN_QUOTA, PLAN_GROWTH
    from sqlmodel import Session as S
    email = f"kb51-{secrets.token_hex(3)}@tg1.ai"
    with S(engine) as s:
        c = Customer(
            email=email,
            hashed_password=security.get_password_hash("Test1234!"),
            industry=industry,
            status=STATUS_ACTIVE, plan=PLAN_GROWTH,
            subscription_status="active",
            account_quota=PLAN_QUOTA[PLAN_GROWTH]["account"],
            group_quota=PLAN_QUOTA[PLAN_GROWTH]["group"],
            token_quota=PLAN_QUOTA[PLAN_GROWTH]["token"],
        )
        s.add(c); s.commit(); s.refresh(c)
        ORPHANS["customers"].append(c.id)
        return c.id, email


def main():
    client = httpx.Client(base_url=BASE, timeout=30)

    # ── 1) P0 guard: retrieve_relevant_kb refuses unscoped calls ──
    print("=== 1) retrieve_relevant_kb requires customer_id_filter ===")
    from app.core.db import engine
    from sqlmodel import Session
    from app.services.kb_retrieval import retrieve_relevant_kb
    with Session(engine) as s:
        try:
            asyncio.run(retrieve_relevant_kb(s, "anything", top_k=1))
            step("raises ValueError when filter omitted", False, "should have raised")
        except ValueError as e:
            step("raises ValueError when filter omitted", True, str(e)[:80])
        # Passing None (explicit, for admin) is allowed
        try:
            asyncio.run(retrieve_relevant_kb(s, "ignored", top_k=1, customer_id_filter=None))
            step("explicit None passes for admin scope", True)
        except Exception as e:
            step("explicit None passes for admin scope", False, repr(e))

    # ── 2) Tenant isolation E2E ──
    print("\n=== 2) Tenant isolation: KB of customer A not visible to customer B ===")
    cid_a, email_a = _make_active_customer()
    cid_b, email_b = _make_active_customer()

    from app.models.knowledge_base import KnowledgeBase
    with Session(engine) as s:
        kb_a = KnowledgeBase(
            name="A-secret-pricing",
            content="Customer A confidential: USDT discount up to 30% for whales.",
            source_type="manual",
            customer_id=cid_a,
        )
        kb_b = KnowledgeBase(
            name="B-secret-pricing",
            content="Customer B confidential: BTC-only invoices for OTC desks.",
            source_type="manual",
            customer_id=cid_b,
        )
        s.add(kb_a); s.add(kb_b); s.commit()
        s.refresh(kb_a); s.refresh(kb_b)

    # As customer A, search for B's content — should NOT match
    with Session(engine) as s:
        hits = asyncio.run(retrieve_relevant_kb(
            s, "BTC OTC desk", top_k=5, customer_id_filter=cid_a,
        ))
        leaked = [h for h in hits if h.id == kb_b.id]
        step("A's retrieval excludes B's KB", len(leaked) == 0,
             f"hits={[h.id for h in hits]}")

        hits = asyncio.run(retrieve_relevant_kb(
            s, "USDT discount", top_k=5, customer_id_filter=cid_b,
        ))
        leaked = [h for h in hits if h.id == kb_a.id]
        step("B's retrieval excludes A's KB", len(leaked) == 0,
             f"hits={[h.id for h in hits]}")

    # ── 3) /import-history with no main account → 400 ──
    print("\n=== 3) /import-history without main account -> 400 ===")
    r = client.post("/customer/login", json={"email": email_a, "password": "Test1234!"})
    headers_a = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/customer/knowledge-bases/import-history",
                    json={}, headers=headers_a)
    step("no main account -> 400", r.status_code == 400, f"HTTP {r.status_code}")

    # ── 4) Bind a (mock) main account, then trigger import ──
    print("\n=== 4) Bind main account (mock) then trigger import ===")
    r = client.post("/customer/main-account/qr/start", headers=headers_a)
    step("QR start ok", r.status_code == 201)
    token = r.json()["token"]
    # poll until success
    import time
    final = None
    for _ in range(20):
        r = client.get(f"/customer/main-account/qr/status?token={token}", headers=headers_a)
        if r.json().get("state") == "success":
            final = "success"; break
        time.sleep(0.5)
    step("QR success", final == "success")

    r = client.post(
        "/customer/knowledge-bases/import-history",
        json={
            "since": "2026-05-01T00:00:00",
            "dialog_types": ["private", "supergroup"],
            "max_messages_per_chat": 50,
            "cost_cap_usd": 2.0,
        },
        headers=headers_a,
    )
    step("import accepted", r.status_code == 202, f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    print(f"  scrape_task_id={body['scrape_task_id'][:8]}  "
          f"scraping_task_id={body['scraping_task_id']}  "
          f"extract_task_id={body['extract_task_id'][:8]}")
    step("returns scraping_task_id", body["scraping_task_id"] > 0)

    # ── 5) ScrapingTask row created with the right config ──
    print("\n=== 5) DB ScrapingTask row has our config ===")
    from app.models.scraping_task import ScrapingTask
    with Session(engine) as s:
        st = s.get(ScrapingTask, body["scraping_task_id"])
        step("row exists", st is not None)
        step("task_type=customer_kb_import", st.task_type == "customer_kb_import")
        cfg = json.loads(st.result_json).get("config", {})
        step("customer_id in config", cfg.get("customer_id") == cid_a)
        step("max_messages 50", cfg.get("max_messages_per_chat") == 50)
        step("dialog_types preserved", cfg.get("dialog_types") == ["private", "supergroup"])

    # ── 6) Status endpoint ──
    print("\n=== 6) GET /import-history/{id}/status ===")
    r = client.get(f"/customer/knowledge-bases/import-history/{body['scraping_task_id']}/status",
                   headers=headers_a)
    step("status ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:160]}")
    print(f"  state={r.json()['status']}  kb_total={r.json().get('kb_extracted_total')}")

    # ── 7) Cross-customer ownership: B can't poll A's task ──
    print("\n=== 7) Cross-customer poll rejected ===")
    r = client.post("/customer/login", json={"email": email_b, "password": "Test1234!"})
    headers_b = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get(f"/customer/knowledge-bases/import-history/{body['scraping_task_id']}/status",
                   headers=headers_b)
    step("B cannot poll A's task", r.status_code == 404, f"HTTP {r.status_code}")

    # Register scraping_task for cleanup (customers + KB cascade via ORPHANS["customers"])
    if body.get("scraping_task_id"):
        ORPHANS["scraping_tasks"].append(body["scraping_task_id"])

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_orphans()
