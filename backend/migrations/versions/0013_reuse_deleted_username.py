"""Release usernames after completed account deletion; retain historical IDs."""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    # Legacy installations may retain the original users_email_key name.
    for constraint in sa.inspect(bind).get_unique_constraints("users"):
        if constraint["column_names"] == ["username"]:
            op.drop_constraint(constraint["name"], "users", type_="unique")
    for index in sa.inspect(bind).get_indexes("users"):
        if index.get("unique") and index["column_names"] == ["username"]:
            op.drop_index(index["name"], table_name="users")
    op.create_index(
        "uq_users_live_username",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("status != 'deleted'"),
        sqlite_where=sa.text("status != 'deleted'"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM users GROUP BY username HAVING count(*) > 1 LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot restore global username uniqueness while historical duplicates exist"
        )
    op.drop_index("uq_users_live_username", table_name="users")
    op.create_unique_constraint("uq_users_username", "users", ["username"])
