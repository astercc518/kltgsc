"""add llm_usage table for cost tracking

Revision ID: c9a7d2e3f4b5
Revises: b4d8e1f2c5a7
Create Date: 2026-05-17 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = 'c9a7d2e3f4b5'
down_revision: Union[str, Sequence[str], None] = 'b4d8e1f2c5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('account_id', sa.Integer(), nullable=True),
        sa.Column('persona_id', sa.Integer(), nullable=True),
        sa.Column('chat_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index('ix_llm_usage_ts', 'llm_usage', ['ts'])
    op.create_index('ix_llm_usage_provider', 'llm_usage', ['provider'])
    op.create_index('ix_llm_usage_model', 'llm_usage', ['model'])
    op.create_index('ix_llm_usage_source', 'llm_usage', ['source'])
    op.create_index('ix_llm_usage_account_id', 'llm_usage', ['account_id'])
    op.create_index('ix_llm_usage_persona_id', 'llm_usage', ['persona_id'])
    op.create_index('ix_llm_usage_chat_id', 'llm_usage', ['chat_id'])
    # 组合索引覆盖最常见查询：时间窗 + 分组维度
    op.create_index('ix_llm_usage_source_ts', 'llm_usage', ['source', 'ts'])
    op.create_index('ix_llm_usage_model_ts', 'llm_usage', ['model', 'ts'])


def downgrade() -> None:
    op.drop_index('ix_llm_usage_model_ts', table_name='llm_usage')
    op.drop_index('ix_llm_usage_source_ts', table_name='llm_usage')
    op.drop_index('ix_llm_usage_chat_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_persona_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_account_id', table_name='llm_usage')
    op.drop_index('ix_llm_usage_source', table_name='llm_usage')
    op.drop_index('ix_llm_usage_model', table_name='llm_usage')
    op.drop_index('ix_llm_usage_provider', table_name='llm_usage')
    op.drop_index('ix_llm_usage_ts', table_name='llm_usage')
    op.drop_table('llm_usage')
