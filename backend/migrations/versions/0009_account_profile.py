"""Personal names for registration; retain existing accounts."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(100), nullable=False, server_default=""),
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(100), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
