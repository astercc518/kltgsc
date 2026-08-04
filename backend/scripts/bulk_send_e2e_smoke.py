"""
Bulk Send end-to-end smoke (W6).

One-shot demo-day sanity check covering W1–W5:

    wallet topup → create draft batch → cost preview → variant CRUD →
    start → wait for completion → simulate inbound reply →
    verify lead in customer-side leads filter → admin metrics →
    cleanup created rows so the script is rerunnable.

Run inside the backend container:
    docker exec -w /app -e PYTHONPATH=/app tgsc-backend-1 \
        python -m scripts.bulk_send_e2e_smoke

Exit code 0 = all checks passed. Non-zero = a check failed; details printed.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

from sqlmodel import Session, select

from app.core.db import engine
from app.models.account import Account
from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_COMPLETED, TARGET_SENT, TARGET_REPLIED,
)
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.wallet import CustomerWallet, WalletTransaction
from app.services.bulk_reply_service import handle_inbound_dm


BASE = os.environ.get("SMOKE_BASE", "http://localhost:8000")
CUST_EMAIL = os.environ.get("SMOKE_CUSTOMER_EMAIL", "smoke@tg1.ai")
CUST_PASS = os.environ.get("SMOKE_CUSTOMER_PASSWORD", "Demo2026!")
ADMIN_USER = os.environ.get("SMOKE_ADMIN_USER", "admin")
ADMIN_PASS = os.environ["SMOKE_ADMIN_PASSWORD"]


PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, ok: bool, hint: str = "") -> None:
    (PASSED if ok else FAILED).append(label)
    sym = "✓" if ok else "✗"
    print(f"  [{sym}] {label}" + (f"  — {hint}" if hint and not ok else ""))


def post_json(headers: dict, path: str, body) -> tuple[int, object]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def post_form(path: str, fields: dict) -> tuple[int, object]:
    data = "&".join(f"{k}={v}" for k, v in fields.items()).encode()
    req = urllib.request.Request(BASE + path, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    r = urllib.request.urlopen(req, timeout=30)
    return r.status, json.loads(r.read())


def get(headers: dict, path: str) -> tuple[int, object]:
    req = urllib.request.Request(BASE + path, headers=headers)
    try:
        r = urllib.request.urlopen(req, timeout=15)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def delete(headers: dict, path: str) -> tuple[int, object]:
    req = urllib.request.Request(BASE + path, headers=headers, method="DELETE")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, (json.loads(r.read()) if r.length else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def main() -> int:
    print(f"\n=== Bulk Send E2E Smoke ===\n  base={BASE}  customer={CUST_EMAIL}\n")

    # ── Auth ───────────────────────────────────────────────────────────
    s, resp = post_json({"Content-Type": "application/json"},
        "/api/v1/customer/login", {"email": CUST_EMAIL, "password": CUST_PASS})
    check("customer login", s == 200 and isinstance(resp, dict) and "access_token" in resp,
          f"status={s} resp={resp}")
    if s != 200:
        return 1
    cust_tok = resp["access_token"]
    CH = {"Authorization": f"Bearer {cust_tok}", "Content-Type": "application/json"}

    s, resp = post_form("/api/v1/login/access-token",
        {"username": ADMIN_USER, "password": ADMIN_PASS})
    check("admin login", s == 200 and "access_token" in resp, f"status={s}")
    admin_tok = resp["access_token"]
    AH = {"Authorization": f"Bearer {admin_tok}"}

    # Get customer id
    s, me = get(CH, "/api/v1/customer/me")
    check("customer/me", s == 200, f"status={s}")
    customer_id = me["id"]

    # ── Topup floor: ensure wallet has enough headroom ─────────────────
    with Session(engine) as db:
        w = db.get(CustomerWallet, customer_id)
        if not w:
            w = CustomerWallet(customer_id=customer_id, balance_cents=100_00)
            db.add(w); db.commit(); db.refresh(w)
        if w.balance_cents < 1_000:
            w.balance_cents = 100_00  # $100
            w.low_balance_notified_at = None
            db.add(w); db.commit()
        balance_before = w.balance_cents
    print(f"  wallet before: ${balance_before/100:.2f}")

    # ── Cost preview ───────────────────────────────────────────────────
    s, p = post_json(CH, "/api/v1/customer/bulk/preview-cost", {"target_count": 10})
    check("preview-cost 10", s == 200 and isinstance(p, dict) and p.get("total_cost_cents", 0) > 0,
          f"status={s} body={p}")

    # ── Create draft batch ─────────────────────────────────────────────
    csv_text = "\n".join(f"301{i:06d}" for i in range(8))
    body = {
        "name": "E2E smoke batch (cleanup OK)",
        "message_template": "primary text {{name}}",
        "csv_text": csv_text,
        "variants": [f"variant {c}" for c in "abcde"],
        "min_delay_sec": 10, "max_delay_sec": 30,
    }
    s, b = post_json(CH, "/api/v1/customer/bulk/batches", body)
    check("create batch", s == 201 and isinstance(b, dict) and b.get("total_targets") == 8,
          f"status={s} body={b}")
    if s != 201:
        return _fail()
    batch_id = b["id"]
    print(f"  batch id={batch_id}  variants={len(b['variants'])}  targets={b['total_targets']}")

    # ── Variant CRUD ───────────────────────────────────────────────────
    s, nv = post_json(CH, f"/api/v1/customer/bulk/batches/{batch_id}/variants",
        {"content": "added later", "weight": 2})
    check("add variant", s == 201, f"status={s}")
    variant_id = nv["id"] if isinstance(nv, dict) else None

    s, _ = post_json({**CH, "Content-Type": "application/json"},
        f"/api/v1/customer/bulk/variants/{variant_id}", None)  # PUT
    # ↑ use real PUT instead
    req = urllib.request.Request(
        BASE + f"/api/v1/customer/bulk/variants/{variant_id}",
        data=json.dumps({"weight": 3}).encode(),
        headers=CH, method="PUT",
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        check("edit variant", r.status == 200, "")
    except urllib.error.HTTPError as e:
        check("edit variant", False, f"status={e.code} body={e.read().decode()[:200]}")

    s, _ = delete(CH, f"/api/v1/customer/bulk/variants/{variant_id}")
    check("delete variant", s == 200, f"status={s}")

    # ── Start + wait ──────────────────────────────────────────────────
    s, _ = post_json(CH, f"/api/v1/customer/bulk/batches/{batch_id}/start", None)
    check("start batch", s == 200, f"status={s}")

    deadline = time.time() + 90
    final = None
    while time.time() < deadline:
        time.sleep(2)
        s, det = get(CH, f"/api/v1/customer/bulk/batches/{batch_id}")
        if det["status"] in ("completed", "failed", "canceled", "paused"):
            final = det
            break

    check("batch completed in <90s", final is not None and final["status"] == BATCH_COMPLETED,
          f"final={final and final['status']}")
    if not final:
        return _fail()
    print(f"  final: sent={final['sent_count']}/{final['total_targets']}  failed={final['failed_count']}")

    # ── Wallet was actually charged ────────────────────────────────────
    with Session(engine) as db:
        w = db.get(CustomerWallet, customer_id)
        balance_after = w.balance_cents
    spent = balance_before - balance_after
    check("wallet was charged", spent > 0, f"before={balance_before} after={balance_after}")
    print(f"  wallet after: ${balance_after/100:.2f}  (spent ${spent/100:.2f})")

    # ── Simulate an inbound reply ──────────────────────────────────────
    with Session(engine) as db:
        sent_target = db.exec(
            select(BulkTarget).where(BulkTarget.batch_id == batch_id)
            .where(BulkTarget.status == TARGET_SENT).limit(1)
        ).first()
        # If no sent target left (mock_mode random), seed one
        if not sent_target:
            sent_target = BulkTarget(
                batch_id=batch_id, customer_id=customer_id,
                tg_user_id=987100001, tg_username="e2e_replyer",
                display_name="E2E Replyer", status=TARGET_SENT,
                assigned_account_id=71,
            )
            db.add(sent_target); db.commit(); db.refresh(sent_target)
        # update tg_user_id if none
        if not sent_target.tg_user_id:
            sent_target.tg_user_id = 987100002
            db.add(sent_target); db.commit()

        account = db.get(Account, sent_target.assigned_account_id or 71)
        lead = handle_inbound_dm(
            db, account=account,
            sender_tg_user_id=sent_target.tg_user_id,
            sender_username="e2e_replyer", sender_first_name="E2E",
            message_text="Yes, tell me more",
        )
        check("inbound bulk reply → Lead created", lead is not None and lead.source == "bulk",
              f"lead={lead}")

    # ── Leads filter shows the bulk reply ──────────────────────────────
    s, ls = get(CH, f"/api/v1/customer/leads?source=bulk&bulk_batch_id={batch_id}")
    check("leads filter (source=bulk, batch)", s == 200 and isinstance(ls, list) and len(ls) >= 1,
          f"status={s} count={len(ls) if isinstance(ls, list) else 'N/A'}")

    # ── Admin metrics endpoint produces a coherent snapshot ────────────
    s, m = get(AH, "/api/v1/admin/bulk/metrics")
    check("admin metrics 200", s == 200, f"status={s}")
    if isinstance(m, dict):
        check("metrics has window stats", "window" in m and "sent" in m["window"], "")
        check("metrics mock_mode flag present", "mock_mode" in m, "")

    # ── Cleanup created rows so this can be re-run ─────────────────────
    with Session(engine) as db:
        # Drop all targets/variants/batch for this run
        for t in db.exec(select(BulkTarget).where(BulkTarget.batch_id == batch_id)).all():
            db.delete(t)
        for v in db.exec(select(BulkTemplateVariant).where(BulkTemplateVariant.batch_id == batch_id)).all():
            db.delete(v)
        batch = db.get(BulkBatch, batch_id)
        if batch:
            db.delete(batch)
        # Drop the lead we created
        for l in db.exec(
            select(Lead).where(Lead.bulk_batch_id == batch_id)
        ).all():
            db.delete(l)
        # Drop wallet charges tied to this batch
        for tx in db.exec(
            select(WalletTransaction).where(WalletTransaction.bulk_batch_id == batch_id)
        ).all():
            db.delete(tx)
        # Restore wallet
        w = db.get(CustomerWallet, customer_id)
        if w:
            w.balance_cents = balance_before
            w.total_spent_cents = max(0, w.total_spent_cents - spent)
            db.add(w)
        db.commit()
    check("cleanup", True)

    return _exit_code()


def _fail() -> int:
    print("\n  abort — see failures above\n")
    return _exit_code()


def _exit_code() -> int:
    print()
    print(f"  passed: {len(PASSED)}")
    print(f"  failed: {len(FAILED)}")
    if FAILED:
        print("\n  FAILED checks:")
        for c in FAILED:
            print(f"    - {c}")
        print()
        return 1
    print("\n  ✓ all checks passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
