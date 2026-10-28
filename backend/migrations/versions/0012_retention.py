"""Seven-day terminal history retention; legacy records receive a full grace period."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = depends_on = None

TABLES = {
    "users": ("status", ["deleted"]),
    "vms": ("status", ["deleted"]),
    "jobs": ("state", ["succeeded"]),
    "vm_requests": ("status", ["rejected", "cancelled", "deleted"]),
    "vm_deletion_requests": ("status", ["rejected", "cancelled", "completed"]),
    "vm_password_resets": ("status", ["rejected", "cancelled", "succeeded", "failed"]),
}


def upgrade():
    for name, (field, states) in TABLES.items():
        op.add_column(
            name,
            sa.Column("retention_since", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(f"ix_{name}_retention_since", name, ["retention_since"])
        table = sa.table(name, sa.column(field), sa.column("retention_since"))
        op.execute(
            table.update()
            .where(table.c[field].in_(states))
            .values(retention_since=sa.func.now())
        )


def downgrade():
    for name in reversed(TABLES):
        op.drop_index(f"ix_{name}_retention_since", table_name=name)
        op.drop_column(name, "retention_since")
