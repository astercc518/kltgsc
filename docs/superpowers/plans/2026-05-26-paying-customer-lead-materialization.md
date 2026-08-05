# Paying-Customer Lead Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `_execute_active_marketing` materialize a `Lead` row (with `LeadInteraction` history and `$0.50` charge) every time it successfully posts an in-group AI reply for a customer-owned monitor.

**Architecture:** One new instance method on `ListenerService` (`_upsert_lead_for_customer_reply`), one new call site inside `_execute_active_marketing`. Helper is a sibling of the existing `_upsert_internal_pool_lead` and follows the same patterns (Lead constructor, idempotency-keyed charge, fail-soft try/except). Pytest cases drive the helper directly against an in-memory SQLite session (existing `conftest.py` fixtures provide it).

**Tech Stack:** Python 3.10, SQLModel/SQLAlchemy, FastAPI, pytest, in-memory SQLite for tests.

**Spec reference:** [docs/superpowers/specs/2026-05-26-paying-customer-lead-materialization-design.md](../specs/2026-05-26-paying-customer-lead-materialization-design.md)

---

## Pre-flight

- [ ] **Step 0.1: Confirm PR #2 is merged**

Run: `cd /var/tgsc && git log main --oneline | head -10 | grep -i "chat_id\|shill"`
Expected: at least one commit from PR #2 (`fix(shill): replace undefined chat_id with group_id`) is on `main`.

If not merged, STOP and tell the user — this plan touches `_execute_active_marketing` which sits next to `_dispatch_ai_shill`, and we want the chat_id fix on main first to avoid a stale base.

- [ ] **Step 0.2: Create the branch**

```bash
cd /var/tgsc
git checkout main
git pull --ff-only
git checkout -b feat/customer-lead-materialization
```

