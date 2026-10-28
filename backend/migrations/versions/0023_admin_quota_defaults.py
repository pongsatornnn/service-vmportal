"""Separate default quotas for admin accounts.

Row 1 keeps the user defaults; row 2 starts as a copy for admins.
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO quota_defaults (id, quota_vms, quota_cpu, quota_ram, quota_disk, "
        "updated_by, updated_at) SELECT 2, quota_vms, quota_cpu, quota_ram, quota_disk, "
        "NULL, updated_at FROM quota_defaults WHERE id = 1"
    )


def downgrade():
    op.execute("DELETE FROM quota_defaults WHERE id = 2")
