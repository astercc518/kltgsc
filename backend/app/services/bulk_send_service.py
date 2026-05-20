"""
Bulk Send service — batch creation, CSV parsing, cost preview (W2).

Sending worker / wallet charging lives in a later weekly milestone (W3).
This module is intentionally read/write on DB only; no Telegram I/O.

参考 docs/planning/bulk_send_spec.md §3.1, §3.2
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Optional

from sqlmodel import Session, select

from app.models.bulk_send import (
    BulkBatch, BulkTarget, BulkTemplateVariant,
    BATCH_DRAFT, TARGET_PENDING, TARGET_SKIPPED,
)
from app.models.customer import Customer
from app.models.wallet import calculate_tier_unit_price_cents
from app.services.wallet_service import get_or_create_wallet


# ── Errors ────────────────────────────────────────────────────────────


class BulkSendError(Exception):
    """Validation / state errors surfaced to API as 400."""


# ── CSV parsing ───────────────────────────────────────────────────────


# 简化的电话号格式：+ 开头，6-20 位数字
PHONE_RE = re.compile(r"^\+?\d{6,20}$")
# TG username：4-32 字符 [a-zA-Z0-9_]
USERNAME_RE = re.compile(r"^@?([a-zA-Z][a-zA-Z0-9_]{3,31})$")
# 纯数字 user_id：6-15 位
TG_USER_ID_RE = re.compile(r"^\d{6,15}$")


_HEADER_ALIASES = {
    "tg_user_id": {"tg_user_id", "user_id", "userid", "tguserid", "id"},
    "tg_username": {"tg_username", "username", "tgusername", "handle"},
    "phone": {"phone", "phone_number", "phonenumber", "mobile", "tel"},
    "display_name": {"name", "display_name", "displayname", "first_name", "fullname"},
    "country": {"country", "country_code", "cc", "iso"},
}


def _normalize_header(h: str) -> Optional[str]:
    h = h.strip().lower().replace("-", "_").replace(" ", "_")
    for canonical, aliases in _HEADER_ALIASES.items():
        if h in aliases:
            return canonical
    return None


def parse_targets_csv(csv_text: str, customer_id: int) -> tuple[list[dict], dict]:
    """Parse CSV text into target dicts.

    Accepts:
        - CSV with header: detected aliases per _HEADER_ALIASES
        - 单列无 header：自动判断每行是 phone / username / user_id

    Returns (rows, summary) where rows is a list of dicts with keys among
    {tg_user_id, tg_username, phone, display_name, country, extra_json}, and
    summary has {raw_count, parsed_count, invalid_count, dedup_in_csv}.

    Does NOT touch DB. customer_id is unused here but kept for future
    cross-batch dedup hooks.
    """
    text = (csv_text or "").strip()
    if not text:
        raise BulkSendError("csv_text is empty")

    raw_lines = [ln for ln in text.splitlines() if ln.strip()]
    if not raw_lines:
        raise BulkSendError("csv_text has no non-empty lines")

    # Detect header: if first line splits to >=2 cells and at least one matches an alias
    first = next(csv.reader(io.StringIO(raw_lines[0])))
    header_indices = {}
    has_header = False
    if len(first) >= 2:
        for i, h in enumerate(first):
            canonical = _normalize_header(h)
            if canonical:
                header_indices[canonical] = i
                has_header = True

    data_lines = raw_lines[1:] if has_header else raw_lines

    rows: list[dict] = []
    invalid = 0
    seen_keys: set[tuple] = set()
    dedup_in_csv = 0

    reader = csv.reader(io.StringIO("\n".join(data_lines)))
    for cells in reader:
        if not cells:
            continue
        row: dict = {}

        if has_header:
            for canonical, idx in header_indices.items():
                if idx < len(cells):
                    val = cells[idx].strip()
                    if val:
                        row[canonical] = val
            # Pack non-mapped columns into extra_json
            mapped_idx = set(header_indices.values())
            extras = {
                first[i].strip(): cells[i].strip()
                for i in range(min(len(first), len(cells)))
                if i not in mapped_idx and cells[i].strip()
            }
            if extras:
                row["extra_json"] = json.dumps(extras, ensure_ascii=False)
        else:
            # No header — guess single value. Order matters:
            #   1. '+'-prefixed or 11+ digit → phone (real E.164 is ≥11 digits)
            #   2. 6-10 digit → tg_user_id (TG ids are typically 7-10 digits)
            #   3. @username or bare identifier → tg_username
            val = cells[0].strip()
            if not val:
                continue
            if val.startswith("+") and PHONE_RE.match(val):
                row["phone"] = val
            elif val.isdigit() and len(val) >= 11 and PHONE_RE.match(val):
                row["phone"] = f"+{val}"
            elif TG_USER_ID_RE.match(val):
                row["tg_user_id"] = int(val)
            elif USERNAME_RE.match(val):
                m = USERNAME_RE.match(val)
                row["tg_username"] = m.group(1)
            else:
                invalid += 1
                continue

        # Normalize the recognised fields one more pass
        row = _normalize_row(row)
        if row is None:
            invalid += 1
            continue

        # Dedup within this CSV: prefer tg_user_id > tg_username > phone
        dedup_key = (
            ("uid", row.get("tg_user_id"))
            if row.get("tg_user_id") else
            ("un", row.get("tg_username", "").lower())
            if row.get("tg_username") else
            ("ph", row.get("phone", ""))
        )
        if not dedup_key[1]:
            invalid += 1
            continue
        if dedup_key in seen_keys:
            dedup_in_csv += 1
            continue
        seen_keys.add(dedup_key)
        rows.append(row)

    return rows, {
        "raw_count": len(data_lines),
        "parsed_count": len(rows),
        "invalid_count": invalid,
        "dedup_in_csv": dedup_in_csv,
        "has_header": has_header,
    }


def _normalize_row(row: dict) -> Optional[dict]:
    """Coerce types + strip + require at least one identifier."""
    out: dict = {}
    if v := row.get("tg_user_id"):
        try:
            uid = int(str(v).strip())
            if 100000 <= uid <= 10**13:
                out["tg_user_id"] = uid
        except (TypeError, ValueError):
            pass
    if v := row.get("tg_username"):
        m = USERNAME_RE.match(str(v).strip())
        if m:
            out["tg_username"] = m.group(1)
    if v := row.get("phone"):
        ph = str(v).strip()
        if not ph.startswith("+"):
            ph = "+" + ph.lstrip("0+")
        if PHONE_RE.match(ph):
            out["phone"] = ph
    if v := row.get("display_name"):
        out["display_name"] = str(v).strip()[:120]
    if v := row.get("country"):
        c = str(v).strip().upper()
        if 2 <= len(c) <= 3:
            out["country"] = c
    if extra := row.get("extra_json"):
        out["extra_json"] = extra

    if not (out.get("tg_user_id") or out.get("tg_username") or out.get("phone")):
        return None
    return out


# ── Cost preview ──────────────────────────────────────────────────────


def preview_cost_cents(
    session: Session,
    customer_id: int,
    target_count: int,
) -> dict:
    """Estimate the cost of sending `target_count` messages right now.

    Tiers cross thresholds based on customer's wallet.total_spent_cents at the
    start. Crossing tiers mid-batch is approximated by walking the tier table.
    The actual wallet charge in W3 uses per-message tier at send time.
    """
    if target_count <= 0:
        raise BulkSendError("target_count must be positive")

    wallet = get_or_create_wallet(session, customer_id)
    spent_cents = wallet.total_spent_cents
    balance_cents = wallet.balance_cents

    remaining = target_count
    total_cents = 0
    cursor = spent_cents
    breakdown = []

    # Tier thresholds in cents (mirrors models/wallet.py::calculate_tier_unit_price_cents)
    tier_caps_cents = [
        (1500_00, 15),  # < $1500 spent → $0.15/msg
        (6500_00, 10),
        (16500_00, 7),
    ]
    floor_price = 5

    while remaining > 0:
        next_cap, unit = None, floor_price
        for cap, price in tier_caps_cents:
            if cursor < cap:
                next_cap, unit = cap, price
                break

        if next_cap is None:
            # already in the floor tier
            n = remaining
        else:
            # how many full-priced msgs fit before crossing into next tier
            available_at_this_tier_cents = next_cap - cursor
            max_msgs = max(1, available_at_this_tier_cents // unit)
            n = min(remaining, int(max_msgs))

        chunk_cost = n * unit
        breakdown.append({"count": n, "unit_cents": unit, "subtotal_cents": chunk_cost})
        total_cents += chunk_cost
        cursor += chunk_cost
        remaining -= n

    return {
        "target_count": target_count,
        "current_tier_unit_cents": calculate_tier_unit_price_cents(spent_cents),
        "total_cost_cents": total_cents,
        "balance_cents": balance_cents,
        "balance_sufficient": balance_cents >= total_cents,
        "shortfall_cents": max(0, total_cents - balance_cents),
        "breakdown": breakdown,
    }


# ── Batch create ──────────────────────────────────────────────────────


def create_batch_draft(
    session: Session,
    customer: Customer,
    name: str,
    message_template: str,
    csv_text: Optional[str],
    variants: list[str],
    min_delay_sec: int = 30,
    max_delay_sec: int = 180,
) -> tuple[BulkBatch, dict]:
    """Create a draft batch and persist its targets + variants in one transaction.

    Returns (batch, parse_summary). Variants are optional; the batch can't be
    started later without ≥ 5 variants (enforced in W3 at /start).

    Targets that collide with the cross-batch UNIQUE(customer_id, tg_user_id)
    constraint are skipped (status=skipped) rather than failing the whole batch.
    """
    if min_delay_sec > max_delay_sec:
        raise BulkSendError("min_delay_sec must be <= max_delay_sec")

    # 1) Parse CSV (may raise BulkSendError)
    parsed: list[dict] = []
    parse_summary: dict = {"raw_count": 0, "parsed_count": 0, "invalid_count": 0, "dedup_in_csv": 0}
    if csv_text:
        parsed, parse_summary = parse_targets_csv(csv_text, customer.id)

    # 2) Estimate cost up-front (uses pre-batch wallet snapshot)
    cost = preview_cost_cents(session, customer.id, max(1, len(parsed)))

    # 3) Insert batch
    batch = BulkBatch(
        customer_id=customer.id,
        name=name.strip(),
        message_template=message_template,
        status=BATCH_DRAFT,
        total_targets=len(parsed),
        estimated_unit_price_cents=cost["current_tier_unit_cents"],
        estimated_total_cents=cost["total_cost_cents"],
        min_delay_sec=min_delay_sec,
        max_delay_sec=max_delay_sec,
    )
    session.add(batch)
    session.flush()  # need batch.id for FKs below

    # 4) Insert variants
    for content in variants or []:
        content = (content or "").strip()
        if not content:
            continue
        session.add(BulkTemplateVariant(batch_id=batch.id, content=content))

    # 5) Insert targets, treating cross-batch dedup as skip
    skipped_dedup = 0
    existing_uids = set()
    if parsed:
        candidate_uids = [r["tg_user_id"] for r in parsed if r.get("tg_user_id")]
        if candidate_uids:
            existing_uids = set(
                session.exec(
                    select(BulkTarget.tg_user_id).where(
                        BulkTarget.customer_id == customer.id,
                        BulkTarget.tg_user_id.in_(candidate_uids),
                    )
                ).all()
            )

    for row in parsed:
        status = TARGET_PENDING
        reason = None
        if row.get("tg_user_id") and row["tg_user_id"] in existing_uids:
            status = TARGET_SKIPPED
            reason = "dedup_cross_batch"
            skipped_dedup += 1
        session.add(BulkTarget(
            batch_id=batch.id,
            customer_id=customer.id,
            tg_user_id=row.get("tg_user_id"),
            tg_username=row.get("tg_username"),
            phone=row.get("phone"),
            display_name=row.get("display_name"),
            country=row.get("country"),
            extra_json=row.get("extra_json"),
            status=status,
            failed_reason=reason,
        ))

    batch.skipped_count = skipped_dedup
    session.add(batch)
    session.commit()
    session.refresh(batch)

    parse_summary["skipped_dedup_cross_batch"] = skipped_dedup
    parse_summary["cost"] = cost
    return batch, parse_summary
