"""add invitetask.customer_id + paused_no_funds status (Epic B)

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-05-21

Lets customer-initiated InviteTask rows be filtered by tenant in the Portal.
NULL = admin/legacy. Also extends the status enum with 'paused_no_funds'
which is informational — invite_service flips a task to this state when
the customer wallet runs dry mid-run; execute_invite_task skips when it
sees this status on its next tick.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6f7a8b9c0d1e'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('invitetask')}
    if 'customer_id' not in cols:
        op.add_column(
            'invitetask',
            sa.Column('customer_id', sa.Integer(),
                      sa.ForeignKey('customer.id'), nullable=True),
        )
        op.create_index(
            'ix_invitetask_customer_id', 'invitetask', ['customer_id'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('invitetask')}
    if 'customer_id' in cols:
        try:
            op.drop_index('ix_invitetask_customer_id', table_name='invitetask')
        except Exception:
            pass
        op.drop_column('invitetask', 'customer_id')
