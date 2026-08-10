"""Backfill auto-enable of AI marketing feature flags on active subs."""
import sys
sys.path.insert(0, "/app")
from sqlmodel import Session, select
from sqlalchemy import text
from app.core.db import engine
from app.models.customer import Customer
from app.services import feature_billing as fb

SLUGS = ("ai_marketing_assistant", "ai_marketing_group_reply", "ai_marketing_lead_created")

with Session(engine) as s:
    customers = list(s.exec(
        select(Customer).where(
            Customer.subscription_status == "active",
            Customer.plan.is_not(None),
        ).order_by(Customer.id)
    ).all())
    print(f"[scan] {len(customers)} active-sub customers")
    touched = 0
    for c in customers:
        # Check which slugs are missing or disabled
        existing = s.exec(text(
            "SELECT feature_slug, enabled FROM customer_feature WHERE customer_id = :cid"
        ).bindparams(cid=c.id)).all()
        existing_map = {row[0]: row[1] for row in existing}
        for slug in SLUGS:
            if not existing_map.get(slug, False):
                try:
                    fb.upsert_customer_feature(
                        s, c.id, slug, enabled=True,
                        notes=f"backfill: auto-enable on active {c.plan} plan",
                    )
                    touched += 1
                    print(f"  enable cust#{c.id:>3} {slug}")
                except Exception as e:
                    print(f"  FAIL cust#{c.id} {slug}: {type(e).__name__}: {e}")
    print(f"[done] {touched} feature rows enabled/upserted")
