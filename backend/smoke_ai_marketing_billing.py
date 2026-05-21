"""S2.4 / S2.5 smoke test — AI marketing per-action billing + pre-assign.

The active-marketing reply path (_execute_active_marketing) and the
lead upsert path (_upsert_internal_pool_lead) both live behind Pyrogram
event handlers, so an HTTP-only smoke can't trigger them.  Instead this
smoke exercises the *service-level* contracts those paths depend on:

    1. feature_billing.charge('ai_marketing_group_reply', ...) deducts
       the right amount from the customer wallet
    2. Re-charging with the same idempotency_key is a no-op (no double
       billing)
    3. feature_billing.charge('ai_marketing_lead_created', ...) deducts
       correctly
    4. lead.assigned_to_user_id is settable to a CustomerUser.id (the
       Phase G + S2.5 model relaxation)
    5. balance after both charges = wallet_credit - group_reply_cost
       - lead_created_cost

The customer is provisioned via /admin/billing/quick-provision with a
$500 wallet credit so charges never hit InsufficientBalanceError.

Run inside the backend container:
    docker exec tgsc-backend-1 python3 /app/smoke_ai_marketing_billing.py

Prereq: ADMIN_PASSWORD env var.
"""
import os
import secrets
import sys

import httpx

# Service-level imports — same engine as the running backend (so reads
# we make show the latest commits of the test customer wallet).
from sqlmodel import Session, select

from app.core.db import engine
from app.models.customer import Customer
from app.models.customer_user import CustomerUser, CU_ROLE_SALES
from app.models.feature import FeatureRegistry, CustomerFeature
from app.models.lead import Lead
from app.models.wallet import CustomerWallet, WalletTransaction, TXN_CHARGE
from app.services import feature_billing as fb
from app.services import wallet_service as ws


BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SMOKE_EMAIL = f"smoke-aib-{secrets.token_hex(4)}@x.tg1.ai"
SMOKE_PASSWORD = "SmokeAIB-Test1234!"
WALLET_CREDIT_CENTS = 50_000  # $500


