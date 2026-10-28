from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.identifiers import PortalID
from app.api.schemas import (
    Action,
    Activation,
    Bootstrap,
    BulkQuota,
    ChangePrimary,
    ChangeRole,
    CloseJob,
    ConnectionSettings,
    Decision,
    DeleteDecision,
    DeleteUser,
    DeleteVM,
    Login,
    Quota,
    QuotaDefaultsUpdate,
    Register,
    RequestSeen,
    RequestVM,
    ResourceDiscovery,
    RetryDelete,
    TemplateIn,
    TemplateToggle,
    VMRequestOut,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    DUMMY_HASH,
    admin,
    current_user,
    passwords,
    primary_admin,
    token,
)
from app.models import (
    VM,
    AuditLog,
    Job,
    User,
    VMDeletionRequest,
    VMRequest,
    VMTemplate,
)
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService
from app.services.portal import PortalService
from app.services.session_policy import SessionPolicyService

router = APIRouter(prefix="/api")


def rate_limit(request: Request):
    try:
        redis = Redis.from_url(
            settings().redis_url, socket_timeout=2, socket_connect_timeout=2
        )
        count = redis.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            "auth:" + request.client.host,
        )
        if count > 10:
            raise HTTPException(429, "Too many attempts")
    except RedisError:
        raise HTTPException(503, "Authentication temporarily unavailable") from None


def with_names(db, rows, field):
    names = PortalRepository(db).display_names(getattr(r, field) for r in rows)
    return [
        {**jsonable_encoder(r), field + "_name": names.get(getattr(r, field))}
        for r in rows
    ]


def public_user(user):
    return {
        key: getattr(user, key)
        for key in (
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "primary_admin",
            "top_admin",
            "status",
            "quota_customized",
            "quota_vms",
            "quota_cpu",
            "quota_ram",
            "quota_disk",
        )
    }


