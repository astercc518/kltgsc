"""Epic 5.2 smoke test — main-account notification + handover timeout.

Verifies via direct task invocation (no Celery beat wait needed):

  1. notify_high_intent task respects opt-out (customer.notify_main_account=False)
  2. notify_high_intent task is idempotent (second run no-ops via main_account_notified_at)
  3. PATCH /customer/settings validates handover_group_link format + timeout range
  4. send_handover_link_if_unclaimed task — TIMING & RACE behavior:
     • before deadline → no-op
     • after deadline + claimed → no-op (race-safe)
     • after deadline + unclaimed + no link → system_alert, no DM
     • after deadline + unclaimed + link configured → DM sent, link_sent_at written
     • retry / second invocation → idempotent no-op
  5. Self-DM guard: prospect TG user == customer's main account → no-op

Run:
    docker exec -e MOCK_QR_AUTOACCEPT=1 tgsc-backend-1 python3 /app/smoke_epic5_handover.py
"""
from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

# Module-level orphans registry — populated as the smoke creates fixtures.
# A try/finally in __main__ flushes these even if step() calls sys.exit(1).
ORPHANS = {
    "customers": [], "accounts": [], "leads": [],
    "invoices": [], "subscriptions": [],
    "scraping_tasks": [], "knowledge_bases": [],
}


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def cleanup_orphans():
    """Best-effort delete of every fixture id this script seeded.

    Runs in __main__'s finally even on sys.exit, so a failed step never
    leaks Account / Customer rows into the prod DB (see Epic 5.2 smoke
    incident 2026-05-18).
    """
    try:
        from app.core.db import engine
        from app.models.account import Account
        from app.models.customer import Customer
        from app.models.knowledge_base import KnowledgeBase
        from app.models.lead import Lead
        from app.models.scraping_task import ScrapingTask
        from app.models.subscription import Invoice, Subscription
        from sqlmodel import Session as S

        with S(engine) as s:
            for kbid in ORPHANS["knowledge_bases"]:
                k = s.get(KnowledgeBase, kbid)
                if k: s.delete(k)
            for lid in ORPHANS["leads"]:
                l = s.get(Lead, lid)
                if l: s.delete(l)
            for inv_id in ORPHANS["invoices"]:
                i = s.get(Invoice, inv_id)
                if i: s.delete(i)
            for sid in ORPHANS["subscriptions"]:
                sub = s.get(Subscription, sid)
                if sub: s.delete(sub)
            for stid in ORPHANS["scraping_tasks"]:
                st = s.get(ScrapingTask, stid)
                if st: s.delete(st)
            for aid in ORPHANS["accounts"]:
                a = s.get(Account, aid)
                if a: s.delete(a)
            for cid in ORPHANS["customers"]:
                c = s.get(Customer, cid)
                if c: s.delete(c)
            s.commit()
        total = sum(len(v) for v in ORPHANS.values())
        if total:
            print(f"  [cleanup] removed {total} fixture rows: "
                  f"{ {k: len(v) for k, v in ORPHANS.items() if v} }")
    except Exception as e:
        print(f"  [cleanup] WARNING (orphans may remain): {e}")


