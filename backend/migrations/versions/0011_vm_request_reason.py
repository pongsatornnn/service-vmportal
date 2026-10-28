"""Preserve requester purpose independently of approval comments."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None


def upgrade():
    op.add_column("vm_requests", sa.Column("request_reason", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("vm_requests", "request_reason")
