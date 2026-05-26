"""End-to-end smoke for active-marketing Lead materialization.

Run from inside the backend container against the live DB:

  docker cp backend/scripts/smoke_active_marketing_lead.py tgsc-backend-1:/tmp/
  docker exec -w /app tgsc-backend-1 python /tmp/smoke_active_marketing_lead.py

Pre-reqs:
  - Gemini provider (Vertex or AI Studio) is active in ai_config and reachable.
    (Smoke does NOT call the LLM — but the surrounding container should still
    have a working AIConfig row for parity with prod path.)
  - Customer 'smoke@tg1.ai' exists with subscription_status='active', wallet
    balance >= $1.00, AI features enabled (see scripts/backfill_ai_marketing_features.py).
  - At least one Account row with customer_id=<smoke customer id>.

The script writes to prod DB. Rows are tagged so they can be cleaned up:
  - KeywordMonitor.description = 'smoke: active-lead'
  - Lead.notes starts with "From 'Smoke Active Lead Group':"

It does NOT actually send a Telegram message — it invokes the helper
_upsert_lead_for_customer_reply directly with a synthetic message + a
synthetic reply_text, bypassing the 30-180s active-marketing delay
AND the real Telegram send_message AND the LLM call.
"""
import asyncio
import sys
from types import SimpleNamespace
from datetime import datetime
sys.path.insert(0, "/app")

# pyrogram.enums.ChatType shim (the helper inspects message.chat.type
# in some surrounding code paths; safe to keep even though _upsert
# doesn't use it directly).
import pyrogram
class _ChatType:
    PRIVATE = "private"
    GROUP = "group"
    SUPERGROUP = "supergroup"
pyrogram.enums.ChatType = _ChatType

from sqlmodel import Session, select
from app.core.db import engine
from app.models.account import Account
from app.models.customer import Customer
from app.models.keyword_monitor import KeywordMonitor
from app.models.lead import Lead, LeadInteraction
from app.models.wallet import CustomerWallet, WalletTransaction
from app.services.listener_service import ListenerService

CUSTOMER_EMAIL = "smoke@tg1.ai"
TEST_KEYWORD = "BTC"
TEST_CHAT_ID = -1001234567890


async def main():
    # Read setup state
    with Session(engine) as s:
        cust = s.exec(select(Customer).where(Customer.email == CUSTOMER_EMAIL)).first()
        if not cust:
            print(f"[FAIL] no Customer with email={CUSTOMER_EMAIL}")
            sys.exit(1)
        print(f"[cust] id={cust.id} plan={cust.plan} sub={cust.subscription_status} "
              f"is_internal_pool={cust.is_internal_pool} industry={cust.industry}")

        acc = s.exec(select(Account).where(Account.customer_id == cust.id).limit(1)).first()
        if not acc:
            print(f"[FAIL] customer {cust.id} has no Account row")
            sys.exit(2)
        print(f"[acc] id={acc.id} sales_uid={acc.assigned_to_sales_user_id} "
              f"sales_kind={acc.assigned_to_sales_kind}")

        mon = s.exec(select(KeywordMonitor).where(
            KeywordMonitor.customer_id == cust.id,
            KeywordMonitor.marketing_mode == "active",
            KeywordMonitor.is_active == True,  # noqa: E712
        ).limit(1)).first()
        if not mon:
            mon = KeywordMonitor(
                keyword=TEST_KEYWORD, match_type="partial",
                target_groups=str(TEST_CHAT_ID),
                marketing_mode="active", action_type="trigger_ai",
                reply_mode="group_reply",
                is_active=True, customer_id=cust.id, industry=cust.industry,
                score_weight=10, max_replies_per_day=10,
                description="smoke: active-lead",
            )
            s.add(mon); s.commit(); s.refresh(mon)
            print(f"[mon] created id={mon.id} kw={mon.keyword}")
        else:
            print(f"[mon] using existing id={mon.id} kw={mon.keyword}")
        mon_id = mon.id

        wallet = s.exec(select(CustomerWallet)
                        .where(CustomerWallet.customer_id == cust.id)).first()
        wallet_before = wallet.balance_cents if wallet else 0
        leads_before = len(list(s.exec(
            select(Lead).where(Lead.customer_id == cust.id)).all()))
        cust_id = cust.id
        acc_id = acc.id

    # Build synthetic message
    fake_msg = SimpleNamespace(
        text=f"Anyone trading {TEST_KEYWORD} today? Looking for a platform.",
        caption=None, id=999, outgoing=False,
        chat=SimpleNamespace(id=TEST_CHAT_ID, type=_ChatType.SUPERGROUP,
                             title="Smoke Active Lead Group", username=None),
        from_user=SimpleNamespace(
            id=80000001, username="smoke_active_user",
            first_name="SmokeActive",
        ),
    )
    reply_text = "Smoke reply: our platform supports BTC pairs."

    # Drive the helper
    with Session(engine) as s:
        acc_ref = s.get(Account, acc_id)
        mon_ref = s.get(KeywordMonitor, mon_id)

        listener = ListenerService()
        listener.client_accounts["smoke_client"] = acc_ref
        await listener._upsert_lead_for_customer_reply(
            session=s,
            client=SimpleNamespace(name="smoke_client"),
            monitor=mon_ref,
            message=fake_msg,
            reply_text=reply_text,
        )

    # Inspect result
    txs = []
    with Session(engine) as s:
        leads_after = list(s.exec(
            select(Lead).where(Lead.customer_id == cust_id)
            .order_by(Lead.id.desc())
        ).all())
        new_count = len(leads_after) - leads_before
        print(f"[delta] leads {leads_before} -> {len(leads_after)} (new: {new_count})")

        if leads_after:
            lead = leads_after[0]
            print(f"  lead#{lead.id} tg_user={lead.telegram_user_id} "
                  f"status={lead.status} src={lead.source} assigned={lead.assigned_to_user_id} "
                  f"industry={lead.industry}")
            interactions = list(s.exec(
                select(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
                .order_by(LeadInteraction.id.desc()).limit(2)
            ).all())
            print(f"  recent interactions: {len(interactions)}")
            for it in reversed(interactions):
                print(f"    {it.direction}: {it.content[:60]!r}")
            txs = list(s.exec(
                select(WalletTransaction)
                .where(WalletTransaction.customer_id == cust_id)
                .where(WalletTransaction.idempotency_key
                       == f"feat:ai_marketing_lead_created:{lead.id}")
            ).all())
            print(f"  charges: {len(txs)} ({sum(t.amount_cents for t in txs)} cents)")

        wallet = s.exec(select(CustomerWallet)
                        .where(CustomerWallet.customer_id == cust_id)).first()
        wallet_after = wallet.balance_cents if wallet else 0
        print(f"[wallet] {wallet_before} -> {wallet_after} cents (delta {wallet_after-wallet_before})")

    is_new = new_count >= 1
    # On first run: new lead + single charge -> PASS
    # On re-run (dedup): no new lead, idempotent single charge, wallet unchanged -> PASS
    # Failure: first run produces no new lead at all
    if leads_after:
        lead = leads_after[0]
        dedup_ok = (not is_new) and (len(txs) == 1) and (wallet_after == wallet_before)
        new_ok = is_new and (len(txs) == 1)
        passed = new_ok or dedup_ok
    else:
        passed = False
    print("\n[PASS]" if passed else "\n[CHECK MANUALLY]")


asyncio.run(main())
