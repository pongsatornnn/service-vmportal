from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.identifiers import PortalID
from app.api.routes import rate_limit
from app.api.schemas import (
    ChangePassword,
    Decision,
    IssueRecovery,
    RedeemRecovery,
    ResetVMPassword,
    SessionPolicyUpdate,
    VMPasswordResetOut,
)
from app.core.db import get_db
from app.core.security import admin, current_user, primary_admin
from app.models import VMPasswordReset
from app.repositories.portal import PortalRepository
from app.services.passwords import PasswordService

router = APIRouter(prefix="/api")


@router.post("/auth/change-password", dependencies=[Depends(rate_limit)])
def change_password(
    data: ChangePassword, user=Depends(current_user), db: Session = Depends(get_db)
):
    return PasswordService(db).change(user, data)


@router.post("/auth/recover-password", dependencies=[Depends(rate_limit)])
def recover_password(data: RedeemRecovery, db: Session = Depends(get_db)):
    return PasswordService(db).redeem(data)


@router.post("/admin/users/{user_id}/recovery-code", dependencies=[Depends(rate_limit)])
def issue_recovery(
    user_id: PortalID,
    data: IssueRecovery,
    user=Depends(admin),
    db: Session = Depends(get_db),
):
    return PasswordService(db).issue(user, user_id, data)


@router.post(
    "/vms/{vm_id}/password-resets",
    status_code=201,
    response_model=VMPasswordResetOut,
    dependencies=[Depends(rate_limit)],
)
def request_vm_reset(
    vm_id: PortalID,
    data: ResetVMPassword,
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    return PasswordService(db).request_vm(user, vm_id, data)


@router.get("/vm-password-resets", response_model=list[VMPasswordResetOut])
def list_vm_resets(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(VMPasswordReset).order_by(VMPasswordReset.id.desc()).limit(200)
    if user.role != "admin":
        query = query.where(VMPasswordReset.owner_id == user.id)
    rows = db.scalars(query).all()
    names = PortalRepository(db).display_names(r.decided_by for r in rows)
    return [
        VMPasswordResetOut.model_validate(r).model_copy(
            update={"decided_by_name": names.get(r.decided_by)}
        )
        for r in rows
    ]


@router.post(
    "/admin/vm-password-resets/{request_id}/decision", response_model=VMPasswordResetOut
)
def decide_vm_reset(
    request_id: PortalID,
    data: Decision,
    user=Depends(admin),
    db: Session = Depends(get_db),
):
    return PasswordService(db).decide_vm(user, request_id, data)


@router.post(
    "/vm-password-resets/{request_id}/cancel", response_model=VMPasswordResetOut
)
def cancel_vm_reset(
    request_id: PortalID, user=Depends(current_user), db: Session = Depends(get_db)
):
    return PasswordService(db).cancel_vm(user, request_id)


@router.post("/auth/logout")
def logout(user=Depends(current_user), db: Session = Depends(get_db)):
    from app.repositories.portal import PortalRepository

    repo = PortalRepository(db)
    account = repo.lock_user(user.id)
    account.auth_version += 1
    repo.audit(account.id, "auth.logout.all_sessions", account.id)
    db.commit()
    return {"ok": True, "scope": "all_sessions"}


@router.get("/admin/session-policy")
def get_session_policy(user=Depends(admin), db: Session = Depends(get_db)):
    from app.services.session_policy import SessionPolicyService

    return SessionPolicyService(db).public()


@router.post("/admin/session-policy")
def save_session_policy(
    data: SessionPolicyUpdate,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.session_policy import SessionPolicyService

    return SessionPolicyService(db).save(user, data)
