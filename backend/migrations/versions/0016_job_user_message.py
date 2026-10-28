"""Owner-visible explanation when an admin closes a job as failed."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("user_message", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("jobs", "user_message")
