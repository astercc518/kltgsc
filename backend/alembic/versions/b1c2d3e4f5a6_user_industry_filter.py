"""add user.industry_filter_json (Phase F3)

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-05-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('user')}
    if 'industry_filter_json' not in cols:
        op.add_column(
            'user',
            sa.Column('industry_filter_json', sa.String(length=500),
                      nullable=False, server_default='[]'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('user')}
    if 'industry_filter_json' in cols:
        op.drop_column('user', 'industry_filter_json')
