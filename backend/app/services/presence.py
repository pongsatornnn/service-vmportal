"""On-demand VM checks. Never interpret API failures as external deletion."""

from fastapi import HTTPException
from sqlalchemy import select

from app.adapters.proxmox import ProxmoxError, make_adapter
from app.core.security import manages_all
from app.models import VM, Job, VMDeletionRequest, VMPasswordReset, VMRequest
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService

REASONS = {
    "moved": "VM moved to another Proxmox node",
    "identity_mismatch": "VM identity changed; command blocked",
    "locked": "VM is locked; command blocked",
    "task_running": "Proxmox task still active; absence cannot be confirmed",
    "unknown_clone": "Clone outcome is uncertain; absence cannot be confirmed",
    "cluster_permission": "Cluster audit permission required to confirm missing VM",
    "permission": "VM presence cannot be verified: permission",
}


class PresenceService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def check(self, actor, vm_id, active_job_id=None):
        audit_actor = actor.id if active_job_id is None else None
        original = self.db.get(VM, vm_id)
        if not original or (actor.role != "admin" and original.owner_id != actor.id):
            raise HTTPException(404, "VM not found")
        cfg = ConfigurationService(self.db).runtime(lock=True)
        self.repo.lock_user(original.owner_id)
        vm = self.db.scalar(
            select(VM)
            .where(VM.id == vm_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if vm.provider != cfg.proxmox_mode or vm.vmid is None:
            raise HTTPException(409, "VM execution mode mismatch")
        if vm.status not in {"ready", "needs_review", "missing"}:
            raise HTTPException(409, "VM is not ready")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id,
                Job.state.in_(["queued", "running"]),
                Job.id != active_job_id if active_job_id is not None else True,
            )
        ):
            raise HTTPException(409, "An operation is already active")
        if cfg.proxmox_mode != "real":
            return {"state": "present"}
        adapter = make_adapter(cfg)
        try:
            result = adapter.inspect_presence(vm.vmid, vm.hostname)
            if result.get("state") == "missing":
                latest = self.db.scalar(
                    select(Job)
                    .where(Job.vm_id == vm.id)
                    .order_by(Job.id.desc())
                    .limit(1)
                )
                if latest and latest.state == "needs_review":
                    if latest.upid:
                        try:
                            task = adapter.presence_task_status(latest.upid)
                            if (
                                not isinstance(task, dict)
                                or task.get("status") != "stopped"
                            ):
                                result = {
                                    "state": "unverified",
                                    "reason": "task_running",
                                }
                        except ProxmoxError:
                            result = {"state": "unverified", "reason": "task_running"}
                    elif latest.operation == "provision" and latest.checkpoint.endswith(
                        "_sending"
                    ):
                        result = {"state": "unverified", "reason": "unknown_clone"}
        finally:
            adapter.close()
        self.repo.audit(audit_actor, "vm.presence.checked", vm.id, **result)
        if result.get("state") == "present":
            if vm.status == "missing":
                vm.status = (
                    vm.presence_previous_status
                    if vm.presence_previous_status in {"ready", "needs_review"}
                    else "needs_review"
                )
                vm.presence_previous_status = None
                self.repo.audit(
                    audit_actor,
                    "vm.presence.returned",
                    vm.id,
                    restored_status=vm.status,
                )
            return result
        if result.get("state") == "missing":
            if vm.status != "missing":
                vm.presence_previous_status, vm.status = vm.status, "missing"
                self.repo.audit(
                    audit_actor, "vm.presence.missing", vm.id, quota_released=False
                )
            # Save the observed state even though the attempted action is rejected.
            self.db.commit()
            raise HTTPException(409, "VM confirmed missing from Proxmox")
        self.db.commit()
        raise HTTPException(
            409, REASONS.get(result.get("reason"), "VM presence could not be verified")
        )

    def confirm_external_deletion(self, actor, vm_id, hostname):
        if not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        original = self.db.get(VM, vm_id)
        if not original or original.status not in {"ready", "needs_review", "missing"}:
            raise HTTPException(409, "A confirmed missing VM is required")
        if hostname != original.hostname:
            raise HTTPException(422, "VM hostname confirmation does not match")
        try:
            self.check(actor, vm_id)
        except HTTPException as exc:
            if exc.detail not in {
                "VM confirmed missing from Proxmox",
                REASONS["cluster_permission"],
            }:
                raise
        else:
            self.db.commit()
            raise HTTPException(
                409, "VM exists again; external deletion was not confirmed"
            )
        # Reacquire locks after check committed its observation; recheck under lock
        # so concurrent confirmation/action cannot release quota twice.
        cfg = ConfigurationService(self.db).runtime(lock=True)
        self.repo.lock_user(original.owner_id)
        vm = self.db.scalar(
            select(VM)
            .where(VM.id == vm_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            vm.status not in {"ready", "needs_review", "missing"}
            or vm.provider != cfg.proxmox_mode
        ):
            raise HTTPException(409, "A confirmed missing VM is required")
        if self.db.scalar(
            select(Job.id).where(
                Job.vm_id == vm.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "An operation is already active")
        adapter = make_adapter(cfg)
        try:
            result = adapter.inspect_presence(vm.vmid, vm.hostname)
        finally:
            adapter.close()
        manual_confirmation = (
            result.get("state") == "unverified"
            and result.get("reason") == "cluster_permission"
        )
        if result.get("state") != "missing" and not manual_confirmation:
            raise HTTPException(
                409, "VM presence changed; external deletion was not confirmed"
            )
        if manual_confirmation:
            latest = self.db.scalar(
                select(Job).where(Job.vm_id == vm.id).order_by(Job.id.desc()).limit(1)
            )
            if latest and latest.state == "needs_review":
                if latest.upid:
                    adapter = make_adapter(cfg)
                    try:
                        task = adapter.presence_task_status(latest.upid)
                    except ProxmoxError:
                        raise HTTPException(409, REASONS["task_running"]) from None
                    finally:
                        adapter.close()
                    if not isinstance(task, dict) or task.get("status") != "stopped":
                        raise HTTPException(409, REASONS["task_running"])
                elif latest.operation == "provision" and latest.checkpoint.endswith(
                    "_sending"
                ):
                    raise HTTPException(409, REASONS["unknown_clone"])
        request = self.db.get(VMRequest, vm.request_id)
        vm.status, vm.presence_previous_status = "deleted", None
        request.status, request.password_encrypted = "deleted", None
        for deletion in self.db.scalars(
            select(VMDeletionRequest).where(
                VMDeletionRequest.vm_id == vm.id,
                VMDeletionRequest.status.in_(["pending", "approved"]),
            )
        ):
            deletion.status = "completed"
            deletion.decision_reason = "ผู้ดูแลยืนยันว่า VM ถูกลบจากภายนอก Portal"
        for reset in self.db.scalars(
            select(VMPasswordReset).where(VMPasswordReset.vm_id == vm.id)
        ):
            reset.password_encrypted = None
            if reset.status in {"pending", "approved", "needs_review"}:
                reset.status = "cancelled"
        for job in self.db.scalars(
            select(Job).where(Job.vm_id == vm.id, Job.state == "needs_review")
        ):
            self.repo.audit(
                actor.id,
                "job.closed.external_deletion",
                job.id,
                previous_error=job.error,
                checkpoint=job.checkpoint,
            )
            job.state = "cancelled"
        self.repo.audit(
            actor.id,
            "vm.external_deletion.confirmed",
            vm.id,
            quota_released=True,
            confirmation_source="admin_proxmox_review"
            if manual_confirmation
            else "provider_verified",
            provider_observation=result,
        )
        from app.services.accounts import AccountService

        AccountService(self.db).finalize(vm.owner_id)
        self.db.commit()
        return {"status": "deleted", "quota_released": True}
