"""add pgvector extension and embedding/chunk columns to ai_knowledge_base

Revision ID: a7e6c2b9f1a3
Revises: 82d3131174c9
Create Date: 2026-05-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision: str = 'a7e6c2b9f1a3'
down_revision: Union[str, Sequence[str], None] = '82d3131174c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = 768


def upgrade() -> None:
    # 1. pgvector 扩展（在引入 Vector 类型前必须先创建扩展）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 延迟导入 pgvector：只有扩展装上后再 import 才安全；
    # 也避免 alembic 扫描旧版本镜像（尚未装 pgvector）时挂掉。
    from pgvector.sqlalchemy import Vector  # noqa: E402

    # 2. ai_knowledge_base 新字段
    op.add_column(
        'ai_knowledge_base',
        sa.Column('embedding', Vector(EMBEDDING_DIM), nullable=True),
    )
    op.add_column(
        'ai_knowledge_base',
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        'ai_knowledge_base',
        sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        'ai_knowledge_base',
        sa.Column('parent_doc_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        'ai_knowledge_base',
        sa.Column('chunk_index', sa.Integer(), nullable=True),
    )
    op.add_column(
        'ai_knowledge_base',
        sa.Column('source_filename', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    op.create_index(
        'ix_ai_knowledge_base_category',
        'ai_knowledge_base',
        ['category'],
    )
    op.create_index(
        'ix_ai_knowledge_base_parent_doc_id',
        'ai_knowledge_base',
        ['parent_doc_id'],
    )

    # 3. HNSW 向量索引 (cosine distance)
    # HNSW 不需要表内已有数据来训练索引，适合从零起步
    op.execute(
        "CREATE INDEX ix_ai_knowledge_base_embedding "
        "ON ai_knowledge_base USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_knowledge_base_embedding;")
    op.drop_index('ix_ai_knowledge_base_parent_doc_id', table_name='ai_knowledge_base')
    op.drop_index('ix_ai_knowledge_base_category', table_name='ai_knowledge_base')

    op.drop_column('ai_knowledge_base', 'source_filename')
    op.drop_column('ai_knowledge_base', 'chunk_index')
    op.drop_column('ai_knowledge_base', 'parent_doc_id')
    op.drop_column('ai_knowledge_base', 'language')
    op.drop_column('ai_knowledge_base', 'category')
    op.drop_column('ai_knowledge_base', 'embedding')

    # 不在 downgrade 里删扩展，因为可能有其它表依赖
