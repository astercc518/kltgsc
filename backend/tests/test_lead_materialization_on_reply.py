from __future__ import annotations
import json
from types import SimpleNamespace
from datetime import datetime
import pytest
from sqlmodel import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.wallet import CustomerWallet, WalletTransaction
from app.models.feature import FeatureRegistry
from app.models.keyword_monitor import KeywordMonitor
from app.models.lead import Lead, LeadInteraction
from app.services.listener_service import ListenerService


def _make_account(session, *, customer_id=None, sales_uid=None, sales_kind=None):
    acc = Account(
        phone_number=f"+1{customer_id or 0:09d}",
        session_string="s", session_file_path="p",
        status="active", api_id=1, api_hash="h",
        customer_id=customer_id,
        assigned_to_sales_user_id=sales_uid,
        assigned_to_sales_kind=sales_kind,
    )
    session.add(acc); session.commit(); session.refresh(acc)
    return acc


def _make_customer(session, *, industry="crypto", is_internal_pool=False):
    c = Customer(
        email=f"c{int(datetime.utcnow().timestamp()*1000)%100000}@t.x",
        name="t", status="active", plan="growth",
        subscription_status="active",
        account_quota=5, group_quota=1000, token_quota=2_000_000, seat_quota=3,
        account_used=0, group_used=0, token_used=0, seat_used=0,
        hashed_password="x",
        industry=industry,
        is_internal_pool=is_internal_pool,
    )
    session.add(c); session.commit(); session.refresh(c)
    w = CustomerWallet(customer_id=c.id, balance_cents=10000,
                       total_topup_cents=10000, total_spent_cents=0)
    session.add(w); session.commit()
    return c


def _make_monitor(session, *, customer_id, keyword="BTC", industry="crypto"):
    m = KeywordMonitor(
        keyword=keyword, match_type="partial",
        target_groups="-100123",
        marketing_mode="active", action_type="trigger_ai",
        reply_mode="group_reply",
        is_active=True, customer_id=customer_id, industry=industry,
        score_weight=10, max_replies_per_day=10,
    )
    session.add(m); session.commit(); session.refresh(m)
    return m


def _make_feature_registry(session):
    rows = [
        FeatureRegistry(
            slug="ai_marketing_lead_created", name_en="AI Auto-Created Lead",
            name_zh="AI 自动线索", category="ai", default_price_cents=50,
            billing_unit="lead", enabled_by_default=True,
        ),
        FeatureRegistry(
            slug="ai_marketing_group_reply", name_en="AI Active Group Reply",
            name_zh="AI 群内主动回话", category="ai", default_price_cents=5,
            billing_unit="reply", enabled_by_default=True,
        ),
    ]
    for r in rows:
        session.add(r)
    session.commit()


def _fake_message(*, text="Anyone trading BTC?", tg_user_id=70000001,
                  username="verify_user", first_name="Verify",
                  chat_id=-100123, chat_title="Verify Group"):
    return SimpleNamespace(
        text=text, caption=None,
        chat=SimpleNamespace(id=chat_id, title=chat_title, username=None,
                             type="supergroup"),
        from_user=SimpleNamespace(id=tg_user_id, username=username,
                                  first_name=first_name),
        id=999,
    )


