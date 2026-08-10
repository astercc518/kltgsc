# Paying-Customer Lead Materialization — Design Spec

**Date:** 2026-05-26
**Branch base:** `main`
**Source:** End-to-end verification of TG 营销助手 on 2026-05-26 surfaced an architectural gap, separate from the (already-fixed) `chat_id` NameError and the (resolved) Vertex/AI-Studio credential outage.

## Goal

Close the Lead-materialization gap so that a paying TG 营销助手 customer (Starter / Growth / Pro) gets a `lead` row whenever their `_execute_active_marketing` rule fires and the AI successfully posts an in-group reply. Today only `is_internal_pool=true` customers get Leads (via the F4 fast path on monitor hit); paying customers pay `$0.05` per AI reply but get nothing in their CRM, contradicting the landing copy contract:

> "On intent hit, AI posts a contextual reply IN the source group … A Lead row materialises — pre-assigned to the salesperson who owns that TG account, source-group attribution intact." — [landing/src/sections/ProductAIAssistant.tsx](../../landing/src/sections/ProductAIAssistant.tsx)

Out of scope:
- Internal-pool F4 path (`_upsert_internal_pool_lead`) — unchanged.
- Passive `trigger_ai` 2-bot shill path (`_dispatch_ai_shill`) — by design, that's a social-proof simulation, not direct user engagement.
- Sales claim flow (`/sales/leads/{id}/view`) — already works, the new Leads reuse it without change.
- Landing copy edits — current promise matches what this spec ships.
- Charging `ai_marketing_lead_created` for the F4 internal-pool path — it already charges correctly on its own.

## Locked Decisions

User-confirmed in brainstorming on 2026-05-26:

1. **Trigger point** — Lead is created when `_execute_active_marketing` successfully sends the in-group reply (after the `send_message` await resolves and `hit.status='handled'` is committed). Not on every hit. Not in passive mode. Not for `trigger_ai` shill.
2. **Dedup** — Same `(account_id, telegram_user_id)` pair = same Lead. Repeat hits bump `last_interaction_at` and append a `LeadInteraction` row; they do NOT create a new Lead and do NOT re-charge `ai_marketing_lead_created`.
3. **Interaction history** — Each successful reply logs two `LeadInteraction` rows (the user's hitting message as `inbound`, the AI's reply as `outbound`). Both per first-touch AND every subsequent re-touch.
4. **Pre-assign** — If the listening account has `assigned_to_sales_user_id` set and `assigned_to_sales_kind ∈ ('platform', 'customer')`, the new Lead lands pre-claimed in that sales inbox (mirrors F4 internal-pool behavior).
5. **Charge** — On truly-new Lead rows only, fire `feature_billing.charge(slug='ai_marketing_lead_created', units=1, idempotency_key=f'feat:ai_marketing_lead_created:{lead.id}')`. Repeat hits do not re-charge.
6. **Skip rules** — Skip the helper if any of:
   - Account has no `customer_id` (= platform-internal account, no tenant to charge)
   - `monitor.customer_id IS NULL` (sales-owned or global rule — same as F4 carve-out)
   - Note: do NOT skip on `customer.is_internal_pool=true`. The F4 fast path only runs in passive mode; an internal-pool customer with an active monitor must still get a Lead. The dedup-by-(account_id, telegram_user_id) at the top of the helper handles any race with F4: if F4 already inserted the Lead at hit time, the helper finds it and just bumps `last_interaction_at` + logs interactions.
7. **Failure tolerance** — Inner try/except wraps the whole helper. Failure logs a warning and returns; it never blocks the reply that just sent successfully, and it never re-raises into `_execute_active_marketing`. Billing failures already use idempotency keys, so retries are safe.

## Architecture

One new helper on `ListenerService`, parallel to the existing `_upsert_internal_pool_lead`:

```
_execute_active_marketing(...)
  └─ send_message(...) ✓
  └─ hit.status = 'handled' ✓
  └─ commit ✓
  └─ feature_billing.charge('ai_marketing_group_reply', ...) ✓  ← existing
  └─ _upsert_lead_for_customer_reply(...)                       ← NEW
       ├─ resolve account → customer_id, sales pre-assign
       ├─ skip-rule check (no cust / is_internal_pool / global monitor)
       ├─ Lead upsert by (account_id, telegram_user_id)
       ├─ LeadInteraction × 2 (inbound + outbound)
       └─ feature_billing.charge('ai_marketing_lead_created', ...) if NEW
```

The helper is a sibling to `_upsert_internal_pool_lead` and lives in the same file. It does NOT call the existing helper — they're separate code paths gated by `is_internal_pool`, so duplication of a few lines (Lead constructor, charge) is preferable to a clever-but-fragile shared method that has to branch on customer type.

## Data Flow

For a single customer-owned active monitor hit that survives keyword + group + cooldown + circuit breaker:

```
listener: message arrives
  → _check_match passes
  → KeywordHit row created (status='pending')
  → _execute_active_marketing
       sleep(random 30-180s)
       _generate_ai_reply → LLM → reply_text
       send_message(reply_to_message_id=...) → Telegram ACK
       hit.status='handled', commit
       charge ai_marketing_group_reply $0.05 (existing)
       _upsert_lead_for_customer_reply
         lookup Lead by (acc.id, msg.from_user.id)
         IF new:
           insert Lead(
             account_id=acc.id,
             telegram_user_id=user.id,
             username=user.username,
             first_name=user.first_name,
             status='new',
             source='monitor',
             customer_id=acc.customer_id,
             industry=monitor.industry or customer.industry,
             tags_json=json.dumps([f"monitor:{monitor.keyword}"]),
             notes=f"From '{chat_title}': {snippet[:200]}",
             last_interaction_at=now,
             assigned_to_user_id=acc.assigned_to_sales_user_id if kind in ('platform','customer') else None,
             claimed_at=now if pre-assigned else None,
           )
           commit, refresh
           charge ai_marketing_lead_created $0.50
         ELSE:
           lead.last_interaction_at = now
           commit
         insert LeadInteraction(lead_id, direction='inbound',  content=msg.text)
         insert LeadInteraction(lead_id, direction='outbound', content=reply_text)
         commit
```

