"""seed ai_marketing_assistant + group_reply + lead_created features (S2.3 / S2.4)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-21

Three new feature_registry rows:
  - ai_marketing_assistant   : gate-switch (no per-unit price). Controls
                                whether a customer can author monitor rules
                                via /portal/monitors. Auto-enabled by
                                billing_service.activate_invoice for any
                                paid subscription tier.
  - ai_marketing_group_reply : per-reply charge when listener_service's
                                _execute_active_marketing posts an AI
                                reply into a customer-owned monitor's
                                source group.
  - ai_marketing_lead_created: per-lead charge when a customer-owned
                                monitor materializes a Lead row in the
                                customer's inbox.

Idempotent INSERT (ON CONFLICT DO NOTHING). Downgrade removes these
three rows only — leaves any prior ones alone.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, Sequence[str], None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO feature_registry
            (slug, name_zh, name_en, description, billing_unit,
             default_price_cents, enabled_by_default, category, is_active)
        VALUES
            ('ai_marketing_assistant',
             'AI 营销助手',
             'AI Marketing Assistant',
             '开关：客户能否在 /portal/monitors 配置 AI 主动营销规则。订阅激活时自动开通。',
             'enabled', 0, false, 'ai', true),
            ('ai_marketing_group_reply',
             'AI 群内主动回话',
             'AI Active Group Reply',
             '客户自配 monitor 命中后 AI 在源群内主动回话，按条计费。',
             'reply', 5, false, 'ai', true),
            ('ai_marketing_lead_created',
             'AI 自动线索',
             'AI Auto-Created Lead',
             '客户自配 monitor 命中后系统自动落 Lead 进 inbox，按条计费。',
             'lead', 50, false, 'ai', true)
        ON CONFLICT (slug) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM feature_registry
        WHERE slug IN (
            'ai_marketing_assistant',
            'ai_marketing_group_reply',
            'ai_marketing_lead_created'
        );
    """)
