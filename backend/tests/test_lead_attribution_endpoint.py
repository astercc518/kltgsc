"""
Phase 11 endpoint: GET /api/v1/customer/leads/{id}/attribution.

Hits the FastAPI surface so the lazy-link-then-return shape works end-to-end.
"""
from datetime import datetime, timedelta, timezone

from app.models.customer import Customer
from app.models.lead import Lead
from app.models.pending_reply import PendingReply, PendingReplyStatus


def _now():
    return datetime.now(timezone.utc)


def _seed_customer(session) -> Customer:
    c = Customer(
        email="attr@example.test",
        hashed_password="x",
        status="active",
        plan="starter",
        account_quota=3,
        group_quota=500,
        token_quota=2_000_000,
        seat_quota=1,
    )
    session.add(c); session.commit(); session.refresh(c)
    return c


_REPLY_ID = [2000]


def _next_reply_id():
    _REPLY_ID[0] += 1
    return _REPLY_ID[0]


def _seed_reply(session, *, customer_id, source_user_id, sent_at,
                lead_id=None, monitor_id=7, chat_id=-100_222_333):
    r = PendingReply(
        id=_next_reply_id(),
        customer_id=customer_id,
        monitor_id=monitor_id,
        chat_id=chat_id,
        message_id=1,
        source_user_id=source_user_id,
        source_text="want OTC USDT",
        reply_text="DM me",
        status=PendingReplyStatus.SENT.value,
        created_at=_now(),
        sent_at=sent_at,
        lead_id=lead_id,
        layer3_score=72,
        layer3_confidence=0.81,
        experiment_tag="exp_a",
    )
    session.add(r); session.commit(); session.refresh(r)
    return r


def _override_current_customer(client, customer: Customer):
    from app.api.deps_customer import get_current_customer
    client.app.dependency_overrides[get_current_customer] = lambda: customer


def test_attribution_endpoint_returns_lazy_linked_replies(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    now = _now()
    lead = Lead(
        account_id=1,
        customer_id=customer.id,
        telegram_user_id=555,
        username="otc_buyer",
        status="new",
        created_at=now,
    )
    session.add(lead); session.commit(); session.refresh(lead)

    # PendingReply pre-exists with no lead_id; endpoint should lazy-link it.
    _seed_reply(
        session, customer_id=customer.id, source_user_id=555,
        sent_at=now - timedelta(hours=3),
    )

    r = client.get(f"/api/v1/customer/leads/{lead.id}/attribution")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lead_id"] == lead.id
    assert body["customer_id"] == customer.id
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["monitor_id"] == 7
    assert entry["source_text"] == "want OTC USDT"
    assert entry["reply_text"] == "DM me"
    assert entry["layer3_score"] == 72
    assert entry["experiment_tag"] == "exp_a"


def test_attribution_endpoint_404_on_other_tenant_lead(client, session):
    me = _seed_customer(session)
    other = Customer(
        email="other@example.test",
        hashed_password="y",
        status="active",
        plan="starter",
        account_quota=3, group_quota=500, token_quota=2_000_000, seat_quota=1,
    )
    session.add(other); session.commit(); session.refresh(other)
    _override_current_customer(client, me)

    other_lead = Lead(
        account_id=1,
        customer_id=other.id,
        telegram_user_id=777,
        username="not_mine",
        status="new",
        created_at=_now(),
    )
    session.add(other_lead); session.commit(); session.refresh(other_lead)

    r = client.get(f"/api/v1/customer/leads/{other_lead.id}/attribution")
    assert r.status_code == 404


def test_attribution_endpoint_empty_when_nothing_linked(client, session):
    customer = _seed_customer(session)
    _override_current_customer(client, customer)

    lead = Lead(
        account_id=1,
        customer_id=customer.id,
        telegram_user_id=999,
        username="ghost",
        status="new",
        created_at=_now(),
    )
    session.add(lead); session.commit(); session.refresh(lead)

    r = client.get(f"/api/v1/customer/leads/{lead.id}/attribution")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entries"] == []
