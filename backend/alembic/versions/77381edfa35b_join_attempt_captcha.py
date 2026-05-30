"""join_attempt_captcha

Revision ID: 77381edfa35b
Revises: 160a46df89f9
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '77381edfa35b'
down_revision: Union[str, Sequence[str], None] = '160a46df89f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "join_attempt",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customer.id"), nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("account.id"), nullable=False),
        sa.Column("discovered_group_id", sa.BigInteger,
                  sa.ForeignKey("discovered_group.id"), nullable=True),
        # discovered_group_id 可空: 也允许手工触发 join
        sa.Column("chat_link", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        # pending → joining → captcha → joined / failed / abandoned
        sa.Column("captcha_type", sa.Text, nullable=True),
        # inline_button | text_qa | vision | admin_dm | unknown
        sa.Column("captcha_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_join_attempt_status",
        "join_attempt", ["status", "updated_at"],
    )

    op.create_table(
        "captcha_event",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("join_attempt_id", sa.BigInteger,
                  sa.ForeignKey("join_attempt.id"), nullable=False),
        sa.Column("handler", sa.Text, nullable=False),
        sa.Column("input_summary", sa.Text, nullable=True),
        # e.g. "Click 'I am human' button" or "Q: 你怎么知道这群?"
        sa.Column("output_summary", sa.Text, nullable=True),
        # e.g. "Clicked button" or "Answered: 朋友推荐"
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_captcha_event_attempt",
        "captcha_event", ["join_attempt_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_captcha_event_attempt", table_name="captcha_event")
    op.drop_table("captcha_event")
    op.drop_index("idx_join_attempt_status", table_name="join_attempt")
    op.drop_table("join_attempt")
