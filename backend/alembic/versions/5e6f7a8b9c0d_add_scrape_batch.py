"""add scrape_batch table (Epic A — customer-facing scrape)

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-05-21

Customer view of group-member scrape jobs. The admin-side ScrapingTask table
stays as-is (generic task tracking). A ScrapeBatch row links 1:1 to a
ScrapingTask via scraping_task_id once a Celery task is dispatched, and is
charged on completion via FeatureRegistry.scrape_group_members.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '4d5e6f7a8b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'scrape_batch' in inspector.get_table_names():
        return
    op.create_table(
        'scrape_batch',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customer.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('source_links_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('account_ids_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('limit_per_group', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('filter_active_only', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('filter_has_photo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('filter_has_username', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', index=True),
        sa.Column('estimated_unit_price_cents', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('estimated_total_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('charged_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scraped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('new_users_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_group_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scraping_task_id', sa.Integer(), sa.ForeignKey('scrapingtask.id'), nullable=True),
        sa.Column('celery_task_id', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'scrape_batch' in inspector.get_table_names():
        op.drop_table('scrape_batch')
