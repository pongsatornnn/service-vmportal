"""Explicit admin-approved removal; preserve audit references until VM deletion completes."""

import secrets
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import passwords, require_outranks
from app.models import (
    VM,
    Job,
    PasswordRecovery,
    VMDeletionRequest,
    VMPasswordReset,
    VMRequest,
)
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService
from app.services.portal import PortalService


class AccountService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def delete(self, actor, user_id, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        if not actor.primary_admin:
            raise HTTPException(403, "Primary administrator required")
        if not passwords.verify(
            data.admin_password.get_secret_value(), actor.password_hash
        ):
            raise HTTPException(403, "Administrator password is incorrect")
        # Same ordering as VM approvals/actions: configuration then owner lock.
        ConfigurationService(self.db).row(lock=True)
        user = self.repo.lock_user(user_id)
        if not user:
            raise HTTPException(404, "User not found")
        require_outranks(actor, user)
        if user.status in {"deleting", "deleted"}:
            raise HTTPException(409, "Account deletion already requested")
        if data.confirm_username != user.username:
            raise HTTPException(422, "Username confirmation does not match")
        vms = self.db.scalars(
            select(VM)
            .where(VM.owner_id == user.id, VM.status != "deleted")
            .order_by(VM.id)
            .with_for_update()
        ).all()
        if sorted(data.confirm_vm_ids) != [vm.id for vm in vms]:
            raise HTTPException(409, "Account VM list changed; reload deletion preview")
        if self.db.scalar(
            select(Job.id).where(
                Job.owner_id == user.id, Job.state.in_(["queued", "running"])
            )
        ):
            raise HTTPException(409, "Account has active VM jobs; wait for completion")
        if any(vm.status != "ready" for vm in vms):
            raise HTTPException(
                409, "Account has VMs requiring review; reconcile before deletion"
            )
        portal = PortalService(self.db)
        # Read-only checks for every VM before scheduling ANY mutation.
        for vm in vms:
            portal.deletion_preflight(actor, vm)
        job_ids = []
        for vm in vms:
            existing = self.db.scalars(
                select(VMDeletionRequest).where(
                    VMDeletionRequest.vm_id == vm.id,
                    VMDeletionRequest.status.in_(["pending", "approved"]),
                )
            ).all()
            if any(d.status == "approved" for d in existing):
                raise HTTPException(
                    409,
                    "An approved deletion already exists; reconcile before account deletion",
                )
            for deletion in existing:
                deletion.status, deletion.decision_reason = (
                    "cancelled",
                    "Superseded by account deletion",
                )
            deletion = VMDeletionRequest(
                vm_id=vm.id,
                owner_id=user.id,
                status="approved",
                reason=data.reason,
                decision_reason="Admin confirmed account cascade",
                decided_by=actor.id,
            )
            self.db.add(deletion)
            job = portal.action(actor, vm.id, "delete", commit=False)
            job_ids.append(job.id)
            self.db.flush()
            self.repo.audit(
                actor.id,
                "vm.deletion.decision",
                deletion.id,
                approved=True,
                job_id=job.id,
                account_deletion=True,
            )
        for req in self.db.scalars(
            select(VMRequest).where(VMRequest.owner_id == user.id)
        ):
            req.password_encrypted = None
            if req.status == "pending":
                req.status, req.decided_by, req.reason = (
                    "cancelled",
                    actor.id,
                    "Account deletion",
                )
        for reset in self.db.scalars(
            select(VMPasswordReset).where(VMPasswordReset.owner_id == user.id)
        ):
            reset.password_encrypted = None
            if reset.status in {"pending", "approved"}:
                reset.status, reset.decided_by = "cancelled", actor.id
        for code in self.db.scalars(
            select(PasswordRecovery).where(
                PasswordRecovery.user_id == user.id, PasswordRecovery.used_at.is_(None)
            )
        ):
            code.used_at = datetime.now(UTC)
        user.status = "deleting" if vms else "deleted"
        user.auth_version += 1
        user.password_hash = passwords.hash(secrets.token_urlsafe(48))
        self.repo.audit(
            actor.id,
            "account.deletion.confirmed",
            user.id,
            reason=data.reason,
            vm_ids=[v.id for v in vms],
            job_ids=job_ids,
        )
        if not vms:
            self.repo.audit(actor.id, "account.deleted", user.id)
        self.db.commit()
        return {"status": user.status, "job_ids": job_ids, "vm_count": len(vms)}

    def finalize(self, owner_id):
        user = self.repo.lock_user(owner_id)
        if not user or user.status != "deleting":
            return
        remaining = self.db.scalar(
            select(VM.id).where(VM.owner_id == owner_id, VM.status != "deleted")
        )
        if remaining is None:
            user.status = "deleted"
            self.repo.audit(None, "account.deleted", owner_id)

    def change_role(self, actor, user_id, data):
        if actor.role != "admin" or not actor.primary_admin:
            raise HTTPException(403, "Primary administrator required")
        if not passwords.verify(
            data.admin_password.get_secret_value(), actor.password_hash
        ):
            raise HTTPException(403, "Administrator password is incorrect")
        user = self.repo.lock_user(user_id)
        if not user or user.status in {"deleting", "deleted"}:
            raise HTTPException(404, "User not found")
        require_outranks(actor, user)
        if user.status != "approved":
            raise HTTPException(409, "Only an approved account can change role")
        if data.confirm_username != user.username:
            raise HTTPException(422, "Username confirmation does not match")
        if user.role == data.role:
            raise HTTPException(409, "Account already has this role")
        previous, user.role = user.role, data.role
        if data.role == "user":
            # Primary rights only exist on admin accounts.
            user.primary_admin = False
        self.repo.audit(
            actor.id, "user.role.changed", user.id, previous=previous, role=data.role
        )
        self.db.commit()
        return user

    def change_primary(self, actor, user_id, data):
        """Only the top admin grants or revokes primary admin rights."""
        if actor.role != "admin" or not actor.top_admin:
            raise HTTPException(403, "Top administrator required")
        if not passwords.verify(
            data.admin_password.get_secret_value(), actor.password_hash
        ):
            raise HTTPException(403, "Administrator password is incorrect")
        user = self.repo.lock_user(user_id)
        if not user or user.status in {"deleting", "deleted"}:
            raise HTTPException(404, "User not found")
        if user.id == actor.id or user.top_admin:
            raise HTTPException(409, "The top administrator keeps primary rights")
        if user.role != "admin" or user.status != "approved":
            raise HTTPException(409, "Only an approved admin can hold primary rights")
        if data.confirm_username != user.username:
            raise HTTPException(422, "Username confirmation does not match")
        if user.primary_admin == data.primary_admin:
            raise HTTPException(409, "Account already has this role")
        user.primary_admin = data.primary_admin
        self.repo.audit(
            actor.id, "user.primary.changed", user.id, primary_admin=data.primary_admin
        )
        self.db.commit()
        return user
