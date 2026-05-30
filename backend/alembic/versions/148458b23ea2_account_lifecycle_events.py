"""account_lifecycle_events

Revision ID: 148458b23ea2
Revises: 41f948211e5f
Create Date: 2026-05-30

记录账号状态变化事件 (active / session_invalid / banned), 用于:
- A/B 实验 kick_rate 指标
- 容量监控 / 池子健康度
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from typing import Sequence, Union

revision: str = "148458b23ea2"
down_revision: Union[str, Sequence[str], None] = "41f948211e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_lifecycle_events",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("chat_id", sa.BigInteger, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_acc_lifecycle_account_time",
        "account_lifecycle_events", ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_acc_lifecycle_account_time", table_name="account_lifecycle_events")
    op.drop_table("account_lifecycle_events")
