"""The first primary administrator becomes the top administrator.

Only the top administrator grants or revokes primary (super) admin rights.
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("top_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE users SET top_admin = TRUE WHERE id = (SELECT min(id) FROM users "
        "WHERE role = 'admin' AND primary_admin = true AND status = 'approved')"
    )


def downgrade():
    op.drop_column("users", "top_admin")
