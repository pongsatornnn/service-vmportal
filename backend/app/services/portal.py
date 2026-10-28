from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import manages_all
from app.models import (
    VM,
    AuditLog,
    Job,
    VMDeletionRequest,
    VMPasswordReset,
    VMRequest,
)
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService

CLONE_RESUME_CHECKPOINTS = {"clone_accepted", "configure_sending", "resume_after_clone"}
# VM configuration was confirmed; later steps can be observed and repeated.
CONFIGURED_RESUME_CHECKPOINTS = {"configure_complete", "resume_after_configure"} | {
    f"{step}_{phase}"
    for step in ("ssh_policy_verify", "cloudinit_regenerate", "resize", "start")
    for phase in ("sending", "accepted", "complete")
}


class PortalService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def decide_account(self, actor, user_id, decision):
        user = self.repo.lock_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        if user.status != "pending" or user.role == "admin":
            raise HTTPException(409, "Account already decided")
        user.status = "approved" if decision.approve else "rejected"
        self.repo.audit(
            actor.id,
            "account.decision",
            user.id,
            approved=decision.approve,
            reason=decision.reason,
        )
        self.db.commit()

    def request_vm(self, actor, data):
        config = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        if (
            data.ssh_password_login
            and config.proxmox_mode == "real"
            and not config.ssh_password_snippet
        ):
            raise HTTPException(
                409, "Admin must configure the SSH password policy in Setup first"
            )
        owner = self.repo.lock_user(actor.id)
        if not owner or owner.status != "approved":
            raise HTTPException(403, "Account not approved")
        from app.services.templates import TemplateService

        template = TemplateService(self.db).choose(data.template_id)
        minimum = template.min_disk_gb if template else config.template_disk_gb
        if data.disk < minimum:
            raise HTTPException(422, "Disk smaller than template")
        pending = self.db.scalar(
            select(VMRequest.id)
            .where(VMRequest.owner_id == actor.id, VMRequest.status == "pending")
            .offset(19)
            .limit(1)
        )
        if pending:
            raise HTTPException(409, "Too many pending requests")
        # Refuse here rather than leave the admin to discover it at approval.
        reserved = self.repo.usage(owner.id, include_pending=True)
        for name, amount in dict(
            vms=1, cpu=data.cpu, ram=data.ram, disk=data.disk
        ).items():
            left = getattr(owner, "quota_" + name) - reserved[name]
            if amount > left:
                raise HTTPException(
                    409, f"Quota exceeded: {name}; remaining {max(left, 0)}"
                )
        values = data.model_dump(exclude={"vm_password"})
        encrypted = None
        if data.auth_method == "password":
            encrypted = (
                ConfigurationService(self.db)
                .cipher()
                .encrypt(data.vm_password.get_secret_value().encode())
                .decode()
            )
        values["template_id"] = template.id if template else None
        values["template_name"] = template.name if template else None
        request = VMRequest(owner_id=actor.id, password_encrypted=encrypted, **values)
        self.db.add(request)
        self.db.flush()
        self.repo.audit(actor.id, "request.created", request.id)
        self.db.commit()
        return request

    def decide_vm(self, actor, request_id, decision):
        config = (
            ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
            if decision.approve
            else None
        )
        original = self.db.get(VMRequest, request_id)
        if not original:
            raise HTTPException(404, "Request not found")
        owner = self.repo.lock_user(original.owner_id)
        req = self.db.scalar(
            select(VMRequest)
            .where(VMRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if req.status != "pending":
            raise HTTPException(409, "Request already decided")
        if decision.approve:
            if (
                req.ssh_password_login
                and config.proxmox_mode == "real"
                and not config.ssh_password_snippet
            ):
                raise HTTPException(
                    409, "Admin must configure the SSH password policy in Setup first"
                )
            if owner.status != "approved":
                raise HTTPException(409, "Owner not approved")
            if req.template_id is not None:
                from app.services.templates import TemplateService

                templates = TemplateService(self.db)
                template = templates.get(req.template_id)
                if not templates.usable(template):
                    raise HTTPException(409, "Template is not available")
                if req.disk < template.min_disk_gb:
                    raise HTTPException(409, "Disk smaller than template")
                # Fix the clone source now; later template edits leave it alone.
                req.template_vmid = template.vmid
                req.template_disk_device = template.disk_device
            usage = self.repo.usage(owner.id)
            for name, amount in dict(
                vms=1, cpu=req.cpu, ram=req.ram, disk=req.disk
            ).items():
                if usage[name] + amount > getattr(owner, "quota_" + name):
                    raise HTTPException(409, "Quota exceeded: " + name)
            if self.db.scalar(
                select(VM.id).where(VM.hostname == req.hostname, VM.status != "deleted")
            ):
                raise HTTPException(
                    409, "Hostname already exists; choose a different hostname"
                )
            vm = VM(
                owner_id=owner.id,
                provider=config.proxmox_mode,
                request_id=req.id,
                hostname=req.hostname,
            )
            self.db.add(vm)
            try:
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                raise HTTPException(
                    409, "Hostname already exists; choose a different hostname"
                ) from None
            self.db.add(Job(vm_id=vm.id, owner_id=owner.id, operation="provision"))
        if not decision.approve:
            req.password_encrypted = None
        req.status = "approved" if decision.approve else "rejected"
        req.decided_by, req.reason = actor.id, decision.reason
        self.repo.audit(
            actor.id,
            "request.decision",
            req.id,
            approved=decision.approve,
            reason=decision.reason,
        )
        self.db.commit()
        return req

    def owned_vm(self, actor, vm_id):
        vm = self.db.get(VM, vm_id)
        if not vm or (actor.role != "admin" and vm.owner_id != actor.id):
            raise HTTPException(404, "VM not found")
        return vm

    def managed_vm(self, actor, vm_id):
        """The owner or a primary admin operates a VM; other admins only view it."""
        vm = self.owned_vm(actor, vm_id)
        if vm.owner_id != actor.id and not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        return vm

    def action(self, actor, vm_id, action, *, commit=True):
        if action not in {
            "start",
            "stop",
            "shutdown",
            "reboot",
            "delete",
            "reset_password",
        } or (action in {"delete", "reset_password"} and actor.role != "admin"):
            raise HTTPException(403, "Unsupported or unauthorized action")
        if action == "delete" and not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        config = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        self.repo.lock_user(actor.id)
        # A password reset runs only for a request the owner made and any admin
        # approved; every other operation needs the owner or a primary admin.
        vm = (
            self.owned_vm(actor, vm_id)
            if action == "reset_password"
            else self.managed_vm(actor, vm_id)
        )
        vm = self.db.scalar(
            select(VM)
            .where(VM.id == vm.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        owner = self.repo.lock_user(vm.owner_id)
        if owner.status in {"deleting", "deleted"} and action != "delete":
            raise HTTPException(409, "Account deletion is in progress")
        if vm.provider != config.proxmox_mode:
            raise HTTPException(409, "VM belongs to a different execution mode")
        if vm.status != "ready":
            raise HTTPException(409, "VM is not ready")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "An operation is already active")
        from app.services.presence import PresenceService

        PresenceService(self.db).check(actor, vm.id)
        job = Job(vm_id=vm.id, owner_id=vm.owner_id, operation=action)
        self.db.add(job)
        self.repo.audit(actor.id, "vm.action.requested", vm.id, operation=action)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return job

    def request_delete(self, actor, vm_id, data):
        ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        self.repo.lock_user(actor.id)
        vm = self.managed_vm(actor, vm_id)
        vm = self.db.scalar(select(VM).where(VM.id == vm.id).with_for_update())
        owner = self.repo.lock_user(vm.owner_id)
        if owner.status in {"deleting", "deleted"}:
            raise HTTPException(409, "Account deletion is in progress")
        if vm.status != "ready":
            raise HTTPException(409, "VM is not ready")
        if self.db.scalar(
            select(VMDeletionRequest.id).where(
                VMDeletionRequest.vm_id == vm.id,
                VMDeletionRequest.status.in_(["pending", "approved"]),
            )
        ):
            raise HTTPException(409, "Deletion already requested")
        from app.services.presence import PresenceService

        PresenceService(self.db).check(actor, vm.id)
        req = VMDeletionRequest(vm_id=vm.id, owner_id=vm.owner_id, reason=data.reason)
        self.db.add(req)
        self.repo.audit(actor.id, "vm.deletion.requested", vm.id, reason=data.reason)
        self.db.commit()
        return req

    def decide_delete(self, actor, request_id, decision):
        if not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        # Serialize all decisions/actions with the same configuration lock.
        ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        req = self.db.scalar(
            select(VMDeletionRequest)
            .where(VMDeletionRequest.id == request_id)
            .with_for_update()
        )
        if not req:
            raise HTTPException(404, "Deletion request not found")
        if req.status != "pending":
            raise HTTPException(409, "Request already decided")
        if decision.approve:
            vm = self.owned_vm(actor, req.vm_id)
            if getattr(decision, "confirm_hostname", None) != vm.hostname:
                raise HTTPException(422, "VM hostname confirmation does not match")
            self.deletion_preflight(actor, vm)
            job = self.action(actor, req.vm_id, "delete", commit=False)
            req.status = "approved"
        else:
            job = None
            req.status = "rejected"
        req.decided_by, req.decision_reason = actor.id, decision.reason
        self.repo.audit(
            actor.id,
            "vm.deletion.decision",
            req.id,
            approved=decision.approve,
            job_id=job.id if job else None,
        )
        self.db.commit()
        return req

    def deletion_preflight(self, actor, vm):
        from app.adapters.proxmox import ProxmoxError, make_adapter

        config = ConfigurationService(self.db).runtime(require_enabled=True)
        if vm.vmid is None or vm.provider != config.proxmox_mode:
            raise HTTPException(409, "VM execution mode mismatch")
        from app.services.presence import PresenceService

        PresenceService(self.db).check(actor, vm.id)
        self.repo.audit(actor.id, "proxmox.deletion.preflight", vm.id)
        # Keep preflight, decision and job creation in the caller's transaction.
        adapter = make_adapter(config)
        try:
            adapter.identity(vm.vmid, vm.hostname)
            adapter.ensure_stopped(vm.vmid)
        except ProxmoxError as exc:
            raise HTTPException(409, str(exc)) from None
        finally:
            adapter.close()

    def retry_delete(self, actor, request_id, confirmation):
        if not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        req = self.db.scalar(
            select(VMDeletionRequest)
            .where(VMDeletionRequest.id == request_id)
            .with_for_update()
        )
        if not req or req.status != "approved":
            raise HTTPException(409, "An approved deletion request is required")
        vm = self.db.scalar(select(VM).where(VM.id == req.vm_id).with_for_update())
        last = self.db.scalar(
            select(Job).where(Job.vm_id == vm.id).order_by(Job.id.desc()).limit(1)
        )
        # Only recover a proven precondition rejection, never an uncertain DELETE.
        if (
            vm.status != "needs_review"
            or not last
            or last.operation != "delete"
            or last.state != "needs_review"
            or last.upid is not None
            or last.checkpoint != "delete_sending"
            or last.error
            != "VM must be stopped before approved deletion; no force stop performed"
        ):
            raise HTTPException(
                409, "Outcome requires administrator reconciliation; retry is not safe"
            )
        if confirmation.confirm_hostname != vm.hostname:
            raise HTTPException(422, "VM hostname confirmation does not match")
        self.deletion_preflight(actor, vm)
        vm.status = "ready"
        job = self.action(actor, vm.id, "delete", commit=False)
        self.repo.audit(
            actor.id,
            "vm.deletion.retry.confirmed",
            req.id,
            previous_job=last.id,
            job_id=job.id,
        )
        self.db.commit()
        return job

    def resume_clone(self, actor, job_id, confirmation):
        from app.adapters.proxmox import ProxmoxError, make_adapter

        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        cfg = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        job = self.db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job:
            raise HTTPException(404, "Job not found")
        vm = self.db.scalar(select(VM).where(VM.id == job.vm_id).with_for_update())
        req = self.db.get(VMRequest, vm.request_id)
        from app.services.templates import for_request

        cfg = for_request(cfg, req)
        owner = self.repo.lock_user(vm.owner_id)
        if (
            job.operation != "provision"
            or job.state != "needs_review"
            or job.checkpoint
            not in {"clone_accepted", "configure_sending", "resume_after_clone"}
            or vm.vmid is None
            or vm.status != "needs_review"
            or vm.provider != cfg.proxmox_mode
            or req.status != "approved"
            or owner.status != "approved"
            or (req.auth_method == "password" and not req.password_encrypted)
        ):
            raise HTTPException(
                409, "Only an approved, unconfigured clone can be resumed"
            )
        if confirmation.confirm_hostname != vm.hostname:
            raise HTTPException(422, "VM hostname confirmation does not match")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "An operation is already active")
        clone_upid = (
            job.upid
            if job.checkpoint in {"clone_accepted", "resume_after_clone"}
            else None
        )
        if job.checkpoint == "configure_sending":
            for entry in self.db.scalars(
                select(AuditLog)
                .where(
                    AuditLog.action == "proxmox.clone.accepted",
                    AuditLog.target == str(vm.id),
                )
                .order_by(AuditLog.id.desc())
                .limit(50)
            ):
                if entry.details.get("job_id") == job.id:
                    clone_upid = entry.details.get("upid")
                    break
        if not isinstance(clone_upid, str) or not clone_upid.startswith("UPID:"):
            raise HTTPException(
                409, "Clone task proof not found; admin review required"
            )
        from app.services.presence import PresenceService

        PresenceService(self.db).check(actor, vm.id)
        adapter = make_adapter(cfg)
        try:
            task = adapter.task_status(clone_upid)
            if (
                task.get("status") != "stopped"
                or task.get("exitstatus") != "OK"
                or task.get("type") != "qmclone"
            ):
                raise HTTPException(409, "Clone task has not completed successfully")
            adapter.identity(vm.vmid, vm.hostname)
            adapter.ensure_stopped(vm.vmid)
            adapter.validate_existing_clone(vm.vmid, req)
        except ProxmoxError as exc:
            raise HTTPException(409, str(exc)) from None
        finally:
            adapter.close()
        self.repo.audit(
            actor.id,
            "provision.clone.resume.confirmed",
            job.id,
            vm_id=vm.id,
            previous_error=job.error,
            clone_upid=clone_upid,
            previous_checkpoint=job.checkpoint,
        )
        job.state, job.checkpoint, job.error = "queued", "resume_after_clone", None
        job.upid, job.reviewed_by = clone_upid, actor.id
        self.db.commit()
        return job

    def resume_provision(self, actor, job_id, confirmation):
        from app.adapters.proxmox import GIB, ProxmoxError, make_adapter

        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        job = self.db.get(Job, job_id)
        if job and job.checkpoint in CLONE_RESUME_CHECKPOINTS:
            return self.resume_clone(actor, job_id, confirmation)
        cfg = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        job = self.db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job:
            raise HTTPException(404, "Job not found")
        vm = self.db.scalar(select(VM).where(VM.id == job.vm_id).with_for_update())
        req = self.db.get(VMRequest, vm.request_id)
        from app.services.templates import for_request

        cfg = for_request(cfg, req)
        owner = self.repo.lock_user(vm.owner_id)
        if (
            job.operation != "provision"
            or job.state != "needs_review"
            or job.checkpoint not in CONFIGURED_RESUME_CHECKPOINTS
            or vm.vmid is None
            or vm.status != "needs_review"
            or vm.provider != cfg.proxmox_mode
            or req.status != "approved"
            or owner.status != "approved"
        ):
            raise HTTPException(
                409, "This job cannot be resumed safely; close it and notify the user"
            )
        if confirmation.confirm_hostname != vm.hostname:
            raise HTTPException(422, "VM hostname confirmation does not match")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "An operation is already active")
        from app.services.presence import PresenceService

        PresenceService(self.db).check(actor, vm.id)
        adapter = make_adapter(cfg)
        try:
            adapter.identity(vm.vmid, vm.hostname)
            disk = adapter.disk_bytes(vm.vmid)
        except ProxmoxError as exc:
            raise HTTPException(409, str(exc)) from None
        finally:
            adapter.close()
        if disk > req.disk * GIB:
            raise HTTPException(
                409, "VM disk is larger than requested; admin review required"
            )
        self.repo.audit(
            actor.id,
            "provision.configure.resume.confirmed",
            job.id,
            vm_id=vm.id,
            previous_error=job.error,
            previous_checkpoint=job.checkpoint,
            disk_bytes=disk,
        )
        job.state, job.checkpoint, job.error = "queued", "resume_after_configure", None
        job.reviewed_by = actor.id
        self.db.commit()
        return job

    def close_job(self, actor, job_id, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        job = self.db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job:
            raise HTTPException(404, "Job not found")
        if job.state != "needs_review":
            raise HTTPException(409, "Only a job awaiting review can be closed")
        vm = self.db.scalar(select(VM).where(VM.id == job.vm_id).with_for_update())
        if data.confirm_hostname != vm.hostname:
            raise HTTPException(422, "VM hostname confirmation does not match")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "An operation is already active")
        message = data.message.strip()
        cleanup = None
        if job.operation == "provision":
            cleanup = self.close_provision(actor, job, vm, message)
        elif job.operation == "delete":
            # The owner keeps the VM; prove it still exists before reopening it.
            self.verify_identity(actor, vm)
            vm.status = "ready"
            for deletion in self.db.scalars(
                select(VMDeletionRequest).where(
                    VMDeletionRequest.vm_id == vm.id,
                    VMDeletionRequest.status.in_(["pending", "approved"]),
                )
            ):
                deletion.status, deletion.decision_reason = "cancelled", message
        elif job.operation == "reset_password":
            reset = self.db.scalar(
                select(VMPasswordReset).where(VMPasswordReset.job_id == job.id)
            )
            if reset:
                reset.status, reset.password_encrypted = "failed", None
                reset.decision_reason = message
        job.state, job.user_message, job.reviewed_by = "failed", message, actor.id
        self.repo.audit(
            actor.id,
            "job.closed.failed",
            job.id,
            vm_id=vm.id,
            previous_error=job.error,
            checkpoint=job.checkpoint,
            cleanup_job=cleanup.id if cleanup else None,
        )
        self.db.commit()
        return job

    def verify_identity(self, actor, vm):
        from app.adapters.proxmox import ProxmoxError, make_adapter
        from app.services.presence import PresenceService

        cfg = ConfigurationService(self.db).runtime(require_enabled=True)
        PresenceService(self.db).check(actor, vm.id)
        adapter = make_adapter(cfg)
        try:
            adapter.identity(vm.vmid, vm.hostname)
        except ProxmoxError as exc:
            raise HTTPException(409, str(exc)) from None
        finally:
            adapter.close()

    def close_provision(self, actor, job, vm, message):
        req = self.db.get(VMRequest, vm.request_id)
        req.password_encrypted = None
        if vm.vmid is not None:
            from app.services.presence import PresenceService

            try:
                PresenceService(self.db).check(actor, vm.id)
            except HTTPException as exc:
                if exc.detail != "VM confirmed missing from Proxmox":
                    raise
                # The presence check committed; take the locks again.
                ConfigurationService(self.db).row(lock=True)
                self.db.refresh(job, with_for_update=True)
                self.db.refresh(vm, with_for_update=True)
                if job.state != "needs_review" or vm.status != "missing":
                    raise HTTPException(
                        409, "Job changed; reload and try again"
                    ) from None
            else:
                # A partial clone exists: remove it through the normal,
                # identity-checked deletion so quota is released afterwards.
                self.deletion_preflight(actor, vm)
                self.db.add(
                    VMDeletionRequest(
                        vm_id=vm.id,
                        owner_id=vm.owner_id,
                        reason=message,
                        status="approved",
                        decision_reason=message,
                        decided_by=actor.id,
                    )
                )
                vm.status = "ready"
                return self.action(actor, vm.id, "delete", commit=False)
        vm.status, vm.presence_previous_status = "deleted", None
        req.status = "cancelled"
        return None