@pytest.mark.asyncio
async def test_new_lead_with_pre_assign_and_charge(session):
    _make_feature_registry(session)
    cust = _make_customer(session)
    acc = _make_account(session, customer_id=cust.id,
                        sales_uid=99, sales_kind="customer")
    monitor = _make_monitor(session, customer_id=cust.id)

    listener = ListenerService()
    listener.client_accounts["c1"] = acc

    msg = _fake_message()
    reply_text = "Sure, our platform supports BTC/USDT with 0.1% fees."

    await listener._upsert_lead_for_customer_reply(
        session=session,
        client=SimpleNamespace(name="c1"),
        monitor=monitor,
        message=msg,
        reply_text=reply_text,
    )

    leads = list(session.exec(select(Lead).where(Lead.customer_id == cust.id)).all())
    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "monitor"
    assert lead.status == "new"
    assert lead.industry == "crypto"
    assert lead.telegram_user_id == 70000001
    assert lead.account_id == acc.id
    assert lead.assigned_to_user_id == 99
    assert lead.claimed_at is not None
    tags = json.loads(lead.tags_json)
    assert "monitor:BTC" in tags

    interactions = list(session.exec(
        select(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
        .order_by(LeadInteraction.id)
    ).all())
    assert len(interactions) == 2
    assert interactions[0].direction == "inbound"
    assert interactions[0].content == "Anyone trading BTC?"
    assert interactions[1].direction == "outbound"
    assert interactions[1].content == reply_text

    txs = list(session.exec(
        select(WalletTransaction)
        .where(WalletTransaction.customer_id == cust.id)
        .where(WalletTransaction.idempotency_key
               == f"feat:ai_marketing_lead_created:{lead.id}")
    ).all())
    assert len(txs) == 1
    assert txs[0].amount_cents == -50  # debit


@pytest.mark.asyncio
async def test_repeat_hit_no_duplicate_lead_no_recharge(session):
    _make_feature_registry(session)
    cust = _make_customer(session)
    acc = _make_account(session, customer_id=cust.id)
    monitor = _make_monitor(session, customer_id=cust.id)

    listener = ListenerService()
    listener.client_accounts["c1"] = acc
    msg = _fake_message()
    fake_client = SimpleNamespace(name="c1")

    await listener._upsert_lead_for_customer_reply(
        session=session, client=fake_client, monitor=monitor,
        message=msg, reply_text="r1",
    )
    await listener._upsert_lead_for_customer_reply(
        session=session, client=fake_client, monitor=monitor,
        message=msg, reply_text="r2",
    )

    leads = list(session.exec(select(Lead).where(Lead.customer_id == cust.id)).all())
    assert len(leads) == 1

    interactions = list(session.exec(
        select(LeadInteraction).where(LeadInteraction.lead_id == leads[0].id)
        .order_by(LeadInteraction.id)
    ).all())
    assert len(interactions) == 4
    assert interactions[0].direction == "inbound"
    assert interactions[1].direction == "outbound"
    assert interactions[1].content == "r1"
    assert interactions[3].content == "r2"

    txs = list(session.exec(
        select(WalletTransaction).where(WalletTransaction.customer_id == cust.id)
        .where(WalletTransaction.idempotency_key
               == f"feat:ai_marketing_lead_created:{leads[0].id}")
    ).all())
    assert len(txs) == 1


@pytest.mark.asyncio
async def test_internal_pool_active_monitor_creates_lead(session):
    _make_feature_registry(session)
    cust = _make_customer(session, is_internal_pool=True)
    acc = _make_account(session, customer_id=cust.id,
                        sales_uid=7, sales_kind="platform")
    monitor = _make_monitor(session, customer_id=cust.id)

    listener = ListenerService()
    listener.client_accounts["c1"] = acc

    await listener._upsert_lead_for_customer_reply(
        session=session, client=SimpleNamespace(name="c1"),
        monitor=monitor, message=_fake_message(),
        reply_text="hello from active mode",
    )

    leads = list(session.exec(select(Lead).where(Lead.customer_id == cust.id)).all())
    assert len(leads) == 1, (
        "internal-pool customers running active monitors must still get a Lead "
        "from this helper — F4 only fires in passive mode"
    )
    assert leads[0].assigned_to_user_id == 7


@pytest.mark.asyncio
async def test_account_without_customer_skipped(session):
    _make_feature_registry(session)
    acc = _make_account(session, customer_id=None)
    other_cust = _make_customer(session)
    monitor = _make_monitor(session, customer_id=other_cust.id)

    listener = ListenerService()
    listener.client_accounts["c1"] = acc

    await listener._upsert_lead_for_customer_reply(
        session=session, client=SimpleNamespace(name="c1"),
        monitor=monitor, message=_fake_message(),
        reply_text="nope",
    )

    leads = list(session.exec(select(Lead)).all())
    assert len(leads) == 0


@pytest.mark.asyncio
async def test_dedup_with_existing_f4_lead(session):
    _make_feature_registry(session)
    cust = _make_customer(session, is_internal_pool=True)
    acc = _make_account(session, customer_id=cust.id)
    monitor = _make_monitor(session, customer_id=cust.id)

    import json as _json
    pre_lead = Lead(
        account_id=acc.id,
        telegram_user_id=70000001,
        username="verify_user",
        first_name="Verify",
        status="new",
        source="monitor",
        tags_json=_json.dumps(["monitor:BTC"]),
        customer_id=cust.id,
        industry="crypto",
        last_interaction_at=datetime.utcnow(),
    )
    session.add(pre_lead); session.commit(); session.refresh(pre_lead)
    original_id = pre_lead.id

    listener = ListenerService()
    listener.client_accounts["c1"] = acc

    await listener._upsert_lead_for_customer_reply(
        session=session, client=SimpleNamespace(name="c1"),
        monitor=monitor, message=_fake_message(),
        reply_text="from active reply",
    )

    leads = list(session.exec(select(Lead).where(Lead.customer_id == cust.id)).all())
    assert len(leads) == 1
    assert leads[0].id == original_id

    interactions = list(session.exec(
        select(LeadInteraction).where(LeadInteraction.lead_id == original_id)
    ).all())
    assert len(interactions) == 2

    txs = list(session.exec(
        select(WalletTransaction).where(WalletTransaction.customer_id == cust.id)
        .where(WalletTransaction.idempotency_key
               == f"feat:ai_marketing_lead_created:{original_id}")
    ).all())
    assert len(txs) == 0
