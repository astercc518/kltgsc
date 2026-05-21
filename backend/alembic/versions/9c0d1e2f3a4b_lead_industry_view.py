"""add lead.industry / category / view_count (Epic D)

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-05-21

Adds three columns to the lead table so the sales workbench can filter
by industry/category and track view consumption (lead view = billable
event against the sales personal wallet).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c0d1e2f3a4b'
down_revision: Union[str, Sequence[str], None] = '8b9c0d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('lead')}
    if 'industry' not in cols:
        op.add_column('lead', sa.Column('industry', sa.String(length=50), nullable=True))
        op.create_index('ix_lead_industry', 'lead', ['industry'])
    if 'category' not in cols:
        op.add_column('lead', sa.Column('category', sa.String(length=50), nullable=True))
        op.create_index('ix_lead_category', 'lead', ['category'])
    if 'view_count' not in cols:
        op.add_column('lead', sa.Column('view_count', sa.Integer(),
                                         nullable=False, server_default='0'))

    # Backfill industry from the parent customer.industry where it's set
    # so existing leads pre-populated under Epic 4 KB / customer onboarding
    # immediately become filterable.
    op.execute("""
        UPDATE lead l
        SET industry = c.industry
        FROM customer c
        WHERE l.customer_id = c.id
          AND c.industry IS NOT NULL
          AND l.industry IS NULL
    """)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('lead')}
    if 'view_count' in cols:
        op.drop_column('lead', 'view_count')
    if 'category' in cols:
        try:
            op.drop_index('ix_lead_category', table_name='lead')
        except Exception:
            pass
        op.drop_column('lead', 'category')
    if 'industry' in cols:
        try:
            op.drop_index('ix_lead_industry', table_name='lead')
        except Exception:
            pass
        op.drop_column('lead', 'industry')
