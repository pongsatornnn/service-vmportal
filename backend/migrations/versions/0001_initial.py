"""Initial schema. Immutable migration snapshot."""

import sqlalchemy as sa
from alembic import op
from app.core.config import settings

revision = "0001"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        *[
            sa.Column("quota_" + k, sa.Integer, nullable=False)
            for k in ("vms", "cpu", "ram", "disk")
        ],
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "vm_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("hostname", sa.String(63), nullable=False),
        *[sa.Column(k, sa.Integer, nullable=False) for k in ("cpu", "ram", "disk")],
        sa.Column("ssh_key", sa.Text, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cpu > 0 AND ram >= 512 AND disk > 0"),
    )
    op.create_table(
        "vms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer,
            sa.ForeignKey("vm_requests.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("vmid", sa.Integer, unique=True),
        sa.Column("hostname", sa.String(63), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "vm_id", sa.Integer, sa.ForeignKey("vms.id"), nullable=False, index=True
        ),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, index=True),
        sa.Column("checkpoint", sa.String(32), nullable=False),
        sa.Column("upid", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "vmid_allocator",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("next_id", sa.Integer, nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "vmid_allocator",
            sa.column("id", sa.Integer),
            sa.column("next_id", sa.Integer),
        ),
        [{"id": 1, "next_id": settings().vmid_start}],
    )


def downgrade():
    for table in (
        "vmid_allocator",
        "audit_logs",
        "jobs",
        "vms",
        "vm_requests",
        "users",
    ):
        op.drop_table(table)
