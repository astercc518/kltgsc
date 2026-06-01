"""llm_usage safety columns: moderation_score, block_layer, routed_provider

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("llm_usage", sa.Column("moderation_score", sa.Float(), nullable=True))
    op.add_column("llm_usage", sa.Column("block_layer", sa.String(length=8), nullable=True))
    op.add_column("llm_usage", sa.Column("routed_provider", sa.String(length=32), nullable=True))
    op.create_index("ix_llm_usage_moderation_score", "llm_usage", ["moderation_score"])
    op.create_index("ix_llm_usage_block_layer", "llm_usage", ["block_layer"])
    op.create_index("ix_llm_usage_routed_provider", "llm_usage", ["routed_provider"])


def downgrade():
    op.drop_index("ix_llm_usage_routed_provider", table_name="llm_usage")
    op.drop_index("ix_llm_usage_block_layer", table_name="llm_usage")
    op.drop_index("ix_llm_usage_moderation_score", table_name="llm_usage")
    op.drop_column("llm_usage", "routed_provider")
    op.drop_column("llm_usage", "block_layer")
    op.drop_column("llm_usage", "moderation_score")
