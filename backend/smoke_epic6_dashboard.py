"""Epic 6.0 smoke test — admin business-ops dashboard endpoints.

Hits all six endpoints, validates structure + sanity of aggregates. We don't
seed fresh fixtures here because Epic 1-5 smokes already left enough data in
the dev DB (customers, accounts, subscriptions, KB, leads).

Run:
    ADMIN_PW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
    docker exec -e ADMIN_PASSWORD="$ADMIN_PW" tgsc-backend-1 python3 /app/smoke_epic6_dashboard.py
"""
from __future__ import annotations

import os
import sys

import httpx

BASE = "http://localhost:8000/api/v1"
OK, FAIL = "PASS", "FAIL"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def step(name, ok, detail=""):
    marker = OK if ok else FAIL
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def main():
    if not ADMIN_PASSWORD:
        print("ADMIN_PASSWORD env not set"); sys.exit(1)

    client = httpx.Client(base_url=BASE, timeout=30)

    # Admin login
    r = client.post("/login/access-token", data={
        "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    step("admin login", r.status_code == 200)
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ── 1) /overview ──
    print("\n=== 1) /admin/dashboard/overview ===")
    r = client.get("/admin/dashboard/overview", headers=headers)
    step("overview 200", r.status_code == 200, f"HTTP {r.status_code}")
    d = r.json()
    for key in ("customers", "mrr_usd", "accounts", "leads",
                "knowledge_base_total", "source_groups_total", "pending_invoices"):
        step(f"has '{key}'", key in d)
    step("customers.by_status is dict", isinstance(d["customers"]["by_status"], dict))
    step("accounts has free/main_accounts/banned",
         all(k in d["accounts"] for k in ("free", "main_accounts", "banned")))
    print(f"  → customers={d['customers']['total']} mrr=${d['mrr_usd']} "
          f"accounts={d['accounts']['total']} leads={d['leads']['total']} "
          f"kb={d['knowledge_base_total']}")

    # ── 2) /customers ──
    print("\n=== 2) /admin/dashboard/customers ===")
    r = client.get("/admin/dashboard/customers?limit=10", headers=headers)
    step("customers 200", r.status_code == 200)
    rows = r.json()
    step("returns a list", isinstance(rows, list))
    if rows:
        c = rows[0]
        for k in ("id", "email", "status", "accounts", "kb_entries", "leads",
                  "main_account_bound"):
            step(f"row has '{k}'", k in c, f"row keys: {list(c.keys())[:6]}...")
        step("accounts has used/quota/pct",
             all(k in c["accounts"] for k in ("used", "quota", "pct")))
        print(f"  → top customer id={c['id']} acc={c['accounts']['used']}/{c['accounts']['quota']} "
              f"kb={c['kb_entries']} leads={c['leads']}")

    # ── 3) /lead-funnel ──
    print("\n=== 3) /admin/dashboard/lead-funnel ===")
    r = client.get("/admin/dashboard/lead-funnel?days=30", headers=headers)
    step("funnel 200", r.status_code == 200)
    f = r.json()
    step("has stages dict", isinstance(f["stages"], dict))
    for stage in ("new", "contacted", "replied", "interested", "converted", "closed"):
        step(f"stage '{stage}' present", stage in f["stages"])
    step("has conversion_rates_pct", "conversion_rates_pct" in f)
    print(f"  → total={f['total_leads']} stages={f['stages']}")

    # Per-customer drill-down
    if rows:
        cid = rows[0]["id"]
        r = client.get(f"/admin/dashboard/lead-funnel?customer_id={cid}&days=30", headers=headers)
        step(f"funnel for customer {cid} ok", r.status_code == 200,
             f"HTTP {r.status_code}")
        step("customer_id echoed", r.json()["customer_id"] == cid)

    # ── 4) /account-pool ──
    print("\n=== 4) /admin/dashboard/account-pool ===")
    r = client.get("/admin/dashboard/account-pool", headers=headers)
    step("pool 200", r.status_code == 200)
    p = r.json()
    step("has by_status", isinstance(p["by_status"], dict))
    step("has by_role", isinstance(p["by_role"], dict))
    step("has free_for_allocation", isinstance(p["free_for_allocation"], int))
    step("has health_score_buckets (5 buckets)",
         isinstance(p["health_score_buckets"], dict) and len(p["health_score_buckets"]) == 5)
    print(f"  → roles={p['by_role']}  free={p['free_for_allocation']}")

    # ── 5) /llm-usage ──
    print("\n=== 5) /admin/dashboard/llm-usage ===")
    r = client.get("/admin/dashboard/llm-usage?days=14", headers=headers)
    step("llm 200", r.status_code == 200)
    u = r.json()
    step("has total_cost_usd", "total_cost_usd" in u)
    step("daily is list", isinstance(u["daily"], list))
    step("by_source is dict", isinstance(u["by_source"], dict))
    step("by_provider is dict", isinstance(u["by_provider"], dict))
    print(f"  → 14-day total=${u['total_cost_usd']}  "
          f"sources={list(u['by_source'].keys())}  "
          f"days_with_data={len(u['daily'])}")

    # ── 6) /handover-stats ──
    print("\n=== 6) /admin/dashboard/handover-stats ===")
    r = client.get("/admin/dashboard/handover-stats?days=30", headers=headers)
    step("handover 200", r.status_code == 200)
    h = r.json()
    for k in ("notified", "claimed_in_time", "handover_link_sent",
              "converted", "claim_rate_pct", "escalation_rate_pct",
              "conversion_rate_pct"):
        step(f"has '{k}'", k in h)
    print(f"  → notified={h['notified']} claimed={h['claimed_in_time']} "
          f"escalated={h['handover_link_sent']} converted={h['converted']}")

    # ── 7) Non-admin / unauth rejected ──
    print("\n=== 7) Unauth & non-admin rejected ===")
    r = client.get("/admin/dashboard/overview")
    step("no token → 401/403", r.status_code in (401, 403), f"HTTP {r.status_code}")

    print("\n[ALL PASSED]")


if __name__ == "__main__":
    main()
