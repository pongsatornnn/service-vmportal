"""Web-based setup and encrypted Proxmox credentials."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = depends_on = None


def upgrade():
    table = op.create_table(
        "portal_configuration",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("data", sa.JSON, nullable=False),
        sa.Column("token_encrypted", sa.Text),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("tested_revision", sa.Integer),
        sa.Column("enabled", sa.Boolean, nullable=False),
    )
    op.bulk_insert(table, [{"id": 1, "data": {}, "revision": 0, "enabled": False}])


def downgrade():
    op.drop_table("portal_configuration")
