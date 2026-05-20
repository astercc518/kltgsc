"""Epic 2.5 smoke test — billing automation tasks + NowPayments webhook.

What we verify (without waiting for Celery beat):
  1. expire_pending_invoices flips overdue pending invoices to 'expired'
  2. sweep_expired_subscriptions expires active subs past period_end
     and suspends the customer (if no newer active sub exists)
  3. send_renewal_reminders finds subs ending within 7 days (broadcasts no-op
     if no WS listeners, but the count is correct)
  4. NowPayments webhook accepts a correctly-signed payload and auto-
     activates the invoice → subscription. Bad signatures are rejected.

We talk to the DB directly to set up the "past expiry" scenarios so we don't
have to actually wait minutes.

Run:
    docker exec tgsc-backend-1 python3 /app/smoke_billing_automation.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sys
import time
from datetime import datetime, timedelta

OK, FAIL = "PASS", "FAIL"

# Module-level orphan registry — flushed by cleanup_orphans() in __main__ finally,
# so even step() -> sys.exit(1) won't leak Customer/Invoice/Subscription rows.
ORPHANS = {"customers": []}


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def cleanup_orphans():
    try:
        from app.core.db import engine
        from app.models.customer import Customer
        from app.models.subscription import Invoice, Subscription
        from sqlmodel import Session as S, select
        with S(engine) as s:
            for cid in ORPHANS["customers"]:
                for inv in s.exec(select(Invoice).where(Invoice.customer_id == cid)).all():
                    s.delete(inv)
                for sub in s.exec(select(Subscription).where(Subscription.customer_id == cid)).all():
                    s.delete(sub)
                c = s.get(Customer, cid)
                if c: s.delete(c)
            s.commit()
        if ORPHANS["customers"]:
            print(f"  [cleanup] removed {len(ORPHANS['customers'])} customers + their invoices/subs")
    except Exception as e:
        print(f"  [cleanup] WARNING: {e}")


def main():
    # imports here so the module loads in either uvicorn or beat workers
    from sqlmodel import Session, select
    from app.core.db import engine
    from app.core.config import settings
    from app.models.customer import (
        Customer, STATUS_ACTIVE, STATUS_PENDING, STATUS_SUSPENDED,
    )
    from app.models.subscription import (
        Invoice, INV_EXPIRED, INV_PAID, INV_PENDING,
        Subscription, SUB_ACTIVE, SUB_EXPIRED, SUB_PENDING,
    )
    from app.core import security
    from app.tasks.billing_tasks import (
        expire_pending_invoices,
        sweep_expired_subscriptions,
        send_renewal_reminders,
    )

    print("=== 1) Seed a fresh test customer with multiple invoices ===")
    with Session(engine) as s:
        cust = Customer(
            email=f"auto-{secrets.token_hex(3)}@tg1.ai",
            hashed_password=security.get_password_hash("Test1234!"),
            name="Auto Test",
            industry="crypto",
            status=STATUS_PENDING,
        )
        s.add(cust)
        s.commit()
        s.refresh(cust)
        ORPHANS["customers"].append(cust.id)

        # Invoice A: created 1h ago, expired (should be flipped by task)
        inv_a = Invoice(
            customer_id=cust.id,
            plan="starter",
            amount_usd=199.0,
            amount_crypto=199.42,
            currency="USDT",
            network="TRC20",
            payment_address="TPlaceholder",
            status=INV_PENDING,
            description="auto-test A",
            expires_at=datetime.utcnow() - timedelta(minutes=10),
        )
        # Invoice B: still in the future (should be left alone)
        inv_b = Invoice(
            customer_id=cust.id,
            plan="growth",
            amount_usd=299.0,
            amount_crypto=299.42,
            currency="USDT",
            network="TRC20",
            payment_address="TPlaceholder",
            status=INV_PENDING,
            description="auto-test B (future)",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        s.add(inv_a); s.add(inv_b)
        s.commit(); s.refresh(inv_a); s.refresh(inv_b)
        cust_id = cust.id
        inv_a_id, inv_b_id = inv_a.id, inv_b.id
    step("seeded customer + 2 invoices", True,
         f"customer={cust_id} expired_invoice={inv_a_id} future={inv_b_id}")

    print("\n=== 2) Run expire_pending_invoices ===")
    result = expire_pending_invoices()
    step("task returned dict", isinstance(result, dict))
    print(f"  result = {result}")
    step("expired >= 1", result["expired"] >= 1)

    with Session(engine) as s:
        a = s.get(Invoice, inv_a_id)
        b = s.get(Invoice, inv_b_id)
        step("invoice A flipped to expired", a.status == INV_EXPIRED,
             f"status={a.status}")
        step("invoice B still pending", b.status == INV_PENDING,
             f"status={b.status}")

    print("\n=== 3) Seed an active subscription with period_end in the past ===")
    with Session(engine) as s:
        cust = s.get(Customer, cust_id)
        cust.status = STATUS_ACTIVE
        cust.plan = "growth"
        cust.subscription_status = SUB_ACTIVE
        cust.current_period_end = datetime.utcnow() - timedelta(hours=2)
        s.add(cust)

        sub = Subscription(
            customer_id=cust_id,
            plan="growth",
            status=SUB_ACTIVE,
            period_start=datetime.utcnow() - timedelta(days=35),
            period_end=datetime.utcnow() - timedelta(hours=2),
            activated_at=datetime.utcnow() - timedelta(days=35),
        )
        s.add(sub)
        s.commit(); s.refresh(sub)
        expired_sub_id = sub.id
    step("seeded expired-but-still-active subscription", True,
         f"sub_id={expired_sub_id}")

    print("\n=== 4) Run sweep_expired_subscriptions ===")
    result = sweep_expired_subscriptions()
    print(f"  result = {result}")
    step("at least 1 sub expired", result["expired_subs"] >= 1)
    step("at least 1 customer suspended", result["suspended_customers"] >= 1)

    with Session(engine) as s:
        sub = s.get(Subscription, expired_sub_id)
        cust = s.get(Customer, cust_id)
        step("sub flipped to expired", sub.status == SUB_EXPIRED, f"status={sub.status}")
        step("customer suspended", cust.status == STATUS_SUSPENDED,
             f"status={cust.status}")

    print("\n=== 5) Renewal reminder finds subs ending soon ===")
    # Seed another customer with sub ending in 3 days
    with Session(engine) as s:
        c2 = Customer(
            email=f"renew-{secrets.token_hex(3)}@tg1.ai",
            hashed_password=security.get_password_hash("Test1234!"),
            industry="crypto",
            status=STATUS_ACTIVE,
            plan="starter",
            subscription_status=SUB_ACTIVE,
        )
        s.add(c2); s.commit(); s.refresh(c2)
        ORPHANS["customers"].append(c2.id)
        sub2 = Subscription(
            customer_id=c2.id,
            plan="starter",
            status=SUB_ACTIVE,
            period_start=datetime.utcnow() - timedelta(days=27),
            period_end=datetime.utcnow() + timedelta(days=3),
            activated_at=datetime.utcnow() - timedelta(days=27),
        )
        s.add(sub2); s.commit()
        c2_id = c2.id
    result = send_renewal_reminders(warn_days=7)
    print(f"  result = {result}")
    step("renewal reminder counted at least 1", result["reminded"] >= 1)

    print("\n=== 6) NowPayments webhook — signature verification ===")
    import httpx
    BASE = "http://localhost:8000/api/v1"

    # Make a fresh pending invoice to activate via webhook
    with Session(engine) as s:
        c3 = Customer(
            email=f"wh-{secrets.token_hex(3)}@tg1.ai",
            hashed_password=security.get_password_hash("Test1234!"),
            industry="ecommerce",
            status=STATUS_PENDING,
        )
        s.add(c3); s.commit(); s.refresh(c3)
        ORPHANS["customers"].append(c3.id)
        wh_sub = Subscription(
            customer_id=c3.id, plan="starter", status=SUB_PENDING,
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow() + timedelta(days=30),
        )
        s.add(wh_sub); s.commit(); s.refresh(wh_sub)
        wh_inv = Invoice(
            customer_id=c3.id, subscription_id=wh_sub.id,
            plan="starter",
            amount_usd=199.0, amount_crypto=199.55,
            currency="USDT", network="TRC20",
            payment_address="TPlaceholder",
            status=INV_PENDING,
            description="webhook auto-test",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        s.add(wh_inv); s.commit(); s.refresh(wh_inv)
        wh_inv_id = wh_inv.id
        wh_c3_id = c3.id

    # ── Bad signature path ──
    client = httpx.Client(base_url=BASE, timeout=30)
    body = {
        "payment_id": 99999,
        "payment_status": "finished",
        "order_id": f"tg1-invoice-{wh_inv_id}",
        "payin_hash": "0xnowpaymentstestpaytx",
    }
    raw = json.dumps(body, separators=(",", ":"))
    bad_sig = "0" * 128

    # Need a configured secret for this path to make sense; if unset, the
    # endpoint returns 503 which we should test too.
    if not settings.NOWPAYMENTS_IPN_SECRET:
        r = client.post("/webhooks/nowpayments",
                        content=raw,
                        headers={"x-nowpayments-sig": bad_sig,
                                 "Content-Type": "application/json"})
        step("kill-switch: 503 when secret unset", r.status_code == 503,
             f"HTTP {r.status_code}: {r.text[:160]}")
        print("  (NOWPAYMENTS_IPN_SECRET unset — skipping signed-path test)")
    else:
        r = client.post("/webhooks/nowpayments",
                        content=raw,
                        headers={"x-nowpayments-sig": bad_sig,
                                 "Content-Type": "application/json"})
        step("bad signature -> 403", r.status_code == 403, f"HTTP {r.status_code}")

        # ── Good signature path ──
        canonical = json.dumps(body, separators=(",", ":"), sort_keys=True)
        good_sig = hmac.new(
            settings.NOWPAYMENTS_IPN_SECRET.encode(),
            canonical.encode(), hashlib.sha512,
        ).hexdigest()
        r = client.post("/webhooks/nowpayments",
                        content=canonical,
                        headers={"x-nowpayments-sig": good_sig,
                                 "Content-Type": "application/json"})
        step("good signature -> 200", r.status_code == 200,
             f"HTTP {r.status_code}: {r.text[:200]}")
        body_out = r.json()
        step("status=activated", body_out.get("status") == "activated",
             f"got {body_out}")

        with Session(engine) as s:
            inv = s.get(Invoice, wh_inv_id)
            cust = s.get(Customer, wh_c3_id)
            step("invoice now paid", inv.status == INV_PAID)
            step("customer now active", cust.status == STATUS_ACTIVE)

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Always runs (even on sys.exit) so partial smokes never leave orphans.
        cleanup_orphans()
