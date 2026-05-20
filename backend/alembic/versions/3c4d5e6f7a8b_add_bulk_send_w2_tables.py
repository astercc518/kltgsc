"""add bulk_batch / bulk_target / bulk_template_variant + lead source columns (W2)

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-05-20

Creates the 3 W2 tables for TG Bulk Send:
- bulk_batch
- bulk_target
- bulk_template_variant

Also augments lead with source / bulk_batch_id so bulk replies that flow into
the existing Inbox can be filtered/joined back to their batch.

Idempotent across `SQLModel.metadata.create_all` (app startup) and `alembic
upgrade`: each step inspects current schema and only creates what's missing.

参考 docs/planning/bulk_send_spec.md §3.1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, name: str) -> bool:
    return name in set(inspector.get_table_names())


def _column_exists(inspector, table: str, column: str) -> bool:
    return column in {c['name'] for c in inspector.get_columns(table)}


def _index_exists(inspector, table: str, name: str) -> bool:
    return name in {ix['name'] for ix in inspector.get_indexes(table)}


def _fk_exists(inspector, table: str, name: str) -> bool:
    return name in {fk.get('name') for fk in inspector.get_foreign_keys(table)}


def _create_table_if_absent(inspector, table_name, *columns_and_constraints):
    """Create table if absent and refresh inspector to see it."""
    if not _table_exists(inspector, table_name):
        op.create_table(table_name, *columns_and_constraints)


def _create_index_if_absent(inspector, table, idx_name, cols):
    if _table_exists(inspector, table) and not _index_exists(inspector, table, idx_name):
        op.create_index(idx_name, table, cols)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── bulk_batch ─────────────────────────────────────────────────────
    _create_table_if_absent(
        inspector, 'bulk_batch',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('message_template', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('total_targets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replied_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_unit_price_cents', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('estimated_total_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('min_delay_sec', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('max_delay_sec', sa.Integer(), nullable=False, server_default='180'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('pause_reason', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
    )
    inspector = sa.inspect(bind)
    _create_index_if_absent(inspector, 'bulk_batch', 'ix_bulk_batch_customer_id', ['customer_id'])
    _create_index_if_absent(inspector, 'bulk_batch', 'ix_bulk_batch_status', ['status'])
    _create_index_if_absent(inspector, 'bulk_batch', 'ix_bulk_batch_started_at', ['started_at'])
    _create_index_if_absent(inspector, 'bulk_batch', 'ix_bulk_batch_created_at', ['created_at'])

    # ── bulk_template_variant ──────────────────────────────────────────
    _create_table_if_absent(
        inspector, 'bulk_template_variant',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['batch_id'], ['bulk_batch.id'], ondelete='CASCADE'),
        sa.CheckConstraint('weight >= 1', name='ck_variant_weight_min'),
    )
    inspector = sa.inspect(bind)
    _create_index_if_absent(inspector, 'bulk_template_variant', 'ix_bulk_template_variant_batch_id', ['batch_id'])

    # ── bulk_target ────────────────────────────────────────────────────
    _create_table_if_absent(
        inspector, 'bulk_target',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=True),
        sa.Column('tg_username', sa.String(length=64), nullable=True),
        sa.Column('phone', sa.String(length=24), nullable=True),
        sa.Column('display_name', sa.String(length=120), nullable=True),
        sa.Column('country', sa.String(length=4), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('assigned_account_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('failed_reason', sa.String(length=200), nullable=True),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['batch_id'], ['bulk_batch.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['assigned_account_id'], ['account.id']),
        sa.ForeignKeyConstraint(['variant_id'], ['bulk_template_variant.id']),
        sa.UniqueConstraint('customer_id', 'tg_user_id', name='uq_bulk_target_customer_user'),
    )
    inspector = sa.inspect(bind)
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_batch_id', ['batch_id'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_customer_id', ['customer_id'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_tg_user_id', ['tg_user_id'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_tg_username', ['tg_username'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_phone', ['phone'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_status', ['status'])
    _create_index_if_absent(inspector, 'bulk_target', 'ix_bulk_target_assigned_account_id', ['assigned_account_id'])

    # ── lead: source + bulk_batch_id ───────────────────────────────────
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, 'lead', 'source'):
        op.add_column('lead', sa.Column('source', sa.String(length=20), nullable=False, server_default='monitor'))
    if not _column_exists(inspector, 'lead', 'bulk_batch_id'):
        op.add_column('lead', sa.Column('bulk_batch_id', sa.Integer(), nullable=True))
    inspector = sa.inspect(bind)
    _create_index_if_absent(inspector, 'lead', 'ix_lead_source', ['source'])
    _create_index_if_absent(inspector, 'lead', 'ix_lead_bulk_batch_id', ['bulk_batch_id'])
    inspector = sa.inspect(bind)
    if not _fk_exists(inspector, 'lead', 'fk_lead_bulk_batch_id'):
        op.create_foreign_key(
            'fk_lead_bulk_batch_id', 'lead', 'bulk_batch',
            ['bulk_batch_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _fk_exists(inspector, 'lead', 'fk_lead_bulk_batch_id'):
        op.drop_constraint('fk_lead_bulk_batch_id', 'lead', type_='foreignkey')
    if _index_exists(inspector, 'lead', 'ix_lead_bulk_batch_id'):
        op.drop_index('ix_lead_bulk_batch_id', table_name='lead')
    if _index_exists(inspector, 'lead', 'ix_lead_source'):
        op.drop_index('ix_lead_source', table_name='lead')
    if _column_exists(inspector, 'lead', 'bulk_batch_id'):
        op.drop_column('lead', 'bulk_batch_id')
    if _column_exists(inspector, 'lead', 'source'):
        op.drop_column('lead', 'source')

    if _table_exists(inspector, 'bulk_target'):
        op.drop_table('bulk_target')
    if _table_exists(inspector, 'bulk_template_variant'):
        op.drop_table('bulk_template_variant')
    if _table_exists(inspector, 'bulk_batch'):
        op.drop_table('bulk_batch')
