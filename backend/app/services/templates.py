"""Named templates: admins configure and verify them; users request by name."""

from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.adapters.proxmox import ProxmoxError, make_adapter
from app.models import VM, Job, VMRequest, VMTemplate, now
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService


def with_template(config, template):
    """Runtime settings with one template's clone source and boot disk."""
    return config.model_copy(
        update={
            "proxmox_template": template.vmid,
            "disk_device": template.disk_device,
            "template_disk_gb": template.min_disk_gb,
        }
    )


def for_request(config, req):
    """Settings for work on a request's VM: the template fixed at approval."""
    if req is None or req.template_vmid is None:
        return config
    return config.model_copy(
        update={
            "proxmox_template": req.template_vmid,
            "disk_device": req.template_disk_device or config.disk_device,
        }
    )


class TemplateService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)
        self.configuration = ConfigurationService(db)

    def config_revision(self):
        return self.configuration.row().revision

    def verified(self, template, config_revision=None):
        revision = (
            self.config_revision() if config_revision is None else config_revision
        )
        return (
            template.verified_revision == template.revision
            and template.verified_config_revision == revision
        )

    def usable(self, template, config_revision=None):
        return template.enabled and self.verified(template, config_revision)

    def get(self, template_id, lock=False):
        query = select(VMTemplate).where(VMTemplate.id == template_id)
        if lock:
            query = query.with_for_update()
        template = self.db.scalar(query)
        if not template:
            raise HTTPException(404, "Template not found")
        return template

    def defined(self):
        return self.db.scalar(select(VMTemplate.id).limit(1)) is not None

    def public(self, template, admin, config_revision, in_use=0, requests=0):
        data = {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "min_disk_gb": template.min_disk_gb,
        }
        if admin:
            data.update(
                vmid=template.vmid,
                disk_device=template.disk_device,
                enabled=template.enabled,
                verified=self.verified(template, config_revision),
                verified_at=template.verified_at,
                # Pending requests still need this template to be approved.
                in_use=in_use,
                requests=requests,
            )
        return data

    def listing(self, user):
        admin = user.role == "admin"
        revision = self.config_revision()
        rows = self.db.scalars(select(VMTemplate).order_by(VMTemplate.name)).all()
        uses, pending = {}, {}
        for template_id, status, count in self.db.execute(
            select(VMRequest.template_id, VMRequest.status, func.count())
            .where(VMRequest.template_id.is_not(None))
            .group_by(VMRequest.template_id, VMRequest.status)
        ).all():
            uses[template_id] = uses.get(template_id, 0) + count
            if status == "pending":
                pending[template_id] = count
        return [
            self.public(t, admin, revision, pending.get(t.id, 0), uses.get(t.id, 0))
            for t in rows
            if admin or self.usable(t, revision)
        ]

    def choose(self, template_id):
        """The template a new request uses; None only before any is defined."""
        if template_id is None:
            if not self.defined():
                return None
            choices = [t for t in self.db.scalars(select(VMTemplate)) if self.usable(t)]
            if len(choices) != 1:
                raise HTTPException(422, "Choose a template")
            return choices[0]
        template = self.db.get(VMTemplate, template_id)
        if not template or not self.usable(template):
            raise HTTPException(409, "Template is not available")
        return template

    def _unique(self, name, current=None):
        clash = self.db.scalar(
            select(VMTemplate.id).where(
                func.lower(VMTemplate.name) == name.lower(), VMTemplate.id != current
            )
        )
        if clash:
            raise HTTPException(409, "Template name already exists")

    def create(self, actor, data):
        self._unique(data.name)
        template = VMTemplate(**data.model_dump())
        self.db.add(template)
        self.db.flush()
        self.repo.audit(actor.id, "template.created", template.id, vmid=data.vmid)
        self.db.commit()
        return template

    def _busy(self, template):
        return self.db.scalar(
            select(Job.id)
            .join(VM, VM.id == Job.vm_id)
            .join(VMRequest, VMRequest.id == VM.request_id)
            .where(
                VMRequest.template_id == template.id,
                Job.operation == "provision",
                Job.state.in_(["queued", "running"]),
            )
            .limit(1)
        )

    def update(self, actor, template_id, data):
        template = self.get(template_id, lock=True)
        self._unique(data.name, template.id)
        values = data.model_dump()
        technical = any(
            getattr(template, key) != values[key]
            for key in ("vmid", "disk_device", "min_disk_gb")
        )
        if technical and self._busy(template):
            raise HTTPException(
                409, "Wait for pending provisioning jobs before changing template"
            )
        for key, value in values.items():
            setattr(template, key, value)
        if technical:
            # Changed clone settings must be checked again before anyone uses them.
            template.revision += 1
            template.enabled = False
        self.repo.audit(
            actor.id, "template.updated", template.id, needs_verification=technical
        )
        self.db.commit()
        return template

    def verify(self, actor, template_id):
        template = self.get(template_id, lock=True)
        config = with_template(self.configuration.runtime(), template)
        revision = self.config_revision()
        self.repo.audit(actor.id, "template.check", template.id, vmid=template.vmid)
        adapter = None
        try:
            adapter = make_adapter(config)
            adapter.validate_template(SimpleNamespace(disk=template.min_disk_gb))
        except Exception as exc:
            template.verified_revision = template.verified_config_revision = None
            template.enabled = False
            self.repo.audit(
                actor.id,
                "template.check.failed",
                template.id,
                error_type=type(exc).__name__,
            )
            self.db.commit()
            raise HTTPException(
                502,
                str(exc)
                if isinstance(exc, ProxmoxError)
                else "Template check failed; check the connection and VMID",
            ) from None
        finally:
            if adapter:
                adapter.close()
        template.verified_revision = template.revision
        template.verified_config_revision = revision
        template.verified_at = now()
        self.repo.audit(actor.id, "template.verified", template.id)
        self.db.commit()
        return template

    def set_enabled(self, actor, template_id, enabled):
        template = self.get(template_id, lock=True)
        if enabled and not self.verified(template):
            raise HTTPException(409, "Verify the template before enabling it")
        template.enabled = enabled
        self.repo.audit(actor.id, "template.enabled", template.id, enabled=enabled)
        self.db.commit()
        return template

    def delete(self, actor, template_id):
        template = self.get(template_id, lock=True)
        if self.db.scalar(
            select(VMRequest.id)
            .where(VMRequest.template_id == template.id, VMRequest.status == "pending")
            .limit(1)
        ):
            raise HTTPException(
                409, "Template has pending requests; decide them before deleting"
            )
        # Approved requests already hold the clone source; history keeps the name.
        self.db.execute(
            update(VMRequest)
            .where(VMRequest.template_id == template.id)
            .values(template_id=None)
        )
        self.repo.audit(actor.id, "template.deleted", template.id, name=template.name)
        self.db.delete(template)
        self.db.commit()
