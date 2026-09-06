"""users table

Phase 2 (Security & Observability, minimal track): replaces the old
two-hardcoded-users model (app/core/users.py's in-memory _USERS dict,
rebuilt from ADMIN_USERNAME/PASSWORD + VIEWER_USERNAME/PASSWORD env vars
on every process start) with a real, DB-backed users table. Those same
env vars remain the *bootstrap* mechanism (see
repository.seed_default_users(), called once from main.py's lifespan)
but the DB row is the durable source of truth from then on — a restart
no longer silently re-derives credentials from whatever the env vars
currently say.

username is the primary key (no surrogate id — see db_models.py's
UserRecord docstring). tenant_id is what Phase 2's object-level
authorization filters cases/transactions reads by (see
repository.list_cases/list_transactions's tenant_id parameter and
app/api/cases.py).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches app.core.constants.DEFAULT_TENANT_ID — duplicated as a literal
# here (see 0002's identical comment) since migrations must stay runnable
# unchanged even if that constant's value is ever revisited later.
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False, server_default=_DEFAULT_TENANT_ID),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('username'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=False)
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    # Same "backfill then drop the server default" pattern as 0002 —
    # existing rows (none yet, on a brand-new table, but this keeps the
    # column's steady-state definition matching db_models.py exactly,
    # with no permanent DB-level default that could mask an application
    # bug that forgets to pass tenant_id explicitly).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('tenant_id', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
