"""add customer_wallet and wallet_transaction tables

Revision ID: 1101622ac928
Revises: d5e6f7a8b9c0
Create Date: 2026-05-19 16:46:59.956434

NOTE: This migration ONLY creates wallet-related tables.
Auto-generated `op.alter_column` / `op.drop_table` calls for unrelated
historical drift were discarded — those reflect model-level edits that
predate this migration and should not be touched here.

参考 docs/planning/bulk_send_spec.md §3.1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1101622ac928'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create customer_wallet + wallet_transaction tables for TG Bulk Send."""
    op.create_table(
        'customer_wallet',
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('balance_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_topup_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_spent_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('customer_id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.CheckConstraint('balance_cents >= 0', name='wallet_balance_nonneg'),
    )
    op.create_index('ix_customer_wallet_customer_id', 'customer_wallet', ['customer_id'])

    op.create_table(
        'wallet_transaction',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('balance_after_cents', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('bulk_batch_id', sa.Integer(), nullable=True),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id']),
        sa.UniqueConstraint('idempotency_key', name='uq_wallet_txn_idempotency_key'),
    )
    op.create_index('ix_wallet_transaction_customer_id', 'wallet_transaction', ['customer_id'])
    op.create_index('ix_wallet_transaction_type', 'wallet_transaction', ['type'])
    op.create_index('ix_wallet_transaction_bulk_batch_id', 'wallet_transaction', ['bulk_batch_id'])
    op.create_index('ix_wallet_transaction_invoice_id', 'wallet_transaction', ['invoice_id'])
    op.create_index('ix_wallet_transaction_created_at', 'wallet_transaction', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_wallet_transaction_created_at', table_name='wallet_transaction')
    op.drop_index('ix_wallet_transaction_invoice_id', table_name='wallet_transaction')
    op.drop_index('ix_wallet_transaction_bulk_batch_id', table_name='wallet_transaction')
    op.drop_index('ix_wallet_transaction_type', table_name='wallet_transaction')
    op.drop_index('ix_wallet_transaction_customer_id', table_name='wallet_transaction')
    op.drop_table('wallet_transaction')

    op.drop_index('ix_customer_wallet_customer_id', table_name='customer_wallet')
    op.drop_table('customer_wallet')
