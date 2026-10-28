"""Remember workflow state while an externally missing VM awaits review."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "vms", sa.Column("presence_previous_status", sa.String(32), nullable=True)
    )


def downgrade():
    op.drop_column("vms", "presence_previous_status")
