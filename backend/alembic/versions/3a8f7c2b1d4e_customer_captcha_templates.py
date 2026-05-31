"""customer_captcha_templates

Revision ID: 3a8f7c2b1d4e
Revises: 77381edfa35b
Create Date: 2026-05-31

Phase 10: add captcha_join_template / captcha_intro_template columns to the
customer table. These feed join_orchestrator._customer_join_template /
_customer_intro_template (Phase 9 placeholder stubs) so that text_qa and
admin_dm captcha handlers can use customer-tuned templates instead of the
built-in fallbacks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8f7c2b1d4e'
down_revision: Union[str, Sequence[str], None] = '77381edfa35b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customer",
        sa.Column("captcha_join_template", sa.Text, nullable=True),
    )
    op.add_column(
        "customer",
        sa.Column("captcha_intro_template", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customer", "captcha_intro_template")
    op.drop_column("customer", "captcha_join_template")
