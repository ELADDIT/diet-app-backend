"""Add role column to users"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f5d4b4c2a1b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True, server_default='client'))

    op.execute("UPDATE users SET role='client' WHERE role IS NULL")

    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('role', existing_type=sa.String(length=20), nullable=False, server_default='client')


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('role')
