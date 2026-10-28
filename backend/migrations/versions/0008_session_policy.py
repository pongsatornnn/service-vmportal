"""Admin-managed session duration, separate from Proxmox setup."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None


def upgrade():
    table = op.create_table(
        "session_policy",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("token_minutes", sa.Integer),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": 1,
                "token_minutes": None,
                "updated_by": None,
                "updated_at": datetime.now(UTC),
            }
        ],
    )


def downgrade():
    op.drop_table("session_policy")
