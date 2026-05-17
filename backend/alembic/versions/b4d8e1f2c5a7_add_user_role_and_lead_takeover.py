"""add user.role and lead takeover columns

Revision ID: b4d8e1f2c5a7
Revises: a7e6c2b9f1a3
Create Date: 2026-05-17 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = 'b4d8e1f2c5a7'
down_revision: Union[str, Sequence[str], None] = 'a7e6c2b9f1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user 表加 role
    op.add_column(
        'user',
        sa.Column(
            'role',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default='admin',
        ),
    )
    op.create_index('ix_user_role', 'user', ['role'])
    # 把所有已存在的 user 标为 admin（server_default 只对新行生效）
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE role IS NULL OR role = '';")

    # 2. lead 表加接管相关字段
    op.add_column(
        'lead',
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'lead',
        sa.Column(
            'ai_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )
    op.add_column(
        'lead',
        sa.Column('ai_draft', sa.Text(), nullable=True),
    )
    op.add_column(
        'lead',
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
    )

    op.create_index(
        'ix_lead_assigned_to_user_id',
        'lead',
        ['assigned_to_user_id'],
    )
    op.create_foreign_key(
        'fk_lead_assigned_to_user_id',
        'lead',
        'user',
        ['assigned_to_user_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_lead_assigned_to_user_id', 'lead', type_='foreignkey')
    op.drop_index('ix_lead_assigned_to_user_id', table_name='lead')
    op.drop_column('lead', 'claimed_at')
    op.drop_column('lead', 'ai_draft')
    op.drop_column('lead', 'ai_enabled')
    op.drop_column('lead', 'assigned_to_user_id')

    op.drop_index('ix_user_role', table_name='user')
    op.drop_column('user', 'role')
