"""Let hostnames repeat; VMID alone identifies a VM."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = depends_on = None


def upgrade():
    op.drop_index("uq_vms_live_hostname", table_name="vms")


def downgrade():
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT 1 FROM vms WHERE status != 'deleted' "
            "GROUP BY hostname HAVING count(*) > 1 LIMIT 1"
        )
    ).first():
        raise RuntimeError(
            "Cannot restore live hostname uniqueness while live VMs share a hostname"
        )
    op.create_index(
        "uq_vms_live_hostname",
        "vms",
        ["hostname"],
        unique=True,
        postgresql_where=sa.text("status != 'deleted'"),
        sqlite_where=sa.text("status != 'deleted'"),
    )
