"""add feature_registry, customer_feature, and seed 7 features

Revision ID: 2b3c4d5e6f7a
Revises: 1101622ac928
Create Date: 2026-05-19

Adds:
  - feature_registry (system-wide feature catalog with default pricing)
  - customer_feature (per-customer enable/disable + price override)
  - llm_usage.customer_id column (for per-customer aggregation)
Seeds 7 MVP features with PostgreSQL ON CONFLICT DO NOTHING for idempotency.

参考 /root/.claude/plans/groovy-strolling-canyon.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, Sequence[str], None] = '1101622ac928'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── feature_registry ────────────────────────────────────────────────
    op.create_table(
        'feature_registry',
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('name_zh', sa.String(length=100), nullable=False),
        sa.Column('name_en', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('billing_unit', sa.String(length=40), nullable=False),
        sa.Column('default_price_cents', sa.Integer(), nullable=False),
        sa.Column('enabled_by_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('slug'),
        sa.CheckConstraint('default_price_cents >= 0', name='feat_reg_price_nonneg'),
    )
    op.create_index('ix_feature_registry_billing_unit', 'feature_registry', ['billing_unit'])
    op.create_index('ix_feature_registry_enabled_by_default', 'feature_registry', ['enabled_by_default'])
    op.create_index('ix_feature_registry_category', 'feature_registry', ['category'])
    op.create_index('ix_feature_registry_is_active', 'feature_registry', ['is_active'])

    # ── customer_feature ────────────────────────────────────────────────
    op.create_table(
        'customer_feature',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('feature_slug', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('custom_price_cents', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('granted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['feature_slug'], ['feature_registry.slug']),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['user.id']),
        sa.UniqueConstraint('customer_id', 'feature_slug', name='uq_customer_feature'),
        sa.CheckConstraint(
            'custom_price_cents IS NULL OR custom_price_cents >= 0',
            name='cust_feat_price_nonneg',
        ),
    )
    op.create_index('ix_customer_feature_customer_id', 'customer_feature', ['customer_id'])
    op.create_index('ix_customer_feature_feature_slug', 'customer_feature', ['feature_slug'])

    # ── llm_usage.customer_id (向后兼容 nullable) ───────────────────────
    op.add_column('llm_usage', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.create_index('ix_llm_usage_customer_id', 'llm_usage', ['customer_id'])
    op.create_index('ix_llm_usage_customer_id_ts', 'llm_usage', ['customer_id', 'ts'])
    op.create_foreign_key(
        'fk_llm_usage_customer_id', 'llm_usage', 'customer',
        ['customer_id'], ['id'],
    )

    # ── seed 7 MVP features ─────────────────────────────────────────────
    op.execute("""
        INSERT INTO feature_registry
            (slug, name_zh, name_en, description, billing_unit, default_price_cents, enabled_by_default, category, is_active)
        VALUES
            ('bulk_send_message', '群发消息', 'Bulk Send Message',
             'TG 群发，按成功送达条数计费', 'message', 10, false, 'marketing', true),
            ('scrape_group_members', '群成员采集', 'Scrape Group Members',
             '按入库成员数计费', 'member', 1, false, 'scraping', true),
            ('bulk_invite', '批量拉人', 'Bulk Invite',
             '按邀请请求数计费（含失败）', 'invite', 5, false, 'marketing', true),
            ('auto_register', '自动注册账号', 'Auto Register',
             '每个新账号 SMS + 代理实际成本', 'account', 150, false, 'account', true),
            ('kb_extract_qa', 'KB Q&A 抽取', 'KB Q&A Extraction',
             '按 LLM 窗口数计费', 'qa_window', 2, false, 'kb', true),
            ('kb_file_upload', 'KB 文件上传', 'KB File Upload',
             '按文件 MB 数计费（embedding 成本）', 'mb', 20, false, 'kb', true),
            ('auto_reply_ai', 'AI 自动回复', 'AI Auto Reply',
             '按 AI 生成回复条数计费（含副驾驶草稿）', 'ai_reply', 2, false, 'ai', true)
        ON CONFLICT (slug) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_constraint('fk_llm_usage_customer_id', 'llm_usage', type_='foreignkey')
    op.drop_index('ix_llm_usage_customer_id_ts', table_name='llm_usage')
    op.drop_index('ix_llm_usage_customer_id', table_name='llm_usage')
    op.drop_column('llm_usage', 'customer_id')

    op.drop_index('ix_customer_feature_feature_slug', table_name='customer_feature')
    op.drop_index('ix_customer_feature_customer_id', table_name='customer_feature')
    op.drop_table('customer_feature')

    op.drop_index('ix_feature_registry_is_active', table_name='feature_registry')
    op.drop_index('ix_feature_registry_category', table_name='feature_registry')
    op.drop_index('ix_feature_registry_enabled_by_default', table_name='feature_registry')
    op.drop_index('ix_feature_registry_billing_unit', table_name='feature_registry')
    op.drop_table('feature_registry')