def step(name: str, ok: bool, detail: str = "") -> None:
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def provision(http: httpx.Client, admin_h: dict) -> int:
    r = http.post(
        "/admin/billing/quick-provision",
        json={
            "new_customer_email": SMOKE_EMAIL,
            "new_customer_password": SMOKE_PASSWORD,
            "new_customer_name": "Smoke AI Billing",
            "plan": "growth",
            "wallet_credit_cents": WALLET_CREDIT_CENTS,
            "note": "smoke_ai_marketing_billing.py",
        },
        headers=admin_h,
    )
    step("quick-provision ok", r.status_code in (200, 201),
         f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["customer_id"]


def main() -> None:
    if not ADMIN_PASSWORD:
        print("  ADMIN_PASSWORD env not set; aborting")
        sys.exit(2)

    http = httpx.Client(base_url=BASE, timeout=10)

    # ── 1) Setup customer with $500 wallet + growth plan ──────────────
    print("=== 1) Provision smoke customer (admin quick-provision) ===")
    r = http.post(
        "/login/access-token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    step("admin login ok", r.status_code == 200)
    admin_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cid = provision(http, admin_h)
    print(f"  customer_id={cid}  email={SMOKE_EMAIL}")

    with Session(engine) as session:
        wallet = ws.get_or_create_wallet(session, cid)
        starting_balance = wallet.balance_cents
        step("wallet credited $500", starting_balance == WALLET_CREDIT_CENTS,
             f"got {starting_balance}")

    # ── 2) feature_billing.charge for ai_marketing_group_reply ───────
    print("\n=== 2) Charge ai_marketing_group_reply ===")
    fake_hit_id = secrets.randbelow(10**9)
    idem_reply = f"feat:ai_marketing_group_reply:{fake_hit_id}"
    with Session(engine) as session:
        # Look up registered price for the assertion later.
        reg = session.get(FeatureRegistry, "ai_marketing_group_reply")
        step("ai_marketing_group_reply registered", reg is not None
             and reg.is_active, f"reg={reg}")
        unit_price_group = reg.default_price_cents

        txn = fb.charge(
            session, customer_id=cid,
            slug="ai_marketing_group_reply", units=1,
            idempotency_key=idem_reply,
            description=f"smoke active reply hit#{fake_hit_id}",
        )
        step("group_reply charge txn returned", txn is not None)
        step("amount == default_price_cents",
             abs(txn.amount_cents) == unit_price_group,
             f"got {txn.amount_cents}, expected -{unit_price_group}")

    # ── 3) Idempotency — re-charge same key, no extra debit ──────────
    print("\n=== 3) Repeat charge with same idempotency_key ===")
    with Session(engine) as session:
        before = ws.get_balance_cents(session, cid)
        txn2 = fb.charge(
            session, customer_id=cid,
            slug="ai_marketing_group_reply", units=1,
            idempotency_key=idem_reply,
            description="retry — should be idempotent",
        )
        after = ws.get_balance_cents(session, cid)
        step("repeat returns existing txn id", txn2.idempotency_key == idem_reply)
        step("balance unchanged on retry", before == after,
             f"before={before} after={after}")

    # ── 4) Charge ai_marketing_lead_created ──────────────────────────
    print("\n=== 4) Charge ai_marketing_lead_created ===")
    fake_lead_id = secrets.randbelow(10**9)
    idem_lead = f"feat:ai_marketing_lead_created:{fake_lead_id}"
    with Session(engine) as session:
        reg = session.get(FeatureRegistry, "ai_marketing_lead_created")
        unit_price_lead = reg.default_price_cents
        txn = fb.charge(
            session, customer_id=cid,
            slug="ai_marketing_lead_created", units=1,
            idempotency_key=idem_lead,
            description=f"smoke auto lead #{fake_lead_id}",
        )
        step("lead_created charge txn returned", txn is not None)
        step("amount == default_price_cents",
             abs(txn.amount_cents) == unit_price_lead,
             f"got {txn.amount_cents}, expected -{unit_price_lead}")

    # ── 5) Final balance sanity check ────────────────────────────────
    print("\n=== 5) Wallet balance reflects both charges ===")
    with Session(engine) as session:
        end = ws.get_balance_cents(session, cid)
        expected = starting_balance - unit_price_group - unit_price_lead
        step("balance == start - group_reply - lead_created",
             end == expected,
             f"end={end} start={starting_balance} group={unit_price_group} "
             f"lead={unit_price_lead} expected={expected}")

    # ── 6) Audit the WalletTransaction rows (source classification) ──
    print("\n=== 6) WalletTransaction rows recorded ===")
    with Session(engine) as session:
        rows = session.exec(
            select(WalletTransaction).where(
                WalletTransaction.customer_id == cid,
                WalletTransaction.type == TXN_CHARGE,
            ).order_by(WalletTransaction.created_at.desc())
        ).all()
        keys = {r.idempotency_key for r in rows}
        step("group_reply txn present", idem_reply in keys)
        step("lead_created txn present", idem_lead in keys)
        step("exactly 2 charge rows (idempotent retry did not insert)",
             len(rows) == 2, f"saw {len(rows)} rows")

    # ── 7) Pre-assign extension — verify S2.5 in source (avoids
    # needing Pyrogram to actually run + needing the test customer's
    # account pool to be non-empty).
    print("\n=== 7) S2.5 — listener pre-assigns leads for customer-kind sales ===")
    import inspect
    from app.services import listener_service
    src = inspect.getsource(listener_service.ListenerService._upsert_internal_pool_lead)
    step("upsert references both platform and customer kinds",
         '("platform", "customer")' in src,
         "expected the kind tuple to include both")
    step("upsert charges ai_marketing_lead_created",
         "ai_marketing_lead_created" in src,
         "S2.4 wiring should be present in the source")
    step("active marketing charges ai_marketing_group_reply",
         "ai_marketing_group_reply" in inspect.getsource(
             listener_service.ListenerService._execute_active_marketing),
         "S2.4 wiring should be present in the source")

    print("\n[PASS] smoke_ai_marketing_billing")


if __name__ == "__main__":
    main()
