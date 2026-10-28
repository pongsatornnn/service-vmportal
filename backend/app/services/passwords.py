import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.adapters.proxmox import ProxmoxError, make_adapter
from app.core.security import passwords, require_outranks
from app.models import PasswordRecovery, VMPasswordReset
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService
from app.services.portal import PortalService


class PasswordService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def invalidate_codes(self, user_id):
        for code in self.db.scalars(
            select(PasswordRecovery).where(
                PasswordRecovery.user_id == user_id, PasswordRecovery.used_at.is_(None)
            )
        ):
            code.used_at = datetime.now(UTC)

    def change(self, actor, data):
        user = self.repo.lock_user(actor.id)
        if not passwords.verify(
            data.current_password.get_secret_value(), user.password_hash
        ):
            raise HTTPException(400, "Current password is incorrect")
        if passwords.verify(data.new_password.get_secret_value(), user.password_hash):
            raise HTTPException(422, "New password must differ from current password")
        user.password_hash = passwords.hash(data.new_password.get_secret_value())
        user.auth_version += 1
        self.invalidate_codes(user.id)
        self.repo.audit(user.id, "auth.password.changed", user.id)
        self.db.commit()
        return {"ok": True, "sign_in_required": True}

    def issue(self, actor, user_id, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        if not passwords.verify(
            data.admin_password.get_secret_value(), actor.password_hash
        ):
            raise HTTPException(403, "Administrator password is incorrect")
        target = self.repo.lock_user(user_id)
        if not target or target.status != "approved":
            raise HTTPException(404, "Approved account not found")
        # A recovery code takes over the account, so it only reaches lower
        # levels; the top admin recovers through the server CLI.
        require_outranks(actor, target)
        self.invalidate_codes(target.id)
        raw = secrets.token_urlsafe(32)
        expiry = datetime.now(UTC) + timedelta(minutes=15)
        self.db.add(
            PasswordRecovery(
                user_id=target.id,
                code_hash=hashlib.sha256(raw.encode()).hexdigest(),
                expires_at=expiry,
            )
        )
        self.repo.audit(actor.id, "auth.recovery.issued", target.id)
        self.db.commit()
        return {"code": raw, "expires_at": expiry, "username": target.username}

    def redeem(self, data):
        digest = hashlib.sha256(
            data.code.get_secret_value().strip().encode()
        ).hexdigest()
        original = self.db.scalar(
            select(PasswordRecovery).where(PasswordRecovery.code_hash == digest)
        )
        error = "Recovery code is invalid, expired or already used"
        if not original:
            raise HTTPException(400, error)
        user = self.repo.lock_user(original.user_id)
        code = self.db.scalar(
            select(PasswordRecovery)
            .where(PasswordRecovery.id == original.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        expiry = (
            code.expires_at.replace(tzinfo=UTC)
            if code.expires_at.tzinfo is None
            else code.expires_at
        )
        if (
            not user
            or user.status != "approved"
            or code.used_at
            or expiry <= datetime.now(UTC)
        ):
            raise HTTPException(400, error)
        user.password_hash = passwords.hash(data.new_password.get_secret_value())
        user.auth_version += 1
        self.invalidate_codes(user.id)
        self.repo.audit(user.id, "auth.recovery.redeemed", user.id)
        self.db.commit()
        return {"ok": True, "sign_in_required": True}

    def request_vm(self, actor, vm_id, data):
        cfg = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        vm = PortalService(self.db).managed_vm(actor, vm_id)
        owner = self.repo.lock_user(vm.owner_id)
        if owner.status in {"deleting", "deleted"}:
            raise HTTPException(409, "Account deletion is in progress")
        if vm.status != "ready" or vm.provider != cfg.proxmox_mode:
            raise HTTPException(409, "VM is not ready")
        if self.db.scalar(
            select(VMPasswordReset.id).where(
                VMPasswordReset.vm_id == vm.id,
                VMPasswordReset.status.in_(["pending", "approved"]),
            )
        ):
            raise HTTPException(409, "A password reset is already pending")
        # Recording an approval request sends no VM command. Live presence and
        # password-reset preflight remain mandatory at approval and execution.
        encrypted = (
            ConfigurationService(self.db)
            .cipher()
            .encrypt(data.new_password.get_secret_value().encode())
            .decode()
        )
        req = VMPasswordReset(
            vm_id=vm.id,
            owner_id=vm.owner_id,
            reason=data.reason,
            password_encrypted=encrypted,
        )
        self.db.add(req)
        self.repo.audit(actor.id, "vm.password_reset.requested", vm.id)
        self.db.commit()
        return req

    def decide_vm(self, actor, request_id, decision):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        cfg = ConfigurationService(self.db).runtime(lock=True, require_enabled=True)
        req = self.db.scalar(
            select(VMPasswordReset)
            .where(VMPasswordReset.id == request_id)
            .with_for_update()
        )
        if not req:
            raise HTTPException(404, "Reset request not found")
        if req.status != "pending":
            raise HTTPException(409, "Request already decided")
        if decision.approve:
            vm = PortalService(self.db).owned_vm(actor, req.vm_id)
            owner = self.repo.lock_user(vm.owner_id)
            if owner.status != "approved":
                raise HTTPException(409, "Owner not approved")
            from app.services.presence import PresenceService

            PresenceService(self.db).check(actor, vm.id)
            adapter = make_adapter(cfg)
            self.repo.audit(actor.id, "proxmox.password_reset.preflight", vm.id)
            try:
                adapter.identity(vm.vmid, vm.hostname)
                adapter.validate_password_reset(vm.vmid)
            except ProxmoxError as exc:
                self.repo.audit(
                    actor.id, "proxmox.password_reset.preflight.rejected", vm.id
                )
                self.db.commit()
                raise HTTPException(409, str(exc)) from None
            finally:
                adapter.close()
            # Same active-operation checks/locking as other VM commands.
            job = PortalService(self.db).action(
                actor, vm.id, "reset_password", commit=False
            )
            req.job_id, req.status = job.id, "approved"
        else:
            req.status, req.password_encrypted = "rejected", None
        req.decided_by, req.decision_reason = actor.id, decision.reason
        self.repo.audit(
            actor.id, "vm.password_reset.decision", req.id, approved=decision.approve
        )
        self.db.commit()
        return req

    def cancel_vm(self, actor, request_id):
        ConfigurationService(self.db).row(lock=True)
        req = self.db.scalar(
            select(VMPasswordReset)
            .where(VMPasswordReset.id == request_id)
            .with_for_update()
        )
        if not req or (actor.role != "admin" and req.owner_id != actor.id):
            raise HTTPException(404, "Reset request not found")
        if req.status != "pending":
            raise HTTPException(409, "Only a pending reset can be cancelled")
        req.status, req.password_encrypted = "cancelled", None
        self.repo.audit(actor.id, "vm.password_reset.cancelled", req.id)
        self.db.commit()
        return req
