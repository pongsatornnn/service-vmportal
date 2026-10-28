"""Close review items left on VMs that a later portal deletion removed."""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE vm_password_resets SET status = 'cancelled',
            password_encrypted = NULL, retention_since = CURRENT_TIMESTAMP
        WHERE status IN ('pending', 'approved', 'needs_review')
          AND vm_id IN (SELECT id FROM vms WHERE status = 'deleted')
        """
    )
    op.execute(
        """
        UPDATE jobs SET state = 'cancelled', retention_since = CURRENT_TIMESTAMP
        WHERE state = 'needs_review'
          AND vm_id IN (SELECT id FROM vms WHERE status = 'deleted')
        """
    )


def downgrade():
    pass
