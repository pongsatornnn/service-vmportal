"""Requests keep their template's name so templates can be deleted later."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = depends_on = None


def upgrade():
    with op.batch_alter_table("vm_requests") as batch:
        batch.add_column(sa.Column("template_name", sa.String(40), nullable=True))
    op.execute(
        "UPDATE vm_requests SET template_name = (SELECT t.name FROM vm_templates t "
        "WHERE t.id = vm_requests.template_id) WHERE template_id IS NOT NULL"
    )


def downgrade():
    with op.batch_alter_table("vm_requests") as batch:
        batch.drop_column("template_name")
