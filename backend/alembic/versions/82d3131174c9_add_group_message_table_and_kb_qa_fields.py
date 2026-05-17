"""add group_message table and KB qa fields

Revision ID: 82d3131174c9
Revises: 91f453595349
Create Date: 2026-05-15 12:22:14.403425

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = '82d3131174c9'
down_revision: Union[str, Sequence[str], None] = '91f453595349'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. group_message 表
    op.create_table(
        'group_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_title', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('chat_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='supergroup'),
        sa.Column('chat_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('sender_id', sa.BigInteger(), nullable=True),
        sa.Column('sender_username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('sender_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('reply_to_msg_id', sa.BigInteger(), nullable=True),
        sa.Column('has_media', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('media_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('message_date', sa.DateTime(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('qa_extracted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['account_id'], ['account.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'chat_id', 'message_id', name='uq_group_msg'),
    )
    op.create_index('ix_group_message_account_id', 'group_message', ['account_id'])
    op.create_index('ix_group_message_chat_id', 'group_message', ['chat_id'])
    op.create_index('ix_group_message_sender_id', 'group_message', ['sender_id'])
    op.create_index('ix_group_message_qa_extracted', 'group_message', ['qa_extracted'])

    # 2. ai_knowledge_base 新字段（QA 抽取相关）
    op.add_column('ai_knowledge_base', sa.Column('source_type', sqlmodel.sql.sqltypes.AutoString(),
                                                  nullable=False, server_default='manual'))
    op.add_column('ai_knowledge_base', sa.Column('source_chat_id', sa.BigInteger(), nullable=True))
    op.add_column('ai_knowledge_base', sa.Column('source_chat_title', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('ai_knowledge_base', sa.Column('qa_question', sa.Text(), nullable=True))
    op.add_column('ai_knowledge_base', sa.Column('qa_answer', sa.Text(), nullable=True))
    op.add_column('ai_knowledge_base', sa.Column('qa_topic', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('ai_knowledge_base', sa.Column('qa_tags', sa.Text(), nullable=True))

    op.create_index('ix_ai_knowledge_base_source_type', 'ai_knowledge_base', ['source_type'])
    op.create_index('ix_ai_knowledge_base_source_chat_id', 'ai_knowledge_base', ['source_chat_id'])
    op.create_index('ix_ai_knowledge_base_qa_topic', 'ai_knowledge_base', ['qa_topic'])


def downgrade() -> None:
    op.drop_index('ix_ai_knowledge_base_qa_topic', table_name='ai_knowledge_base')
    op.drop_index('ix_ai_knowledge_base_source_chat_id', table_name='ai_knowledge_base')
    op.drop_index('ix_ai_knowledge_base_source_type', table_name='ai_knowledge_base')

    op.drop_column('ai_knowledge_base', 'qa_tags')
    op.drop_column('ai_knowledge_base', 'qa_topic')
    op.drop_column('ai_knowledge_base', 'qa_answer')
    op.drop_column('ai_knowledge_base', 'qa_question')
    op.drop_column('ai_knowledge_base', 'source_chat_title')
    op.drop_column('ai_knowledge_base', 'source_chat_id')
    op.drop_column('ai_knowledge_base', 'source_type')

    op.drop_index('ix_group_message_qa_extracted', table_name='group_message')
    op.drop_index('ix_group_message_sender_id', table_name='group_message')
    op.drop_index('ix_group_message_chat_id', table_name='group_message')
    op.drop_index('ix_group_message_account_id', table_name='group_message')
    op.drop_table('group_message')
