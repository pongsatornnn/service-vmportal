"""Per-request guest username and explicit SSH password policy."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "vm_requests",
        sa.Column(
            "guest_username", sa.String(32), nullable=False, server_default="ubuntu"
        ),
    )
    op.add_column(
        "vm_requests",
        sa.Column(
            "ssh_password_login", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("vm_requests", "guest_username", server_default=None)
    op.alter_column("vm_requests", "ssh_password_login", server_default=None)


def downgrade():
    op.drop_column("vm_requests", "ssh_password_login")
    op.drop_column("vm_requests", "guest_username")
