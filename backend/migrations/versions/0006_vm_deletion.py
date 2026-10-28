"""Admin-reviewed VM deletion requests."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "vm_deletion_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("vms.id"), nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("decision_reason", sa.Text),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vm_deletion_requests_vm_id", "vm_deletion_requests", ["vm_id"])


def downgrade():
    op.drop_table("vm_deletion_requests")
