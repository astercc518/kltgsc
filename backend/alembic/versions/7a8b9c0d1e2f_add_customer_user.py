"""add customer_user table + customer.seat_used (Epic C1)

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-05-21

customer_user is the sub-user (sales employee) table for the
marketing-assistant module. seat_used on customer tracks how many slots
have been consumed against seat_quota.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '6f7a8b9c0d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # customer.seat_used
    cust_cols = {c['name'] for c in inspector.get_columns('customer')}
    if 'seat_used' not in cust_cols:
        op.add_column(
            'customer',
            sa.Column('seat_used', sa.Integer(), nullable=False, server_default='0'),
        )

    # customer_user table
    if 'customer_user' not in inspector.get_table_names():
        op.create_table(
            'customer_user',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('customer_id', sa.Integer(),
                      sa.ForeignKey('customer.id'), nullable=False, index=True),
            sa.Column('email', sa.String(length=120), nullable=False, unique=True),
            sa.Column('hashed_password', sa.String(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=True),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='sales'),
            sa.Column('industry_filter_json', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('last_login_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.func.now(), index=True),
        )
        op.create_index('ix_customer_user_email', 'customer_user', ['email'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'customer_user' in inspector.get_table_names():
        try:
            op.drop_index('ix_customer_user_email', table_name='customer_user')
        except Exception:
            pass
        op.drop_table('customer_user')

    cust_cols = {c['name'] for c in inspector.get_columns('customer')}
    if 'seat_used' in cust_cols:
        op.drop_column('customer', 'seat_used')
