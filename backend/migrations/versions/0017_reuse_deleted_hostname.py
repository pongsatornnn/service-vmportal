"""Release VM hostnames after deletion; retain historical VM rows."""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    for constraint in sa.inspect(bind).get_unique_constraints("vms"):
        if constraint["column_names"] == ["hostname"]:
            op.drop_constraint(constraint["name"], "vms", type_="unique")
    for index in sa.inspect(bind).get_indexes("vms"):
        if index.get("unique") and index["column_names"] == ["hostname"]:
            op.drop_index(index["name"], table_name="vms")
    op.create_index(
        "uq_vms_live_hostname",
        "vms",
        ["hostname"],
        unique=True,
        postgresql_where=sa.text("status != 'deleted'"),
        sqlite_where=sa.text("status != 'deleted'"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM vms GROUP BY hostname HAVING count(*) > 1 LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot restore global hostname uniqueness while historical duplicates exist"
        )
    op.drop_index("uq_vms_live_hostname", table_name="vms")
    op.create_unique_constraint("uq_vms_hostname", "vms", ["hostname"])
