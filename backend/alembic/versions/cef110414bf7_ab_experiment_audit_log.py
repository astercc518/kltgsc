"""ab_experiment_audit_log

Revision ID: cef110414bf7
Revises: 148458b23ea2
Create Date: 2026-05-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from typing import Sequence, Union

revision: str = "cef110414bf7"
down_revision: Union[str, Sequence[str], None] = "148458b23ea2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ab_experiment_audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("experiment_id", sa.Integer,
                  sa.ForeignKey("ab_experiments.id"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        # action: 'created' | 'started' | 'stopped' | 'auto_stopped'
        sa.Column("operator_id", sa.Integer,
                  sa.ForeignKey("user.id"), nullable=True),
        # operator_id nullable: 'auto_stopped' is a system action, NULL
        sa.Column("reason", sa.Text, nullable=True),
        # reason for auto_stop: 'significant_result' / 'max_duration' etc
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_ab_audit_experiment_time",
        "ab_experiment_audit_log",
        ["experiment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_ab_audit_experiment_time", table_name="ab_experiment_audit_log")
    op.drop_table("ab_experiment_audit_log")
