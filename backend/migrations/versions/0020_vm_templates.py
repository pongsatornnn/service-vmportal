"""Named VM templates; the template from Setup becomes the first one."""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = depends_on = None


def upgrade():
    templates = op.create_table(
        "vm_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False, unique=True),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column("vmid", sa.Integer(), nullable=False),
        sa.Column("disk_device", sa.String(16), nullable=False),
        sa.Column("min_disk_gb", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("verified_revision", sa.Integer(), nullable=True),
        sa.Column("verified_config_revision", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("vm_requests") as batch:
        batch.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("template_vmid", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("template_disk_device", sa.String(16), nullable=True)
        )
        batch.create_foreign_key(
            "fk_vm_requests_template", "vm_templates", ["template_id"], ["id"]
        )
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT data, revision, tested_revision FROM portal_configuration WHERE id = 1"
        )
    ).first()
    data = row.data if row else None
    if isinstance(data, str):
        import json

        data = json.loads(data)
    if not data or not data.get("template"):
        return
    # Keep the working template usable without a new check: it was verified
    # together with the current connection.
    verified = row.tested_revision == row.revision
    bind.execute(
        templates.insert().values(
            name=f"Template {data['template']}",
            description="",
            vmid=data["template"],
            disk_device=data.get("disk_device") or "scsi0",
            min_disk_gb=data.get("template_disk_gb") or 1,
            enabled=verified,
            revision=1,
            verified_revision=1 if verified else None,
            verified_config_revision=row.revision if verified else None,
            verified_at=sa.func.now() if verified else None,
            created_at=sa.func.now(),
        )
    )
    template_id = bind.execute(sa.text("SELECT id FROM vm_templates")).scalar()
    bind.execute(
        sa.text(
            "UPDATE vm_requests SET template_id = :id, template_vmid = :vmid, "
            "template_disk_device = :disk"
        ),
        {
            "id": template_id,
            "vmid": data["template"],
            "disk": data.get("disk_device") or "scsi0",
        },
    )


def downgrade():
    with op.batch_alter_table("vm_requests") as batch:
        batch.drop_constraint("fk_vm_requests_template", type_="foreignkey")
        batch.drop_column("template_disk_device")
        batch.drop_column("template_vmid")
        batch.drop_column("template_id")
    op.drop_table("vm_templates")
