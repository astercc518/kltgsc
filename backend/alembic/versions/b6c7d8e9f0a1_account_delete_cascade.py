"""account delete cascade — fix FK ON DELETE for batch/single account deletion

9 child tables reference account.id with default NO ACTION, blocking deletes.
- 8 tables get ON DELETE CASCADE (statistics / logs / scheduling state)
- lead gets ON DELETE SET NULL (business asset — leads survive account churn)

Revision ID: b6c7d8e9f0a1
Revises: 41f948211e5f
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa


revision = "b6c7d8e9f0a1"
down_revision = "41f948211e5f"
branch_labels = None
depends_on = None


# (table, fk_name, column, ondelete)
CASCADE_FKS = [
    ("accountsendstats", "accountsendstats_account_id_fkey", "account_id", "CASCADE"),
    ("chathistory", "chathistory_account_id_fkey", "account_id", "CASCADE"),
    ("group_message", "group_message_account_id_fkey", "account_id", "CASCADE"),
    ("sendrecord", "sendrecord_account_id_fkey", "account_id", "CASCADE"),
    ("bulk_target", "bulk_target_assigned_account_id_fkey", "assigned_account_id", "CASCADE"),
    ("pending_replies", "pending_replies_responder_account_id_fkey", "responder_account_id", "CASCADE"),
    ("worker_personas", "worker_personas_account_id_fkey", "account_id", "CASCADE"),
    ("chitchat_log", "chitchat_log_account_id_fkey", "account_id", "CASCADE"),
]

LEAD_FK = ("lead", "lead_account_id_fkey", "account_id", "SET NULL")


def upgrade():
    # Lead.account_id → nullable, FK → SET NULL
    op.alter_column("lead", "account_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint(LEAD_FK[1], LEAD_FK[0], type_="foreignkey")
    op.create_foreign_key(
        LEAD_FK[1], LEAD_FK[0], "account",
        [LEAD_FK[2]], ["id"],
        ondelete=LEAD_FK[3],
    )

    # 8 child tables → CASCADE
    for table, fk_name, column, ondelete in CASCADE_FKS:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name, table, "account",
            [column], ["id"],
            ondelete=ondelete,
        )


def downgrade():
    for table, fk_name, column, _ondelete in CASCADE_FKS:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(fk_name, table, "account", [column], ["id"])

    op.drop_constraint(LEAD_FK[1], LEAD_FK[0], type_="foreignkey")
    op.create_foreign_key(LEAD_FK[1], LEAD_FK[0], "account", [LEAD_FK[2]], ["id"])
    op.alter_column("lead", "account_id", existing_type=sa.Integer(), nullable=False)
