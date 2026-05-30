"""group_discovery_tables

Revision ID: 160a46df89f9
Revises: cef110414bf7
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from typing import Sequence, Union

revision: str = "160a46df89f9"
down_revision: Union[str, Sequence[str], None] = "cef110414bf7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovered_group",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("chat_username", sa.Text, nullable=True),   # @groupname (public group)
        sa.Column("chat_link", sa.Text, nullable=True),       # t.me/+xxx (private invite link)
        sa.Column("chat_id", sa.BigInteger, nullable=True),   # known chat_id (public group)
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("members_count", sa.Integer, nullable=True),
        sa.Column("daily_messages", sa.Integer, nullable=True),
        sa.Column("category", sa.Text, nullable=True),        # industry category (LLM inferred)
        sa.Column("source", sa.Text, nullable=False),         # 'tgstat' | 'tme_search' | 'manual'
        sa.Column("source_query", sa.Text, nullable=True),    # keyword that triggered the search
        sa.Column("score", sa.Float, nullable=True),          # composite score 0-100
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        # status: pending | approved | rejected | failed_join
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("customer_user.id"), nullable=True),
    )
    op.create_index(
        "idx_discovered_group_customer_status",
        "discovered_group", ["customer_id", "status"],
    )
    op.create_unique_constraint(
        "uq_discovered_group_customer_link",
        "discovered_group",
        ["customer_id", "chat_link"],
    )

    op.create_table(
        "discovery_blacklist",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("chat_link", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_discovery_blacklist_customer_link",
        "discovery_blacklist",
        ["customer_id", "chat_link"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_discovery_blacklist_customer_link",
                       "discovery_blacklist", type_="unique")
    op.drop_table("discovery_blacklist")
    op.drop_constraint("uq_discovered_group_customer_link",
                       "discovered_group", type_="unique")
    op.drop_index("idx_discovered_group_customer_status", table_name="discovered_group")
    op.drop_table("discovered_group")