@router.post("/auth/register", status_code=201, dependencies=[Depends(rate_limit)])
def register(data: Register, db: Session = Depends(get_db)):
    if settings().require_setup and not ConfigurationService(db).has_admin():
        raise HTTPException(409, "Create the initial administrator first")
    from app.services.quota_defaults import QuotaDefaultsService

    default_quota = QuotaDefaultsService(db).values(lock=True)
    user = User(
        **default_quota,
        username=str(data.username).lower(),
        first_name=data.first_name,
        last_name=data.last_name,
        password_hash=passwords.hash(data.password),
    )
    db.add(user)
    try:
        db.flush()
        PortalRepository(db).audit(user.id, "account.registered", user.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username unavailable") from None
    return public_user(user)


@router.post("/auth/login", dependencies=[Depends(rate_limit)])
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(
        select(User).where(
            User.username == str(data.username).lower(), User.status != "deleted"
        )
    )
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid credentials")
    if user.status != "approved":
        raise HTTPException(403, "Account not approved")
    PortalRepository(db).audit(user.id, "auth.login", user.id)
    db.commit()
    return {
        "access_token": token(user, SessionPolicyService(db).public()["token_minutes"]),
        "token_type": "bearer",
    }


@router.get("/me")
def me(user=Depends(current_user)):
    return public_user(user)


@router.post("/me/request-seen")
def request_seen(
    data: RequestSeen, user=Depends(current_user), db: Session = Depends(get_db)
):
    user.request_seen = data.entries
    db.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    svc = ConfigurationService(db)
    state = (
        svc.status()
        if settings().require_setup
        else {"configured": True, "enabled": True, "connection_verified": True}
    )
    mode = (
        svc.row().data.get("mode", "unconfigured")
        if settings().require_setup
        else settings().proxmox_mode
    )
    snippet = (
        svc.row().data.get("ssh_password_snippet")
        if settings().require_setup
        else settings().ssh_password_snippet
    )
    return {
        "setup": state,
        "user": public_user(user),
        "request_seen": user.request_seen,
        "usage": PortalRepository(db).usage(user.id),
        "reserved": PortalRepository(db).usage(user.id, include_pending=True),
        "execution_mode": mode,
        "execution_enabled": state["enabled"],
        "ssh_password_login_available": mode == "mock" or bool(snippet),
    }


@router.get("/vm-requests", response_model=list[VMRequestOut])
def requests(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(VMRequest).order_by(VMRequest.id.desc()).limit(200)
    if user.role != "admin":
        query = query.where(VMRequest.owner_id == user.id)
    rows = db.scalars(query).all()
    names = PortalRepository(db).display_names(r.decided_by for r in rows)
    template_names = dict(db.execute(select(VMTemplate.id, VMTemplate.name)).all())
    return [
        VMRequestOut.model_validate(r).model_copy(
            update={
                "decided_by_name": names.get(r.decided_by),
                "template_name": template_names.get(r.template_id) or r.template_name,
                "guest_username": r.guest_username if r.owner_id == user.id else None,
            }
        )
        for r in rows
    ]


@router.get("/templates")
def templates(user=Depends(current_user), db: Session = Depends(get_db)):
    from app.services.templates import TemplateService

    return TemplateService(db).listing(user)


@router.post("/admin/templates", status_code=201)
def create_template(
    data: TemplateIn, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    from app.services.templates import TemplateService

    svc = TemplateService(db)
    return svc.public(svc.create(user, data), True, svc.config_revision())


@router.post("/admin/templates/{template_id}")
def update_template(
    template_id: PortalID,
    data: TemplateIn,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.templates import TemplateService

    svc = TemplateService(db)
    return svc.public(svc.update(user, template_id, data), True, svc.config_revision())


@router.post("/admin/templates/{template_id}/verify")
def verify_template(
    template_id: PortalID, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    from app.services.templates import TemplateService

    svc = TemplateService(db)
    return svc.public(svc.verify(user, template_id), True, svc.config_revision())


@router.post("/admin/templates/{template_id}/enabled")
def enable_template(
    template_id: PortalID,
    data: TemplateToggle,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.templates import TemplateService

    svc = TemplateService(db)
    return svc.public(
        svc.set_enabled(user, template_id, data.enabled), True, svc.config_revision()
    )


@router.post("/admin/templates/{template_id}/delete")
def delete_template(
    template_id: PortalID, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    from app.services.templates import TemplateService

    TemplateService(db).delete(user, template_id)
    return {"ok": True}


@router.post("/vm-requests", status_code=201, response_model=VMRequestOut)
def request_vm(
    data: RequestVM, user=Depends(current_user), db: Session = Depends(get_db)
):
    return PortalService(db).request_vm(user, data)


@router.get("/vms")
def vms(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(VM).order_by(VM.id.desc()).limit(200)
    if user.role != "admin":
        query = query.where(VM.owner_id == user.id)
    rows = db.scalars(query).all()
    if user.role != "admin" or not rows:
        return rows
    latest = (
        select(AuditLog.target, func.max(AuditLog.id).label("latest_id"))
        .where(
            AuditLog.action == "vm.presence.checked",
            AuditLog.target.in_([str(vm.id) for vm in rows]),
        )
        .group_by(AuditLog.target)
        .subquery()
    )
    observations = {
        entry.target: entry.details
        for entry in db.scalars(
            select(AuditLog).join(latest, AuditLog.id == latest.c.latest_id)
        )
    }
    result = []
    for vm in rows:
        observation = observations.get(str(vm.id), {})
        can_confirm = vm.status == "missing" or (
            vm.status in {"ready", "needs_review"}
            and observation.get("state") == "unverified"
            and observation.get("reason") == "cluster_permission"
        )
        result.append(
            {
                **jsonable_encoder(vm),
                "can_confirm_external_deletion": vm.vmid is not None and can_confirm,
            }
        )
    return result


@router.post("/vms/{vm_id}/actions", status_code=202)
def action(
    vm_id: PortalID,
    data: Action,
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    return PortalService(db).action(user, vm_id, data.action)


@router.get("/jobs")
def jobs(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(Job).order_by(Job.id.desc()).limit(200)
    if user.role != "admin":
        query = query.where(Job.owner_id == user.id)
    return with_names(db, db.scalars(query).all(), "reviewed_by")


@router.get("/jobs/{job_id}")
def job(job_id: PortalID, user=Depends(current_user), db: Session = Depends(get_db)):
    result = db.get(Job, job_id)
    if not result or (user.role != "admin" and result.owner_id != user.id):
        raise HTTPException(404, "Job not found")
    return with_names(db, [result], "reviewed_by")[0]


@router.get("/admin/users")
def users(user=Depends(admin), db: Session = Depends(get_db)):
    return [
        public_user(u)
        for u in db.scalars(select(User).order_by(User.id.desc()).limit(200))
    ]


@router.post("/admin/users/{user_id}/decision")
def decide_user(
    user_id: PortalID,
    data: Decision,
    user=Depends(admin),
    db: Session = Depends(get_db),
):
    PortalService(db).decide_account(user, user_id, data)
    return {"ok": True}


@router.post("/admin/vm-requests/{request_id}/decision", response_model=VMRequestOut)
def decide_request(
    request_id: PortalID,
    data: Decision,
    user=Depends(admin),
    db: Session = Depends(get_db),
):
    return PortalService(db).decide_vm(user, request_id, data)


@router.get("/admin/audit-logs")
def audit(user=Depends(admin), db: Session = Depends(get_db)):
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).all()


@router.get("/admin/proxmox/check")
def check(user=Depends(admin), db: Session = Depends(get_db)):
    return ConfigurationService(db).check(user)


@router.post("/admin/users/{user_id}/quota")
def quota(
    user_id: PortalID,
    data: Quota,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    repo = PortalRepository(db)
    target = repo.lock_user(user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.status in {"deleting", "deleted"}:
        raise HTTPException(409, "Account deletion is in progress")
    usage = repo.usage(user_id)
    for key, value in data.model_dump().items():
        if value < usage[key.removeprefix("quota_")]:
            raise HTTPException(409, "Quota cannot be below current reservations")
        setattr(target, key, value)
    target.quota_customized = True
    repo.audit(user.id, "account.quota.updated", user_id, **data.model_dump())
    db.commit()
    return public_user(target)


@router.post("/admin/users/quota/bulk")
def bulk_quota(
    data: BulkQuota, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    repo = PortalRepository(db)
    values = data.model_dump(exclude={"user_ids"})
    targets = []
    # Stable lock order prevents two overlapping selections from deadlocking.
    for user_id in sorted(set(data.user_ids)):
        target = repo.lock_user(user_id)
        if not target:
            raise HTTPException(404, "User not found")
        if target.status in {"deleting", "deleted"}:
            raise HTTPException(409, "Account deletion is in progress")
        usage = repo.usage(user_id)
        if any(
            value < usage[key.removeprefix("quota_")] for key, value in values.items()
        ):
            raise HTTPException(409, "Quota cannot be below current reservations")
        targets.append(target)
    # Validate the entire selection before changing any account.
    for target in targets:
        for key, value in values.items():
            setattr(target, key, value)
        target.quota_customized = True
        repo.audit(user.id, "account.quota.updated", target.id, **values, bulk=True)
    db.commit()
    return {"updated_count": len(targets)}


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    return ConfigurationService(db).status()


@router.post("/setup/bootstrap", status_code=201, dependencies=[Depends(rate_limit)])
def bootstrap(data: Bootstrap, db: Session = Depends(get_db)):
    return ConfigurationService(db).bootstrap(data)


@router.get("/admin/settings")
def get_settings(user=Depends(admin), db: Session = Depends(get_db)):
    return ConfigurationService(db).public()


@router.post("/admin/settings")
def save_settings(
    data: ConnectionSettings, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    return ConfigurationService(db).save(user, data)


@router.post("/admin/settings/resources")
def discover_resources(
    data: ResourceDiscovery, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    from app.services.discovery import DiscoveryService

    return DiscoveryService(db).discover(user, data)


@router.post("/admin/settings/check")
def check_settings(user=Depends(primary_admin), db: Session = Depends(get_db)):
    return ConfigurationService(db).check(user)


@router.post("/admin/settings/activation")
def activation(
    data: Activation, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    return ConfigurationService(db).activate(user, data)


@router.get("/vms/{vm_id}/runtime")
def vm_runtime(
    vm_id: PortalID, user=Depends(current_user), db: Session = Depends(get_db)
):
    vm = PortalService(db).owned_vm(user, vm_id)
    config = ConfigurationService(db).runtime()
    if vm.vmid is None or vm.status != "ready" or vm.provider != config.proxmox_mode:
        raise HTTPException(409, "VM is not ready in this execution mode")
    from app.adapters.proxmox import ProxmoxError, make_adapter

    adapter = make_adapter(config)
    try:
        PortalRepository(db).audit(user.id, "proxmox.runtime.read", vm.id)
        db.commit()
        adapter.identity(vm.vmid, vm.hostname)
        return adapter.runtime(vm.vmid)
    except ProxmoxError as exc:
        raise HTTPException(502, str(exc)) from None
    finally:
        adapter.close()


@router.get("/deletion-requests")
def deletion_requests(user=Depends(current_user), db: Session = Depends(get_db)):
    query = select(VMDeletionRequest).order_by(VMDeletionRequest.id.desc()).limit(200)
    if user.role != "admin":
        query = query.where(VMDeletionRequest.owner_id == user.id)
    return with_names(db, db.scalars(query).all(), "decided_by")


@router.post("/vms/{vm_id}/deletion-requests", status_code=201)
def request_deletion(
    vm_id: PortalID,
    data: DeleteVM,
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    return PortalService(db).request_delete(user, vm_id, data)


@router.post("/admin/deletion-requests/{request_id}/decision")
def decide_deletion(
    request_id: PortalID,
    data: DeleteDecision,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    return PortalService(db).decide_delete(user, request_id, data)


@router.post("/admin/deletion-requests/{request_id}/retry", status_code=202)
def retry_deletion(
    request_id: PortalID,
    data: RetryDelete,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    return PortalService(db).retry_delete(user, request_id, data)


@router.post("/admin/jobs/{job_id}/resume-clone", status_code=202)
def resume_clone(
    job_id: PortalID,
    data: RetryDelete,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    return PortalService(db).resume_provision(user, job_id, data)


@router.post("/admin/jobs/{job_id}/close")
def close_job(
    job_id: PortalID,
    data: CloseJob,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    return PortalService(db).close_job(user, job_id, data)


@router.post(
    "/admin/users/{user_id}/deletion",
    status_code=202,
    dependencies=[Depends(rate_limit)],
)
def delete_user(
    user_id: PortalID,
    data: DeleteUser,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.accounts import AccountService

    return AccountService(db).delete(user, user_id, data)


@router.post("/admin/users/{user_id}/role")
def change_role(
    user_id: PortalID,
    data: ChangeRole,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.accounts import AccountService

    return public_user(AccountService(db).change_role(user, user_id, data))


@router.post("/admin/users/{user_id}/primary")
def change_primary(
    user_id: PortalID,
    data: ChangePrimary,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.accounts import AccountService

    return public_user(AccountService(db).change_primary(user, user_id, data))


@router.get("/admin/users/{user_id}/deletion-preview")
def deletion_preview(
    user_id: PortalID, user=Depends(primary_admin), db: Session = Depends(get_db)
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    machines = db.scalars(
        select(VM)
        .where(VM.owner_id == target.id, VM.status != "deleted")
        .order_by(VM.id)
    ).all()
    return {
        "user": public_user(target),
        "vms": [
            {"id": v.id, "hostname": v.hostname, "vmid": v.vmid, "status": v.status}
            for v in machines
        ],
    }


@router.get("/admin/system-health")
def system_health(user=Depends(admin), db: Session = Depends(get_db)):
    from datetime import UTC, datetime

    from app.adapters.proxmox import ProxmoxError, make_adapter

    cfg = ConfigurationService(db).runtime()
    adapter = make_adapter(cfg)
    try:
        PortalRepository(db).audit(
            user.id, "proxmox.node.health.read", cfg.proxmox_node
        )
        db.commit()
        result = adapter.node_health()
        return {
            **result,
            "node": cfg.proxmox_node,
            "mode": cfg.proxmox_mode,
            "sampled_at": datetime.now(UTC).isoformat(),
        }
    except ProxmoxError as exc:
        raise HTTPException(
            502,
            "Cannot read node health; requires Sys.Audit at /nodes/"
            + cfg.proxmox_node
            + "; "
            + str(exc),
        ) from None
    finally:
        adapter.close()


@router.get("/admin/quota-defaults")
def get_quota_defaults(user=Depends(admin), db: Session = Depends(get_db)):
    from app.services.quota_defaults import QuotaDefaultsService

    return QuotaDefaultsService(db).public()


@router.post("/admin/quota-defaults")
def set_quota_defaults(
    data: QuotaDefaultsUpdate,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.quota_defaults import QuotaDefaultsService

    return QuotaDefaultsService(db).save(user, data)


@router.post("/vms/{vm_id}/presence")
def check_vm_presence(
    vm_id: PortalID, user=Depends(current_user), db: Session = Depends(get_db)
):
    from app.services.presence import PresenceService

    result = PresenceService(db).check(user, vm_id)
    db.commit()
    return {**result, "status": db.get(VM, vm_id).status}


@router.post("/admin/vms/{vm_id}/confirm-external-deletion")
def confirm_external_deletion(
    vm_id: PortalID,
    data: RetryDelete,
    user=Depends(primary_admin),
    db: Session = Depends(get_db),
):
    from app.services.presence import PresenceService

    return PresenceService(db).confirm_external_deletion(
        user, vm_id, data.confirm_hostname
    )