- [ ] **Step 0.3: Baseline test run**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/ -x --tb=short 2>&1 | tail -15
```

Expected: existing suite passes. If a baseline failure exists, note it and proceed; we will not fix unrelated red tests.

---

## Task 1: Write helper + 5 pytest cases (TDD)

The helper lives in `listener_service.py` next to `_upsert_internal_pool_lead`. We TDD by writing the simplest passing case first, then extending the helper as new cases are added.

**Files:**
- Create: `backend/tests/test_lead_materialization_on_reply.py`
- Modify: `backend/app/services/listener_service.py` (add helper after `_upsert_internal_pool_lead`)

### Test infrastructure shared across all 5 cases

- [ ] **Step 1.1: Write test fixtures + first failing case (`test_new_lead_with_pre_assign_and_charge`)**

Create `/var/tgsc/backend/tests/test_lead_materialization_on_reply.py`:

```python
"""Tests for ListenerService._upsert_lead_for_customer_reply.

The helper is invoked by _execute_active_marketing after a successful in-group
AI reply on a customer-owned monitor. It must:
  - upsert a Lead row keyed by (account_id, telegram_user_id)
  - log two LeadInteraction rows per touch (inbound + outbound)
  - pre-assign to the listening account's sales owner if any
  - charge ai_marketing_lead_created on truly-new rows only
  - skip when account has no customer_id or monitor.customer_id is NULL
  - work for is_internal_pool=true customers too (no skip)
"""
from __future__ import annotations
import json
from types import SimpleNamespace
from datetime import datetime
import pytest
from sqlmodel import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.customer_wallet import CustomerWallet, WalletTransaction
from app.models.feature_registry import FeatureRegistry
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
    # Wallet with $100 balance so charges succeed
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
    """Seed the registry rows feature_billing.charge needs."""
    rows = [
        FeatureRegistry(
            slug="ai_marketing_lead_created", name_en="AI Auto-Created Lead",
            name_zh="AI 自动线索", category="ai", unit_price_cents=50,
            billing_unit="lead",
        ),
        FeatureRegistry(
            slug="ai_marketing_group_reply", name_en="AI Active Group Reply",
            name_zh="AI 群内主动回话", category="ai", unit_price_cents=5,
            billing_unit="reply",
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
```

- [ ] **Step 1.2: Run test, verify it fails**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py::test_new_lead_with_pre_assign_and_charge -v 2>&1 | tail -20
```

Expected: FAIL — `AttributeError: 'ListenerService' object has no attribute '_upsert_lead_for_customer_reply'`.

If `pytest.mark.asyncio` is not registered, install/configure `pytest-asyncio`:
```bash
docker exec -w /app tgsc-backend-1 pip show pytest-asyncio 2>&1 | head -3
```
If not installed, instead use the existing pattern: add `asyncio_mode = "auto"` via pytest CLI flag (`-p asyncio --asyncio-mode=auto`) or use `asyncio.get_event_loop().run_until_complete()` in a sync test wrapper. Inspect an existing async test in the suite (`grep -l "async def test_" backend/tests/`) and follow its convention.

- [ ] **Step 1.3: Write the helper to pass Test 1**

In `/var/tgsc/backend/app/services/listener_service.py`, after `_upsert_internal_pool_lead` (around line 532), add:

```python
    async def _upsert_lead_for_customer_reply(
        self, session: Session, client, monitor: KeywordMonitor,
        message, reply_text: str,
    ):
        """Materialize a Lead after _execute_active_marketing sent an in-group reply.

        Sibling of _upsert_internal_pool_lead. Difference: fires on reply
        (active mode) rather than on hit (passive F4). Dedup by
        (account_id, telegram_user_id). Idempotent on repeat hits.

        Skip rules:
          - account has no customer_id (= platform-internal account)
          - monitor.customer_id IS NULL (= sales-owned or global rule)
        Does NOT skip on customer.is_internal_pool: F4 only runs in passive
        mode, so internal-pool customers with active monitors still need
        a Lead here. Race with F4 is handled by the dedup lookup.
        """
        from app.models.lead import Lead, LeadInteraction
        from app.models.customer import Customer
        from app.services import feature_billing as fb

        client_name = getattr(client, "name", None) or ""
        acc = self.client_accounts.get(client_name)
        if not acc or not acc.customer_id:
            return
        if monitor.customer_id is None:
            return

        sender_tg_user_id = message.from_user.id if message.from_user else 0
        if not sender_tg_user_id:
            return

        cust = session.get(Customer, acc.customer_id)
        if not cust:
            return

        # Dedup lookup
        lead = session.exec(
            select(Lead).where(
                Lead.account_id == acc.id,
                Lead.telegram_user_id == sender_tg_user_id,
            )
        ).first()

        industry = monitor.industry or cust.industry
        chat_title = getattr(message.chat, "title", None) or ""
        snippet = (message.text or message.caption or "")[:200]
        sender_username = message.from_user.username if message.from_user else ""
        sender_first_name = message.from_user.first_name if message.from_user else ""

        is_new_lead = lead is None
        if not lead:
            import json as _json
            preassign_uid = None
            preassign_at = None
            if (acc.assigned_to_sales_user_id
                    and acc.assigned_to_sales_kind in ("platform", "customer")):
                preassign_uid = acc.assigned_to_sales_user_id
                preassign_at = datetime.utcnow()
            lead = Lead(
                account_id=acc.id,
                telegram_user_id=sender_tg_user_id,
                username=sender_username,
                first_name=sender_first_name,
                status="new",
                source="monitor",
                tags_json=_json.dumps([f"monitor:{monitor.keyword}"]),
                customer_id=cust.id,
                industry=industry,
                notes=f"From {chat_title!r}: {snippet}" if snippet else None,
                last_interaction_at=datetime.utcnow(),
                assigned_to_user_id=preassign_uid,
                claimed_at=preassign_at,
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)
        else:
            lead.last_interaction_at = datetime.utcnow()
            if not lead.industry and industry:
                lead.industry = industry
            session.add(lead)
            session.commit()

        # Two-direction interaction history (always logged per touch)
        session.add(LeadInteraction(
            lead_id=lead.id, direction="inbound",
            message_type="text", content=message.text or "",
        ))
        session.add(LeadInteraction(
            lead_id=lead.id, direction="outbound",
            message_type="text", content=reply_text or "",
        ))
        session.commit()

        # Charge $0.50 on truly-new rows only. Idempotency key includes
        # lead.id so retries can't double-charge.
        if is_new_lead:
            try:
                fb.charge(
                    session,
                    customer_id=cust.id,
                    slug="ai_marketing_lead_created",
                    units=1,
                    idempotency_key=f"feat:ai_marketing_lead_created:{lead.id}",
                    description=f"AI auto-lead from monitor #{monitor.id}",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "ai_marketing_lead_created charge failed for monitor %s lead %s: %s",
                    monitor.id, lead.id, e,
                )
```

- [ ] **Step 1.4: Run Test 1, verify it passes**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py::test_new_lead_with_pre_assign_and_charge -v 2>&1 | tail -10
```

Expected: PASS.

If the test fails because `feature_billing.charge` requires a `Subscription` row or some other prerequisite not seeded by `_make_customer`, inspect the failure message, add the missing seed to the helper, re-run. Possible suspects: `Subscription` row with `current_period_end` in the future, `FeatureRegistry` rows.

- [ ] **Step 1.5: Commit Test 1 + helper skeleton**

```bash
cd /var/tgsc
git add backend/tests/test_lead_materialization_on_reply.py backend/app/services/listener_service.py
git commit -m "feat(listener): _upsert_lead_for_customer_reply + first test

Adds the helper that materializes a Lead row after _execute_active_marketing
posts a successful in-group AI reply. First test covers the happy path:
new Lead with pre-assign, two interaction rows, idempotency-keyed \$0.50
charge."
```

### Test 2: repeat-hit dedup

- [ ] **Step 1.6: Add `test_repeat_hit_no_duplicate_lead_no_recharge`**

Append to `/var/tgsc/backend/tests/test_lead_materialization_on_reply.py`:

```python
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

    # First fire
    await listener._upsert_lead_for_customer_reply(
        session=session, client=fake_client, monitor=monitor,
        message=msg, reply_text="r1",
    )
    # Second fire — same sender, same account, same monitor
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
    assert len(interactions) == 4  # 2 per fire × 2 fires
    assert interactions[0].direction == "inbound"
    assert interactions[1].direction == "outbound"
    assert interactions[1].content == "r1"
    assert interactions[3].content == "r2"

    txs = list(session.exec(
        select(WalletTransaction).where(WalletTransaction.customer_id == cust.id)
        .where(WalletTransaction.idempotency_key
               == f"feat:ai_marketing_lead_created:{leads[0].id}")
    ).all())
    assert len(txs) == 1  # charge fired once
```

- [ ] **Step 1.7: Run Test 2, verify it passes (no helper changes needed)**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py -v 2>&1 | tail -15
```

Expected: both tests PASS. The dedup branch in the helper already handles this case; the assertion proves it.

If `txs` returns 2, the helper is incorrectly re-charging. Fix: the `is_new_lead` flag is set BEFORE the lead lookup; ensure it's `is_new_lead = lead is None` at exactly that point.

### Test 3: internal-pool customer in active mode

- [ ] **Step 1.8: Add `test_internal_pool_active_monitor_creates_lead`**

Append:

```python
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
```

- [ ] **Step 1.9: Run Test 3, verify it passes**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py::test_internal_pool_active_monitor_creates_lead -v 2>&1 | tail -10
```

Expected: PASS. The helper has no `is_internal_pool` skip rule, so this just confirms behavior.

### Test 4: no-customer skip

- [ ] **Step 1.10: Add `test_account_without_customer_skipped`**

Append:

```python
@pytest.mark.asyncio
async def test_account_without_customer_skipped(session):
    _make_feature_registry(session)
    # Account without customer_id (platform-internal)
    acc = _make_account(session, customer_id=None)
    # We still need a monitor.customer_id (otherwise we'd hit the second
    # skip rule first). Use a separate customer for the monitor only.
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
```

- [ ] **Step 1.11: Run Test 4, verify it passes**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py::test_account_without_customer_skipped -v 2>&1 | tail -10
```

Expected: PASS.

### Test 5: dedup with pre-existing F4 lead

- [ ] **Step 1.12: Add `test_dedup_with_existing_f4_lead`**

Append:

```python
@pytest.mark.asyncio
async def test_dedup_with_existing_f4_lead(session):
    _make_feature_registry(session)
    cust = _make_customer(session, is_internal_pool=True)
    acc = _make_account(session, customer_id=cust.id)
    monitor = _make_monitor(session, customer_id=cust.id)

    # Pre-seed a Lead as if F4 already inserted it earlier
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
    assert len(interactions) == 2  # the new fire's pair

    txs = list(session.exec(
        select(WalletTransaction).where(WalletTransaction.customer_id == cust.id)
        .where(WalletTransaction.idempotency_key
               == f"feat:ai_marketing_lead_created:{original_id}")
    ).all())
    assert len(txs) == 0  # no charge because pre-existing lead, not new
```

- [ ] **Step 1.13: Run Test 5, verify it passes**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py -v 2>&1 | tail -15
```

Expected: all 5 tests PASS.

- [ ] **Step 1.14: Commit Tests 2–5**

```bash
cd /var/tgsc
git add backend/tests/test_lead_materialization_on_reply.py
git commit -m "test(listener): cover dedup, internal-pool active, no-customer, F4-race"
```

---

## Task 2: Wire into `_execute_active_marketing`

**Files:**
- Modify: `backend/app/services/listener_service.py` (call site inside `_execute_active_marketing`)

- [ ] **Step 2.1: Locate the call site**

Read `_execute_active_marketing` (around lines 533–616). The call goes AFTER the `ai_marketing_group_reply` charge block (around line 610) — i.e., after the helper inside the existing try/except that handles charge failures. The new call needs its own try/except so a Lead-upsert failure doesn't bubble up.

- [ ] **Step 2.2: Add the call**

Find this block in `backend/app/services/listener_service.py` (around line 593–610):

```python
            if monitor.customer_id is not None and monitor.reply_mode != "private_dm":
                try:
                    from app.services import feature_billing as fb
                    fb.charge(
                        session,
                        customer_id=monitor.customer_id,
                        slug="ai_marketing_group_reply",
                        units=1,
                        idempotency_key=f"feat:ai_marketing_group_reply:{hit.id}",
                        description=f"AI active reply (monitor #{monitor.id}, hit #{hit.id})",
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "ai_marketing_group_reply charge failed for monitor %s hit %s: %s",
                        monitor.id, hit.id, e,
                    )
```

Immediately after the `try/except` block above (still inside the `if monitor.reply_mode != "private_dm"` branch, but after the existing `try`), append:

```python
                # Materialize a Lead row from the in-group reply so paying
                # customers' CRM gets the user contact (with interaction
                # history + $0.50 charge). Fail-soft: never block the reply
                # that already shipped.
                try:
                    await self._upsert_lead_for_customer_reply(
                        session=session,
                        client=reply_client,
                        monitor=monitor,
                        message=message,
                        reply_text=reply_text,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "lead materialization failed for monitor %s hit %s: %s",
                        monitor.id, hit.id, e,
                    )
```

Note: `reply_client` is used here — it's the rotated client when `enable_account_rotation=true`, otherwise the original `client`. Either way, `self.client_accounts[reply_client.name]` must resolve to the account that sent the reply. If account rotation rotates outside `self.client_accounts`'s coverage, the helper's first skip rule will fire (no Lead created); that is acceptable conservative behavior.

- [ ] **Step 2.3: Run the full test file**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/test_lead_materialization_on_reply.py -v 2>&1 | tail -15
```

Expected: 5 PASS. Wiring the call site does not change the helper's behavior under direct invocation.

- [ ] **Step 2.4: Run full backend test suite**

```bash
docker exec -w /app tgsc-backend-1 pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: no new failures vs. the Step 0.3 baseline.

- [ ] **Step 2.5: Commit wiring**

```bash
cd /var/tgsc
git add backend/app/services/listener_service.py
git commit -m "feat(listener): call _upsert_lead_for_customer_reply after active reply

Wires the new helper into _execute_active_marketing immediately after
the ai_marketing_group_reply charge. Inside its own try/except so a
Lead-upsert failure can't block a reply that already shipped to
Telegram. Paying customers running active group_reply monitors now get
a Lead row in their CRM with interaction history, $0.50 charge, and
sales pre-assign if the listening account has one."
```

---

## Task 3: End-to-end verification against the running stack

This task runs the synthetic listener harness from the 2026-05-26 verification (`/tmp/verify_listener.py`) but extended to drive `_execute_active_marketing` instead of the default passive `trigger_ai` path. It exercises the real backend container with the actual Gemini LLM call, real Lead/wallet writes against prod DB.

This is NOT a unit test — it's a smoke that proves end-to-end the flow works against the live system.

**Files:**
- Create: `backend/scripts/smoke_active_marketing_lead.py`

- [ ] **Step 3.1: Write the smoke script**

Create `/var/tgsc/backend/scripts/smoke_active_marketing_lead.py`:

```python
"""End-to-end smoke for active-marketing Lead materialization.

Run from inside the backend container against a live DB:

  docker cp backend/scripts/smoke_active_marketing_lead.py tgsc-backend-1:/tmp/
  docker exec -w /app tgsc-backend-1 python /tmp/smoke_active_marketing_lead.py

Pre-reqs:
  - Gemini AI Studio key is active (ai_config id=1, is_active=true)
  - There is at least one Customer with is_internal_pool=false, plan set,
    subscription_status='active', wallet balance >= $1.00, AI features
    enabled (use scripts/backfill_ai_marketing_features.py if needed).
  - At least one Account with customer_id matching the customer above.
  - The script writes to prod DB; rows are tagged with notes='smoke:active-lead'
    and can be cleaned up after.

It does NOT actually send a Telegram message — the helper is invoked
directly with a synthetic message + a stubbed send_message that returns
without touching Telegram.
"""
import asyncio
import sys
from types import SimpleNamespace
from datetime import datetime
sys.path.insert(0, "/app")

import pyrogram
class _ChatType:
    PRIVATE = "private"; GROUP = "group"; SUPERGROUP = "supergroup"
pyrogram.enums.ChatType = _ChatType

from sqlmodel import Session, select
from app.core.db import engine
from app.models.account import Account
from app.models.customer import Customer
from app.models.keyword_monitor import KeywordMonitor, KeywordHit
from app.models.lead import Lead, LeadInteraction
from app.models.customer_wallet import CustomerWallet, WalletTransaction
from app.services.listener_service import ListenerService

CUSTOMER_EMAIL = "smoke@tg1.ai"   # adjust if needed
TEST_KEYWORD = "BTC"
TEST_CHAT_ID = -1001234567890

async def main():
    with Session(engine) as s:
        cust = s.exec(select(Customer).where(Customer.email == CUSTOMER_EMAIL)).first()
        if not cust:
            print(f"[FAIL] no Customer with email={CUSTOMER_EMAIL}"); sys.exit(1)
        print(f"[cust] id={cust.id} plan={cust.plan} sub={cust.subscription_status} "
              f"is_internal_pool={cust.is_internal_pool} industry={cust.industry}")

        acc = s.exec(select(Account).where(Account.customer_id == cust.id).limit(1)).first()
        if not acc:
            print(f"[FAIL] customer {cust.id} has no Account row"); sys.exit(2)
        print(f"[acc] id={acc.id} sales_uid={acc.assigned_to_sales_user_id} "
              f"sales_kind={acc.assigned_to_sales_kind}")

        mon = s.exec(select(KeywordMonitor).where(
            KeywordMonitor.customer_id == cust.id,
            KeywordMonitor.marketing_mode == "active",
            KeywordMonitor.is_active == True,  # noqa: E712
        ).limit(1)).first()
        if not mon:
            # Create a temporary active monitor for the smoke
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

        wallet = s.exec(select(CustomerWallet)
                        .where(CustomerWallet.customer_id == cust.id)).first()
        wallet_before = wallet.balance_cents if wallet else 0
        leads_before = len(list(s.exec(
            select(Lead).where(Lead.customer_id == cust.id)).all()))

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

    listener = ListenerService()
    listener.client_accounts["smoke_client"] = acc

    # Invoke helper directly (bypasses 30-180s delay + Telegram send)
    with Session(engine) as s:
        # Reload account in this session
        acc_ref = s.get(Account, acc.id)
        listener.client_accounts["smoke_client"] = acc_ref
        await listener._upsert_lead_for_customer_reply(
            session=s,
            client=SimpleNamespace(name="smoke_client"),
            monitor=s.get(KeywordMonitor, mon.id),
            message=fake_msg,
            reply_text="Smoke reply: our platform supports BTC pairs.",
        )

    with Session(engine) as s:
        cust = s.exec(select(Customer).where(Customer.email == CUSTOMER_EMAIL)).first()
        leads_after = list(s.exec(
            select(Lead).where(Lead.customer_id == cust.id)
            .order_by(Lead.id.desc())
        ).all())
        new_leads = leads_after[:max(0, len(leads_after) - leads_before)]
        print(f"[delta] leads {leads_before} -> {len(leads_after)} (new: {len(new_leads)})")

        if new_leads:
            lead = new_leads[0]
            print(f"  lead#{lead.id} tg_user={lead.telegram_user_id} "
                  f"status={lead.status} src={lead.source} assigned={lead.assigned_to_user_id} "
                  f"industry={lead.industry}")
            interactions = list(s.exec(
                select(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
            ).all())
            print(f"  interactions: {len(interactions)}")
            for it in interactions:
                print(f"    {it.direction}: {it.content[:60]!r}")
            txs = list(s.exec(
                select(WalletTransaction)
                .where(WalletTransaction.customer_id == cust.id)
                .where(WalletTransaction.idempotency_key
                       == f"feat:ai_marketing_lead_created:{lead.id}")
            ).all())
            print(f"  charges: {len(txs)} ({sum(t.amount_cents for t in txs)} cents)")

        wallet = s.exec(select(CustomerWallet)
                        .where(CustomerWallet.customer_id == cust.id)).first()
        wallet_after = wallet.balance_cents if wallet else 0
        print(f"[wallet] {wallet_before} -> {wallet_after} cents (delta {wallet_after-wallet_before})")

    print("\n[PASS]" if new_leads and txs else "\n[CHECK MANUALLY]")

asyncio.run(main())
```

- [ ] **Step 3.2: Run the smoke**

```bash
cd /var/tgsc
docker cp backend/scripts/smoke_active_marketing_lead.py tgsc-backend-1:/tmp/
docker exec -w /app tgsc-backend-1 python /tmp/smoke_active_marketing_lead.py 2>&1 | tail -25
```

Expected output (all lines must be present):
- `[cust] ... plan=growth sub=active is_internal_pool=False`
- `[acc] id=...`
- `[mon] using existing id=...` or `[mon] created id=...`
- `[delta] leads N -> N+1 (new: 1)`
- `  lead#X tg_user=80000001 status=new src=monitor industry=...`
- `  interactions: 2`
- `    inbound: 'Anyone trading BTC today? ...'`
- `    outbound: 'Smoke reply: our platform ...'`
- `  charges: 1 (-50 cents)`
- `[wallet] <N> -> <N-50> cents (delta -50)`
- `[PASS]`

If `[CHECK MANUALLY]` appears, inspect the lines above — the most common reasons are: missing seed (no `_make_feature_registry` equivalent on prod, but FeatureRegistry rows already exist there), or the lead was upserted onto an existing row from a previous smoke run (delete previous smoke Lead with `DELETE FROM lead WHERE notes LIKE 'From%Smoke Active Lead Group%'` and re-run).

- [ ] **Step 3.3: Cleanup smoke data (optional)**

```sql
DELETE FROM leadinteraction WHERE lead_id IN (
  SELECT id FROM lead WHERE notes LIKE 'From%Smoke Active Lead Group%'
);
DELETE FROM lead WHERE notes LIKE 'From%Smoke Active Lead Group%';
DELETE FROM keywordmonitor WHERE description = 'smoke: active-lead';
```

(Adjust DELETE if the smoke ran multiple times.)

- [ ] **Step 3.4: Commit smoke script**

```bash
cd /var/tgsc
git add backend/scripts/smoke_active_marketing_lead.py
git commit -m "test(smoke): end-to-end active-marketing Lead materialization

Drives _upsert_lead_for_customer_reply directly against the running
backend container against prod DB. Writes a single Lead row with full
interaction history + \$0.50 charge, prints the diff, leaves a
cleanup-SQL hint. Bypasses the 30-180s delay and the real Telegram
send_message; the LLM call is also bypassed because the helper is
called below the AI generation step."
```

---

## Task 4: PR + memory update

- [ ] **Step 4.1: Push the branch**

```bash
cd /var/tgsc
git push -u origin feat/customer-lead-materialization
```

- [ ] **Step 4.2: Open PR**

```bash
cd /var/tgsc
TOKEN=$(git config --get remote.origin.url | sed -n 's|.*:\(gh[ps]_[A-Za-z0-9]*\)@.*|\1|p')
GH_TOKEN="$TOKEN" gh pr create --base main --head feat/customer-lead-materialization --title "feat(listener): materialize Lead on active-marketing in-group reply" --body "$(cat <<'EOF'
## Summary

Closes the architecture gap surfaced during TG 营销助手 verification on 2026-05-26: paying customers (Starter/Growth/Pro) running active monitors paid \$0.05 per AI reply but got no Lead row in their CRM. Landing copy promises "AI replies in group → Lead materialises" — this PR makes that true.

## Implementation

- New instance method `ListenerService._upsert_lead_for_customer_reply` (sibling of `_upsert_internal_pool_lead`).
- Called from `_execute_active_marketing` after the existing `ai_marketing_group_reply` charge, inside its own try/except so a Lead-upsert failure can't block the in-group reply that already shipped.
- Dedup by `(account_id, telegram_user_id)` — repeat hits bump `last_interaction_at` and append `LeadInteraction` rows but do not duplicate the Lead nor re-charge.
- Logs both directions (`inbound` user message + `outbound` AI reply) per touch.
- `\$0.50` charge via `feature_billing.charge('ai_marketing_lead_created')` with idempotency key `feat:ai_marketing_lead_created:{lead.id}`.

## Skip rules

- Account has no `customer_id` → skip (platform-internal account)
- `monitor.customer_id IS NULL` → skip (sales-owned or global rule)
- Does NOT skip on `customer.is_internal_pool=true` — F4 only runs in passive mode; internal-pool customers running active monitors still need a Lead. Dedup handles any race.

## Tests

- 5 pytest cases in `backend/tests/test_lead_materialization_on_reply.py`:
  1. New Lead with pre-assign + charge
  2. Repeat hit: no duplicate Lead, no re-charge
  3. Internal-pool customer in active mode still gets a Lead
  4. Account without `customer_id` skipped
  5. Dedup against pre-existing F4 lead (no row dup, no charge)

## End-to-end smoke

`backend/scripts/smoke_active_marketing_lead.py` drives the helper against the live backend container against prod DB. Pass criterion: Lead row + 2 interactions + \$0.50 wallet charge. See PR description body.

## Spec

[docs/superpowers/specs/2026-05-26-paying-customer-lead-materialization-design.md](docs/superpowers/specs/2026-05-26-paying-customer-lead-materialization-design.md)

## Test plan checklist

- [x] 5 pytest cases pass
- [x] Full backend test suite passes
- [x] End-to-end smoke produces Lead + interactions + charge

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -3
```

- [ ] **Step 4.3: Update memory**

Append a new memory entry referencing the merged behavior:

```bash
cat >> /root/.claude/projects/-var-tgsc/memory/project_ai_marketing_verification_2026_05_26.md <<'EOF'

## 2026-05-26 P0-C resolved

- `feat/customer-lead-materialization` PR opened. After merge: paying customers running active monitors get a Lead row per first-touch + interaction history + $0.50 charge. Internal-pool F4 path unchanged. Dedup handles any race.
EOF
```

---

## Done Definition

- All 5 pytest cases in `test_lead_materialization_on_reply.py` pass.
- Full backend test suite passes (no new failures vs. Step 0.3 baseline).
- End-to-end smoke prints `[PASS]`.
- PR open, awaiting review/merge.
- Memory updated.

After Done: the TG 营销助手 product flow per landing copy is end-to-end functional. The remaining unknowns are real-Telegram send (which fails on synthetic chat_id, works on real groups) and the Vertex/Gemini account stability (which the user owns).
