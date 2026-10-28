"""Admin levels, the reviewer of a stuck job, and request updates seen by owners."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "primary_admin", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # Every admin that exists before promotion is possible keeps full rights.
    op.execute("UPDATE users SET primary_admin = true WHERE role = 'admin'")
    op.add_column("users", sa.Column("request_seen", sa.JSON(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
    )


def downgrade():
    op.drop_column("jobs", "reviewed_by")
    op.drop_column("users", "request_seen")
    op.drop_column("users", "primary_admin")