## File Changes

- Modify: `backend/app/services/listener_service.py`
  - Add `_upsert_lead_for_customer_reply(self, session, monitor, message, reply_text)` after the existing `_upsert_internal_pool_lead`.
  - Add `_log_lead_interactions(self, session, lead_id, inbound_text, outbound_text)` next to it.
  - Modify `_execute_active_marketing` to call the helper inside its try-block, right after the `ai_marketing_group_reply` charge.
  - Pass `reply_text` from the caller so we can log the outbound interaction without re-deriving anything.
- Create: `backend/tests/services/test_lead_materialization_on_reply.py`
  - Three cases (see Testing).
- No schema changes — `Lead` and `LeadInteraction` models already carry every field needed.

## Testing

Vitest-equivalent (`pytest` + an async harness). Each test stubs the upstream `_generate_ai_reply` and the Pyrogram `send_message` so the reply succeeds deterministically without hitting LLM / Telegram. Each test asserts against the real DB.

1. **`test_new_lead_with_pre_assign_and_charge`** — Customer-owned active monitor, account has `assigned_to_sales_user_id=99, assigned_to_sales_kind='customer'`. After successful reply:
   - Exactly one new `lead` row with `customer_id`, `source='monitor'`, `assigned_to_user_id=99`, `claimed_at IS NOT NULL`, `industry` inherited.
   - Two `lead_interaction` rows (inbound + outbound) with correct `content`.
   - One `wallet_transaction` row matching `idempotency_key='feat:ai_marketing_lead_created:{lead.id}'` for $0.50.

2. **`test_repeat_hit_no_duplicate_lead_no_recharge`** — Same monitor, same sender, fired twice. After second reply:
   - Still exactly one `lead` row.
   - `last_interaction_at` bumped to the second time.
   - Four `lead_interaction` rows total (two per reply).
   - Only ONE `wallet_transaction` for `ai_marketing_lead_created` (the first); the second is correctly idempotent and not double-charged.

3. **`test_internal_pool_active_monitor_creates_lead_via_new_helper`** — Customer has `is_internal_pool=true` and uses an active monitor (where F4 doesn't fire). After active reply succeeds:
   - Exactly one new `lead` row created by the new helper (F4 was not invoked because mode='active'). Same shape as test 1 (`customer_id`, `industry`, interactions, pre-assign if applicable). This proves the helper covers the gap F4 leaves in active mode for internal-pool customers.

5. **`test_dedup_with_existing_f4_lead`** — Pre-seed a Lead row for `(account_id, telegram_user_id)` simulating an earlier F4 insert. Then fire an active monitor reply for the same pair. After:
   - Still exactly ONE Lead row (same id). `last_interaction_at` bumped to the new time.
   - Two new `lead_interaction` rows (this reply's inbound + outbound), preserving the pre-existing ones.
   - No new `ai_marketing_lead_created` charge (because it's not a new row).

4. **`test_account_without_customer_skipped`** — Account has `customer_id=NULL` (= platform internal). After active reply succeeds:
   - No Lead row created. No `ai_marketing_lead_created` charge. The reply itself still happens and `ai_marketing_group_reply` charge fires as before.

Run: `cd /var/tgsc/backend && pytest tests/services/test_lead_materialization_on_reply.py -v` (requires the backend pytest harness; ops note in case repo's test-run path differs from `pytest` direct invocation).

## Production Risk + Dependencies

- **Blocked end-to-end verification on the LLM step.** `_execute_active_marketing → _generate_ai_reply` calls Gemini (AI Studio key swapped in 2026-05-26 after Vertex account was restricted). If the Gemini consumer is re-suspended, the active path early-returns at `reply_text=None` before reaching the new helper. **Not in scope to fix** — the helper degrades gracefully (no Lead created, no overcharge).
- **No data migration.** Historical `KeywordHit` rows from before this lands will NOT retroactively get Leads — per brainstorming: those hits never actually produced an AI reply (the reply path was either chat_id-broken or LLM-blocked), so they shouldn't count as CRM interactions.
- **Wallet balance** — `_execute_active_marketing` does not pre-check wallet balance; it relies on `feature_billing.charge` rejecting on insufficient funds. Currently the reply ships first ($0.05 charge) and the lead-created charge ($0.50) can fail independently. If lead-created fails for insufficient funds, the Lead row still gets persisted (it was committed before the charge). This is acceptable: the customer got value (Lead in CRM), the charge will retry on next top-up via wallet reconciliation OR get written off; either way the data is consistent and idempotency_key prevents double-billing on retry.

## Done Definition

- New helper merged on `main`.
- Four unit tests passing in CI.
- One smoke run against a real customer monitor (after Vertex/Gemini stable) shows: keyword hit → AI reply sent → Lead row appears in customer's `/portal/leads` UI with correct industry + interaction history + pre-assign → sales user can `view` the lead and the claim semantics work as today.
- Audit-trail spot check: `customer_feature` table shows `ai_marketing_lead_created` charges matching the count of new Leads × $0.50.

After Done: the TG 营销助手 product flow per landing copy is end-to-end true, and the "post-Vertex-outage" verification can rerun and produce a green PASS.
