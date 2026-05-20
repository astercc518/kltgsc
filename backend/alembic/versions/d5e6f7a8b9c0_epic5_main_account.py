"""Epic 5: main account + personal KB + lead handover

Revision ID: d5e6f7a8b9c0
Revises: a3b4c5d6e7f8
Create Date: 2026-05-18

Unified migration covering all three Epic 5 sub-epics:

  5.0 — Main account scan-login + isolation
       customer.main_account_id  FK → account
       account.is_customer_main  bool flag (fast filter)
       account.session_string_encrypted  bool flag (string-at-rest crypto)

  5.1 — Chat history → personal KB
       group_message.customer_id  FK → customer (tenant tag)
       ai_knowledge_base.source_main_account_id  FK → account (audit)
       ai_knowledge_base.customer_id index (likely already present, IF NOT EXISTS)

  5.2 — Main-account notification + handover + timeout
       customer.handover_group_link        VARCHAR(256)
       customer.takeover_timeout_minutes   INTEGER default 5
       customer.notify_main_account        BOOLEAN default true
       lead.main_account_notified_at       TIMESTAMP
       lead.handover_link_sent_at          TIMESTAMP
       lead.takeover_deadline              TIMESTAMP (denormalized for race-safe)

All idempotent via IF NOT EXISTS / ADD COLUMN IF NOT EXISTS pattern used in
prior Epic 1/2/3 migrations.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 5.0 — main account + isolation ──
    op.execute("ALTER TABLE account ADD COLUMN IF NOT EXISTS is_customer_main BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE account ADD COLUMN IF NOT EXISTS session_string_encrypted BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_account_is_customer_main ON account(is_customer_main)")

    op.execute("""
        ALTER TABLE customer
        ADD COLUMN IF NOT EXISTS main_account_id INTEGER
        REFERENCES account(id) ON DELETE SET NULL
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_main_account_id ON customer(main_account_id)")

    # ── 5.1 — chat history → personal KB ──
    op.execute("""
        ALTER TABLE group_message
        ADD COLUMN IF NOT EXISTS customer_id INTEGER
        REFERENCES customer(id) ON DELETE CASCADE
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_group_message_customer_id ON group_message(customer_id)")

    op.execute("""
        ALTER TABLE ai_knowledge_base
        ADD COLUMN IF NOT EXISTS source_main_account_id INTEGER
        REFERENCES account(id) ON DELETE SET NULL
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_knowledge_base_source_main_account_id "
               "ON ai_knowledge_base(source_main_account_id)")
    # customer_id index on ai_knowledge_base added in Epic 1 migration e1a2b3c4d5f6 — skip

    # ── 5.2 — notification + handover + timeout ──
    op.execute("ALTER TABLE customer ADD COLUMN IF NOT EXISTS handover_group_link VARCHAR(256)")
    op.execute("ALTER TABLE customer ADD COLUMN IF NOT EXISTS takeover_timeout_minutes INTEGER NOT NULL DEFAULT 5")
    op.execute("ALTER TABLE customer ADD COLUMN IF NOT EXISTS notify_main_account BOOLEAN NOT NULL DEFAULT TRUE")

    op.execute("ALTER TABLE lead ADD COLUMN IF NOT EXISTS main_account_notified_at TIMESTAMP")
    op.execute("ALTER TABLE lead ADD COLUMN IF NOT EXISTS handover_link_sent_at TIMESTAMP")
    op.execute("ALTER TABLE lead ADD COLUMN IF NOT EXISTS takeover_deadline TIMESTAMP")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lead_takeover_deadline ON lead(takeover_deadline)")


def downgrade() -> None:
    # 5.2
    op.execute("DROP INDEX IF EXISTS ix_lead_takeover_deadline")
    for col in ("takeover_deadline", "handover_link_sent_at", "main_account_notified_at"):
        op.execute(f"ALTER TABLE lead DROP COLUMN IF EXISTS {col}")
    for col in ("notify_main_account", "takeover_timeout_minutes", "handover_group_link"):
        op.execute(f"ALTER TABLE customer DROP COLUMN IF EXISTS {col}")

    # 5.1
    op.execute("DROP INDEX IF EXISTS ix_ai_knowledge_base_source_main_account_id")
    op.execute("ALTER TABLE ai_knowledge_base DROP COLUMN IF EXISTS source_main_account_id")
    op.execute("DROP INDEX IF EXISTS ix_group_message_customer_id")
    op.execute("ALTER TABLE group_message DROP COLUMN IF EXISTS customer_id")

    # 5.0
    op.execute("DROP INDEX IF EXISTS ix_customer_main_account_id")
    op.execute("ALTER TABLE customer DROP COLUMN IF EXISTS main_account_id")
    op.execute("DROP INDEX IF EXISTS ix_account_is_customer_main")
    op.execute("ALTER TABLE account DROP COLUMN IF EXISTS session_string_encrypted")
    op.execute("ALTER TABLE account DROP COLUMN IF EXISTS is_customer_main")
