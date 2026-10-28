"""Optional password authentication for requested VMs."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "vm_requests",
        sa.Column(
            "auth_method", sa.String(16), nullable=False, server_default="ssh_key"
        ),
    )
    op.add_column(
        "vm_requests", sa.Column("password_encrypted", sa.Text, nullable=True)
    )
    op.alter_column("vm_requests", "auth_method", server_default=None)


def downgrade():
    op.drop_column("vm_requests", "password_encrypted")
    op.drop_column("vm_requests", "auth_method")
