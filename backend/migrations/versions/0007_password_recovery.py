"""Portal password recovery and reviewed VM password reset."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer, nullable=False, server_default="0"),
    )
    op.alter_column("users", "auth_version", server_default=None)
    op.create_table(
        "password_recoveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_password_recoveries_user_id", "password_recoveries", ["user_id"]
    )
    op.create_table(
        "vm_password_resets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("vms.id"), nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("password_encrypted", sa.Text),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("decision_reason", sa.Text),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vm_password_resets_vm_id", "vm_password_resets", ["vm_id"])


def downgrade():
    op.drop_table("vm_password_resets")
    op.drop_table("password_recoveries")
    op.drop_column("users", "auth_version")
