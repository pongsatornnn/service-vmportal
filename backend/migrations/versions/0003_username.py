"""Use local usernames for authentication; preserve account IDs and passwords."""

import re
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    accounts = connection.execute(
        sa.text("SELECT id, email FROM users ORDER BY id")
    ).all()
    # Rename keeps ownership foreign keys, password hashes and account state intact.
    op.alter_column(
        "users", "email", new_column_name="username", existing_type=sa.String(254)
    )
    users = sa.table(
        "users", sa.column("id", sa.Integer), sa.column("username", sa.String(254))
    )
    # Temporary unique names avoid collisions with existing local CLI-created names.
    prefix = "migration_" + uuid.uuid4().hex + "_"
    for user_id, _ in accounts:
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(username=prefix + str(user_id))
        )
    used = set()
    for user_id, legacy_name in accounts:
        base = re.sub(r"[^a-z0-9_.-]", "-", legacy_name.split("@", 1)[0].lower()).strip(
            "._-"
        )[:32]
        if len(base) < 3:
            base = "user-" + (base or str(user_id))
        name = base
        if name in used:
            suffix = "-" + str(user_id)
            name = base[: 32 - len(suffix)] + suffix
            while name in used:
                suffix += "x"
                name = base[: 32 - len(suffix)] + suffix
        used.add(name)
        connection.execute(
            users.update().where(users.c.id == user_id).values(username=name)
        )
    op.alter_column(
        "users",
        "username",
        type_=sa.String(32),
        existing_type=sa.String(254),
        existing_nullable=False,
    )


def downgrade():
    # Email addresses cannot be reconstructed. Retain local identifiers for rollback.
    op.alter_column(
        "users",
        "username",
        new_column_name="email",
        type_=sa.String(254),
        existing_type=sa.String(32),
        existing_nullable=False,
    )
