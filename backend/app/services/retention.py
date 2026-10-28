"""Purge closed history after seven days, without issuing provider commands."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, select, update

from app.models import (
    RETENTION_STATES,
    VM,
    AuditLog,
    Job,
    PasswordRecovery,
    User,
    VMDeletionRequest,
    VMPasswordReset,
    VMRequest,
)
from app.services.configuration import ConfigurationService

RETENTION_DAYS = 7


def purge_history(db, at=None):
    cutoff = (at or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    # Same lock order as provisioning and account removal.
    ConfigurationService(db).row(lock=True)
    counts = {}

    def purge(model, *conditions):
        if model in RETENTION_STATES:
            field, states = RETENTION_STATES[model]
            conditions = (*conditions, getattr(model, field).in_(states))
        ids = db.scalars(select(model.id).where(*conditions).limit(500)).all()
        if ids:
            db.execute(
                delete(model).where(model.id.in_(ids)),
                execution_options={"synchronize_session": False},
            )
        counts[model.__tablename__] = counts.get(model.__tablename__, 0) + len(ids)

    # Resolve dependent records before their parent job / VM / account.
    purge(VMPasswordReset, VMPasswordReset.retention_since < cutoff)
    purge(VMDeletionRequest, VMDeletionRequest.retention_since < cutoff)
    purge(
        Job,
        Job.state.in_(["succeeded", "cancelled", "failed"]),
        Job.retention_since < cutoff,
        ~exists().where(VMPasswordReset.job_id == Job.id),
    )
    purge(
        VM,
        VM.status == "deleted",
        VM.retention_since < cutoff,
        ~exists().where(Job.vm_id == VM.id),
        ~exists().where(VMDeletionRequest.vm_id == VM.id),
        ~exists().where(VMPasswordReset.vm_id == VM.id),
    )
    purge(
        VMRequest,
        VMRequest.retention_since < cutoff,
        ~exists().where(VM.request_id == VMRequest.id),
    )
    purge(AuditLog, AuditLog.created_at < cutoff)
    purge(PasswordRecovery, PasswordRecovery.expires_at < cutoff)

    users = db.scalars(
        select(User)
        .where(
            User.status == "deleted",
            User.role != "admin",
            User.retention_since < cutoff,
            ~exists().where(VM.owner_id == User.id),
            ~exists().where(Job.owner_id == User.id),
            ~exists().where(VMRequest.owner_id == User.id),
            ~exists().where(VMDeletionRequest.owner_id == User.id),
            ~exists().where(VMPasswordReset.owner_id == User.id),
        )
        .limit(100)
        .with_for_update()
    ).all()
    for user in users:
        db.execute(delete(PasswordRecovery).where(PasswordRecovery.user_id == user.id))
        # Preserve recent audit events while removing the deleted account reference.
        db.execute(
            update(AuditLog).where(AuditLog.actor_id == user.id).values(actor_id=None)
        )
        for model in (VMRequest, VMDeletionRequest, VMPasswordReset):
            db.execute(
                update(model).where(model.decided_by == user.id).values(decided_by=None)
            )
        db.delete(user)
    counts["users"] = len(users)
    db.flush()
    return counts
