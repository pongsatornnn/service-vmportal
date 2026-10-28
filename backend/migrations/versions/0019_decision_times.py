"""When each request was decided and when each job finished."""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = depends_on = None

# The audit trail already records these moments; copy them for existing rows.
DECISIONS = {
    "vm_requests": "request.decision",
    "vm_deletion_requests": "vm.deletion.decision",
    "vm_password_resets": "vm.password_reset.decision",
}
JOB_ENDS = (
    "'job.succeeded', 'job.needs_review', 'job.closed.failed', "
    "'job.cancelled.missing_vm'"
)


def upgrade():
    for table, action in DECISIONS.items():
        op.add_column(
            table, sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)
        )
        op.execute(
            f"UPDATE {table} SET decided_at = (SELECT MAX(a.created_at) FROM audit_logs a "
            f"WHERE a.action = '{action}' AND a.target = CAST({table}.id AS VARCHAR)) "
            "WHERE status != 'pending'"
        )
    op.add_column(
        "jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE jobs SET finished_at = (SELECT MAX(a.created_at) FROM audit_logs a "
        f"WHERE a.action IN ({JOB_ENDS}) AND a.target = CAST(jobs.id AS VARCHAR)) "
        "WHERE state NOT IN ('queued', 'running')"
    )


def downgrade():
    op.drop_column("jobs", "finished_at")
    for table in DECISIONS:
        op.drop_column(table, "decided_at")
