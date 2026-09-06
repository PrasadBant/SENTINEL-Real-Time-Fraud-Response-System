"""tenant and idempotency

Adds tenant_id to transactions/cases/actions (single tenant today —
app.core.constants.DEFAULT_TENANT_ID — but the column exists from day
one rather than being retrofitted later), and idempotency_key (unique)
to transactions so POST /transaction can detect and short-circuit
duplicate submissions instead of re-scoring them.

Also drops the FK from actions.case_id to cases.case_id: proactive
bridge-node alerts (app/services/global_graph_analyzer.py) write
case_id="GLOBAL", which never corresponds to a real case row. SQLite
never enforced this FK so it "worked" by accident; Postgres does
enforce it and would reject every one of those inserts. The
case/action relationship was never traversed anywhere in the app.

tenant_id is added NOT NULL with a temporary server_default so this is
safe to run against a table that already has rows — existing rows get
backfilled to DEFAULT_TENANT_ID at ALTER TABLE time. The server default
is dropped immediately after: new rows should get their tenant_id from
the application (app.core.repository), not a permanent DB-level default
baked into the schema. Uses batch mode throughout for SQLite
compatibility (SQLite can't ALTER/drop constraints in place; batch mode
falls back to plain ALTER statements on backends — Postgres included —
that support them natively, no table copy involved).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06 13:33:34.249309

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches app.core.constants.DEFAULT_TENANT_ID — duplicated as a literal
# here (rather than imported) since migrations must stay runnable
# unchanged even if that constant's value is ever revisited later.
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.String(), nullable=False, server_default=_DEFAULT_TENANT_ID))
        batch_op.create_index(batch_op.f('ix_actions_tenant_id'), ['tenant_id'], unique=False)
        batch_op.drop_constraint('fk_actions_case_id_cases', type_='foreignkey')
    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.alter_column('tenant_id', server_default=None)

    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.String(), nullable=False, server_default=_DEFAULT_TENANT_ID))
        batch_op.create_index(batch_op.f('ix_cases_tenant_id'), ['tenant_id'], unique=False)
    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.alter_column('tenant_id', server_default=None)

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tenant_id', sa.String(), nullable=False, server_default=_DEFAULT_TENANT_ID))
        batch_op.add_column(sa.Column('idempotency_key', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_transactions_idempotency_key'), ['idempotency_key'], unique=True)
        batch_op.create_index(batch_op.f('ix_transactions_tenant_id'), ['tenant_id'], unique=False)
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('tenant_id', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transactions_tenant_id'))
        batch_op.drop_index(batch_op.f('ix_transactions_idempotency_key'))
        batch_op.drop_column('idempotency_key')
        batch_op.drop_column('tenant_id')

    with op.batch_alter_table('cases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cases_tenant_id'))
        batch_op.drop_column('tenant_id')

    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_actions_case_id_cases', 'cases', ['case_id'], ['case_id'])
        batch_op.drop_index(batch_op.f('ix_actions_tenant_id'))
        batch_op.drop_column('tenant_id')
