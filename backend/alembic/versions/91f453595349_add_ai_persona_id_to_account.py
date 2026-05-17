"""add ai_persona_id to account

Revision ID: 91f453595349
Revises: 5339f2871fae
Create Date: 2026-04-30 07:10:31.959066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '91f453595349'
down_revision: Union[str, Sequence[str], None] = '5339f2871fae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_persona_id column to account table.

    保持极简：只加列、加索引、加外键。不动其他无关索引，避免副作用。
    """
    op.add_column(
        'account',
        sa.Column('ai_persona_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f('ix_account_ai_persona_id'),
        'account',
        ['ai_persona_id'],
        unique=False,
    )
    op.create_foreign_key(
        'fk_account_ai_persona_id',
        'account',
        'ai_persona',
        ['ai_persona_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_account_ai_persona_id', 'account', type_='foreignkey')
    op.drop_index(op.f('ix_account_ai_persona_id'), table_name='account')
    op.drop_column('account', 'ai_persona_id')
