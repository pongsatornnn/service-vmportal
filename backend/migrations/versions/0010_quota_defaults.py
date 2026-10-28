"""Configurable signup quotas; preserve previously customized accounts."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "quota_customized", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.execute("""UPDATE users SET quota_customized = true
        WHERE quota_vms <> 3 OR quota_cpu <> 8 OR quota_ram <> 16384 OR quota_disk <> 200
        OR EXISTS (SELECT 1 FROM audit_logs WHERE audit_logs.action = 'account.quota.updated'
                   AND audit_logs.target = CAST(users.id AS VARCHAR))""")
    table = op.create_table(
        "quota_defaults",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("quota_vms", sa.Integer, nullable=False),
        sa.Column("quota_cpu", sa.Integer, nullable=False),
        sa.Column("quota_ram", sa.Integer, nullable=False),
        sa.Column("quota_disk", sa.Integer, nullable=False),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quota_vms >= 0 AND quota_cpu >= 0 AND quota_ram >= 0 AND quota_disk >= 0"
        ),
    )
    op.bulk_insert(
        table,
        [
            dict(
                id=1,
                quota_vms=3,
                quota_cpu=8,
                quota_ram=16384,
                quota_disk=200,
                updated_by=None,
                updated_at=datetime.now(UTC),
            )
        ],
    )


def downgrade():
    op.drop_table("quota_defaults")
    op.drop_column("users", "quota_customized")
