import logging

from fastapi import HTTPException
from sqlalchemy import select

from app.adapters.proxmox import GIB, ProxmoxError
from app.models import VM, Job, User, VMDeletionRequest, VMPasswordReset, VMRequest
from app.repositories.portal import PortalRepository

log = logging.getLogger("portal.worker")


class ProvisioningService:
    def __init__(self, db, adapter, config):
        self.db, self.adapter, self.config = db, adapter, config
        self.repo = PortalRepository(db)

    def run(self, job_id):
        # Atomic claim; duplicate queue deliveries cannot execute the same command.
        job = self.db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.state != "queued":
            self.db.rollback()
            return
        vm = self.db.get(VM, job.vm_id)
        owner = self.db.get(User, vm.owner_id)
        req = self.db.get(VMRequest, vm.request_id)
        job.state = "running"
        self.db.commit()
        try:
            if vm.provider != self.config.proxmox_mode:
                raise RuntimeError("VM execution mode mismatch")
            if (
                not owner
                or (
                    owner.status != "approved"
                    and not (owner.status == "deleting" and job.operation == "delete")
                )
                or req.status != "approved"
            ):
                raise RuntimeError("Owner or request no longer authorized")
            if job.operation == "provision":
                vm.status = "provisioning"
                self.db.commit()
                if job.checkpoint == "resume_after_configure":
                    self.finish_provision(job, vm, req, resumed=True)
                else:
                    self.prepare_clone(job, vm, req)
                    self.finish_provision(job, vm, req)
                vm.status = "ready"
            else:
                if vm.status != "ready" or vm.vmid is None:
                    raise RuntimeError("VM not ready")
                if self.config.proxmox_mode == "real":
                    from app.services.presence import PresenceService

                    PresenceService(self.db).check(owner, vm.id, active_job_id=job.id)
                self.repo.audit(None, "proxmox.identity.check", vm.id)
                self.db.commit()
                self.adapter.identity(vm.vmid, vm.hostname)
                if job.operation == "reset_password":
                    reset = self.db.scalar(
                        select(VMPasswordReset).where(
                            VMPasswordReset.job_id == job.id,
                            VMPasswordReset.status == "approved",
                        )
                    )
                    if not reset or not reset.password_encrypted:
                        raise ProxmoxError(
                            "Password reset was not approved or credential is missing"
                        )
                    self.repo.audit(None, "proxmox.password_reset.preflight", vm.id)
                    self.db.commit()
                    self.adapter.validate_password_reset(vm.vmid)
                    self.command(
                        job,
                        "reset_password",
                        lambda: self.adapter.reset_password(
                            vm.vmid, req.guest_username, reset.password_encrypted
                        ),
                    )
                    reset.status, reset.password_encrypted = "succeeded", None
                    self.db.commit()
                    self.clear_cloudinit_password(job, vm)
                elif job.operation == "delete":
                    deletion = self.db.scalar(
                        select(VMDeletionRequest).where(
                            VMDeletionRequest.vm_id == vm.id,
                            VMDeletionRequest.status == "approved",
                        )
                    )
                    if not deletion:
                        raise RuntimeError("Deletion was not approved")
                    self.command(
                        job,
                        "delete",
                        lambda: self.adapter.delete(vm.vmid, vm.hostname),
                        wait=True,
                    )
                    vm.status, req.status, deletion.status = (
                        "deleted",
                        "deleted",
                        "completed",
                    )
                    self.close_superseded_reviews(vm, job)
                else:
                    self.command(
                        job,
                        job.operation,
                        lambda: self.adapter.power(vm.vmid, job.operation),
                        wait=True,
                    )
            job.state, job.checkpoint = "succeeded", "complete"
            self.repo.audit(None, "job.succeeded", job.id)
            if job.operation == "delete":
                from app.services.accounts import AccountService

                AccountService(self.db).finalize(vm.owner_id)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            job = self.db.get(Job, job_id)
            vm = self.db.get(VM, job.vm_id)
            if (
                isinstance(exc, HTTPException)
                and exc.detail == "VM confirmed missing from Proxmox"
            ):
                job.state, job.error = "cancelled", exc.detail
                if job.operation == "reset_password":
                    reset = self.db.scalar(
                        select(VMPasswordReset).where(VMPasswordReset.job_id == job.id)
                    )
                    if reset:
                        reset.status, reset.password_encrypted = "cancelled", None
                self.repo.audit(
                    None,
                    "job.cancelled.missing_vm",
                    job.id,
                    vm_id=vm.id,
                    command_sent=False,
                )
                self.db.commit()
                return
            job.state = "needs_review"
            job.error = (
                str(exc)
                if isinstance(exc, ProxmoxError)
                else "Operation failed or outcome uncertain; inspect worker and Proxmox logs."
            )
            if job.operation == "reset_password":
                reset = self.db.scalar(
                    select(VMPasswordReset).where(VMPasswordReset.job_id == job.id)
                )
                if reset:
                    reset.status, reset.password_encrypted = "needs_review", None
            if job.operation in {"provision", "delete"} and vm.status != "missing":
                vm.status = "needs_review"
            self.repo.audit(
                None,
                "job.needs_review",
                job.id,
                checkpoint=job.checkpoint,
                error_type=type(exc).__name__,
            )
            self.db.commit()
            log.error(
                "job_requires_review",
                extra={"job_id": job.id, "error_type": type(exc).__name__},
            )

    def prepare_clone(self, job, vm, req):
        if job.checkpoint == "resume_after_clone":
            self.repo.audit(None, "proxmox.clone.resume.preflight", vm.id)
            self.db.commit()
            task = self.adapter.task_status(job.upid)
            if (
                task.get("status") != "stopped"
                or task.get("exitstatus") != "OK"
                or task.get("type") != "qmclone"
            ):
                raise ProxmoxError("Clone task is not confirmed successful")
            self.adapter.identity(vm.vmid, vm.hostname)
            self.adapter.ensure_stopped(vm.vmid)
            self.adapter.validate_existing_clone(vm.vmid, req)
        else:
            self.repo.audit(
                None, "proxmox.template.check", self.config.proxmox_template
            )
            self.db.commit()
            self.adapter.validate_template(req)
            for _ in range(100):
                candidate = self.repo.allocate_vmid()
                if candidate == self.config.proxmox_template:
                    self.db.commit()
                    continue
                self.repo.audit(None, "proxmox.vmid.check", candidate)
                self.db.commit()
                if self.adapter.available(candidate):
                    vm.vmid = candidate
                    self.db.commit()
                    break
            else:
                raise RuntimeError("VMID allocation exhausted")
            self.command(
                job,
                "clone",
                lambda: self.adapter.clone(vm.vmid, vm.hostname),
                wait=True,
            )
        self.command(
            job,
            "configure",
            lambda: self.adapter.configure(vm.vmid, req),
            wait=True,
        )
        # Once configuration is confirmed, the portal no longer retains the VM password.
        req.password_encrypted = None
        self.db.commit()

    def finish_provision(self, job, vm, req, resumed=False):
        resize_needed = True
        if resumed:
            # Configuration was confirmed earlier; observe each later step
            # instead of assuming it did or did not happen.
            self.repo.audit(None, "proxmox.configure.resume.preflight", vm.id)
            self.db.commit()
            self.adapter.identity(vm.vmid, vm.hostname)
            wanted = req.disk * GIB
            current = self.adapter.disk_bytes(vm.vmid)
            if current > wanted:
                raise ProxmoxError(
                    "VM disk is larger than requested; admin review required"
                )
            power = self.adapter.runtime(vm.vmid).get("power")
            if power == "running":
                if current < wanted:
                    raise ProxmoxError(
                        "VM started before disk resize; admin review required"
                    )
                return
            if power != "stopped":
                raise ProxmoxError("VM power state is unknown; admin review required")
            resize_needed = current < wanted
        if req.ssh_password_login:
            self.command(
                job,
                "ssh_policy_verify",
                lambda: self.adapter.verify_ssh_password_policy(
                    vm.vmid, req.guest_username
                ),
            )
            self.command(
                job,
                "cloudinit_regenerate",
                lambda: self.adapter.regenerate_cloudinit(vm.vmid),
                wait=True,
            )
        if resize_needed:
            self.command(
                job,
                "resize",
                lambda: self.adapter.resize(vm.vmid, req.disk),
                wait=True,
            )
        self.command(
            job,
            "start",
            lambda: self.adapter.power(vm.vmid, "start"),
            wait=True,
        )

    def close_superseded_reviews(self, vm, deletion_job):
        # A verified deletion leaves nothing to reconcile for earlier failures.
        for reset in self.db.scalars(
            select(VMPasswordReset).where(VMPasswordReset.vm_id == vm.id)
        ):
            reset.password_encrypted = None
            if reset.status in {"pending", "approved", "needs_review"}:
                reset.status = "cancelled"
        for old in self.db.scalars(
            select(Job).where(
                Job.vm_id == vm.id,
                Job.state == "needs_review",
                Job.id != deletion_job.id,
            )
        ):
            self.repo.audit(
                None,
                "job.closed.vm_deleted",
                old.id,
                previous_error=old.error,
                checkpoint=old.checkpoint,
                deletion_job=deletion_job.id,
            )
            old.state = "cancelled"

    def clear_cloudinit_password(self, job, vm):
        # The guest password already changed; a failure here only leaves the
        # old Cloud-Init value for an admin to remove, so the reset still succeeds.
        try:
            cleared = self.adapter.clear_cloudinit_password(vm.vmid)
        except Exception as exc:
            self.db.rollback()
            self.repo.audit(
                None,
                "proxmox.cloudinit_password.clear_failed",
                vm.id,
                job_id=job.id,
                error=str(exc) if isinstance(exc, ProxmoxError) else "unexpected error",
            )
        else:
            self.repo.audit(
                None,
                "proxmox.cloudinit_password.cleared",
                vm.id,
                job_id=job.id,
                removed=cleared,
            )
        self.db.commit()

    def command(self, job, operation, callback, wait=False):
        job.checkpoint, job.upid = operation + "_sending", None
        self.repo.audit(
            None, "proxmox." + operation + ".sending", job.vm_id, job_id=job.id
        )
        self.db.commit()
        upid = callback()
        job.upid = upid if isinstance(upid, str) else None
        job.checkpoint = operation + "_accepted"
        self.repo.audit(
            None,
            "proxmox." + operation + ".accepted",
            job.vm_id,
            job_id=job.id,
            upid=job.upid,
        )
        self.db.commit()
        if wait and isinstance(upid, str) and upid:
            self.adapter.wait(upid)
        job.checkpoint = operation + "_complete"
        self.db.commit()