def main():
    client = httpx.Client(base_url=BASE, timeout=30)

    from app.core.db import engine
    from app.core import security
    from app.models.customer import (
        Customer, STATUS_ACTIVE, PLAN_QUOTA, PLAN_GROWTH,
    )
    from app.models.account import Account
    from app.models.lead import Lead
    from sqlmodel import Session as S, select

    # cleanup is handled by module-level cleanup_orphans() via __main__'s finally;
    # this main() only needs to register ids into ORPHANS as it seeds them.

    # ── 1) Seed customer + main account + AI marketing account + Lead ──
    print("=== 1) Seed customer + main account + marketing account + Lead ===")
    email = f"ho-{secrets.token_hex(3)}@tg1.ai"
    with S(engine) as s:
        c = Customer(
            email=email,
            hashed_password=security.get_password_hash("Test1234!"),
            industry="crypto",
            status=STATUS_ACTIVE, plan=PLAN_GROWTH,
            subscription_status="active",
            account_quota=PLAN_QUOTA[PLAN_GROWTH]["account"],
            group_quota=PLAN_QUOTA[PLAN_GROWTH]["group"],
            token_quota=PLAN_QUOTA[PLAN_GROWTH]["token"],
            takeover_timeout_minutes=2,        # short for the smoke
            notify_main_account=True,
        )
        s.add(c); s.commit(); s.refresh(c)
        cust_id = c.id
        ORPHANS["customers"].append(cust_id)

        main = Account(
            phone_number=f"+99{secrets.token_hex(4)}",
            session_string="MOCK_SESSION_smoke_main",
            session_string_encrypted=False,
            status="active", role="main", is_customer_main=True,
            customer_id=cust_id, tags=f"main_account,customer_{cust_id}",
        )
        marketing = Account(
            phone_number=f"+88{secrets.token_hex(4)}",
            session_string="MOCK_SESSION_smoke_marketing",
            session_string_encrypted=False,
            status="active", role="worker",
            customer_id=cust_id,
        )
        s.add(main); s.add(marketing); s.commit()
        s.refresh(main); s.refresh(marketing)
        c.main_account_id = main.id; s.add(c); s.commit()
        main_id, marketing_id = main.id, marketing.id
        ORPHANS["accounts"].extend([main_id, marketing_id])

        # ── Encrypt mock session_string properly (notifier will decrypt) ──
        from app.core.encryption import encrypt_session_string
        main.session_string = encrypt_session_string("MOCK_SESSION_smoke_main")
        main.session_string_encrypted = True
        marketing.session_string = encrypt_session_string("MOCK_SESSION_smoke_marketing")
        marketing.session_string_encrypted = True
        s.add(main); s.add(marketing); s.commit()
    step("seeded", True, f"customer={cust_id} main={main_id} marketing={marketing_id}")

    # ── 2) PATCH /customer/settings validation ──
    print("\n=== 2) PATCH /customer/settings validation ===")
    r = client.post("/customer/login", json={"email": email, "password": "Test1234!"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # bad link
    r = client.patch("/customer/settings",
                     json={"handover_group_link": "ftp://bad"}, headers=headers)
    step("bad link rejected", r.status_code == 400, f"HTTP {r.status_code}")

    # timeout out of range
    r = client.patch("/customer/settings",
                     json={"takeover_timeout_minutes": 99}, headers=headers)
    step("timeout > 30 rejected", r.status_code == 400, f"HTTP {r.status_code}")

    # valid update
    r = client.patch("/customer/settings",
                     json={
                         "handover_group_link": "https://t.me/+TestHandoverGroup",
                         "takeover_timeout_minutes": 2,
                         "notify_main_account": True,
                     }, headers=headers)
    step("valid settings ok", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:160]}")

    # ── 3) Build a high-intent Lead row directly ──
    print("\n=== 3) Seed a high-intent Lead row ===")
    with S(engine) as s:
        lead = Lead(
            account_id=marketing_id,
            telegram_user_id=secrets.randbelow(2**30),
            username="prospect_x",
            first_name="Prospect",
            status="interested",
            tags_json='["high_value", "purchase"]',
            customer_id=cust_id,
            takeover_deadline=datetime.utcnow() + timedelta(seconds=3),
        )
        s.add(lead); s.commit(); s.refresh(lead)
        lead_id = lead.id
        ORPHANS["leads"].append(lead_id)

    # ── 4) notify_high_intent — main account dispatched (in MOCK mode logs only) ──
    print("\n=== 4) notify_high_intent ===")
    from app.services.main_account_notifier import notify_high_intent
    r1 = notify_high_intent(lead_id)
    step("first invocation sent", r1.get("sent") is True, f"r1={r1}")

    # idempotent: second call no-ops
    r2 = notify_high_intent(lead_id)
    step("second invocation idempotent (already notified)",
         r2.get("sent") is False, f"r2={r2}")

    with S(engine) as s:
        lead = s.get(Lead, lead_id)
        step("main_account_notified_at written",
             lead.main_account_notified_at is not None)

    # ── 5) Customer opt-out path ──
    print("\n=== 5) Opt-out — notify is skipped when notify_main_account=False ===")
    with S(engine) as s:
        c = s.get(Customer, cust_id)
        c.notify_main_account = False
        s.add(c); s.commit()
        # seed a fresh lead to test opt-out
        lead2 = Lead(
            account_id=marketing_id,
            telegram_user_id=secrets.randbelow(2**30),
            username="prospect_y",
            status="new",
            customer_id=cust_id,
        )
        s.add(lead2); s.commit(); s.refresh(lead2)
        lead2_id = lead2.id
        ORPHANS["leads"].append(lead2_id)
    r = notify_high_intent(lead2_id)
    step("opt-out -> no send", r.get("sent") is False, f"r={r}")
    # restore
    with S(engine) as s:
        c = s.get(Customer, cust_id)
        c.notify_main_account = True
        s.add(c); s.commit()

    # ── 6) Handover task — before deadline = no-op ──
    print("\n=== 6) send_handover_link_if_unclaimed before deadline -> no-op ===")
    from app.tasks.handover_tasks import send_handover_link_if_unclaimed
    # lead's deadline was +3s; we're well before. Push it out further to be safe.
    with S(engine) as s:
        lead = s.get(Lead, lead_id)
        lead.takeover_deadline = datetime.utcnow() + timedelta(minutes=10)
        s.add(lead); s.commit()
    r = send_handover_link_if_unclaimed(lead_id)
    step("before deadline -> no send", r.get("sent") is False
         and "deadline not yet reached" in r.get("reason", ""),
         f"r={r}")

    # ── 7) Handover task — after deadline + claimed = no-op ──
    print("\n=== 7) After deadline but claimed -> no-op ===")
    with S(engine) as s:
        lead = s.get(Lead, lead_id)
        lead.takeover_deadline = datetime.utcnow() - timedelta(seconds=1)
        lead.assigned_to_user_id = 1  # any non-null
        lead.claimed_at = datetime.utcnow()
        s.add(lead); s.commit()
    r = send_handover_link_if_unclaimed(lead_id)
    step("claimed before deadline -> no send",
         r.get("sent") is False and "claimed" in r.get("reason", ""),
         f"r={r}")

    # ── 8) Handover task — after deadline + unclaimed + no link configured ──
    print("\n=== 8) Unclaimed + no link -> system_alert, no send ===")
    with S(engine) as s:
        c = s.get(Customer, cust_id)
        c.handover_group_link = None
        s.add(c); s.commit()
        # fresh unclaimed lead
        lead3 = Lead(
            account_id=marketing_id,
            telegram_user_id=secrets.randbelow(2**30),
            username="prospect_no_link",
            status="interested",
            customer_id=cust_id,
            takeover_deadline=datetime.utcnow() - timedelta(seconds=1),
        )
        s.add(lead3); s.commit(); s.refresh(lead3)
        lead3_id = lead3.id
        ORPHANS["leads"].append(lead3_id)
    r = send_handover_link_if_unclaimed(lead3_id)
    step("no link -> no send", r.get("sent") is False
         and "handover_group_link" in r.get("reason", ""),
         f"r={r}")

    # ── 9) Handover task — happy path → DM sent, idempotent on retry ──
    print("\n=== 9) Unclaimed + link configured -> DM sent + idempotent ===")
    with S(engine) as s:
        c = s.get(Customer, cust_id)
        c.handover_group_link = "https://t.me/+TestHandoverGroup"
        s.add(c); s.commit()
    r = send_handover_link_if_unclaimed(lead3_id)
    step("happy path sent",
         r.get("sent") is True and r.get("link") == "https://t.me/+TestHandoverGroup",
         f"r={r}")
    with S(engine) as s:
        lead = s.get(Lead, lead3_id)
        step("handover_link_sent_at written", lead.handover_link_sent_at is not None)

    r2 = send_handover_link_if_unclaimed(lead3_id)
    step("second invocation idempotent",
         r2.get("sent") is False and "already sent" in r2.get("reason", ""),
         f"r2={r2}")

    # ── 10) Self-DM guard ──
    print("\n=== 10) Self-DM guard: prospect == main account_id ===")
    with S(engine) as s:
        lead4 = Lead(
            account_id=main_id,  # ← deliberately set to the customer's main account
            telegram_user_id=secrets.randbelow(2**30),
            customer_id=cust_id,
            takeover_deadline=datetime.utcnow() - timedelta(seconds=1),
        )
        s.add(lead4); s.commit(); s.refresh(lead4)
        lead4_id = lead4.id
        ORPHANS["leads"].append(lead4_id)
    r = send_handover_link_if_unclaimed(lead4_id)
    step("self-DM avoided",
         r.get("sent") is False and "main account" in r.get("reason", "").lower(),
         f"r={r}")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Always run, even if step() called sys.exit(1) mid-way.
        # Prevents Account / Customer / Lead orphans from accumulating in dev DB.
        cleanup_orphans()
