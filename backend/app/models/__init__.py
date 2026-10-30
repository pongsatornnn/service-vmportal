from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_live_username",
            "username",
            unique=True,
            postgresql_where=text("status != 'deleted'"),
            sqlite_where=text("status != 'deleted'"),
        ),
    )
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(Text)
    auth_version: Mapped[int] = mapped_column(default=0)
    role: Mapped[str] = mapped_column(String(16), default="user")
    # Primary admins change the Proxmox setup, manage every VM and the accounts;
    # other admins view everything and decide requests.
    primary_admin: Mapped[bool] = mapped_column(default=False)
    # The first administrator: the only one who grants or revokes primary rights.
    top_admin: Mapped[bool] = mapped_column(default=False)
    # Last request states the owner has viewed, so updates alert on any device.
    request_seen: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    quota_customized: Mapped[bool] = mapped_column(default=False)
    quota_vms: Mapped[int] = mapped_column(default=3)
    quota_cpu: Mapped[int] = mapped_column(default=8)
    quota_ram: Mapped[int] = mapped_column(default=16384)
    quota_disk: Mapped[int] = mapped_column(default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VMTemplate(Base):
    """A named Proxmox template users can request once an admin verified it."""

    __tablename__ = "vm_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    description: Mapped[str] = mapped_column(String(200), default="")
    vmid: Mapped[int]
    disk_device: Mapped[str] = mapped_column(String(16))
    min_disk_gb: Mapped[int]
    enabled: Mapped[bool] = mapped_column(default=False)
    # Verification holds only for these exact settings and this connection.
    revision: Mapped[int] = mapped_column(default=1)
    verified_revision: Mapped[int | None]
    verified_config_revision: Mapped[int | None]
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VMRequest(Base):
    __tablename__ = "vm_requests"
    __table_args__ = (CheckConstraint("cpu > 0 AND ram >= 512 AND disk > 0"),)
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    hostname: Mapped[str] = mapped_column(String(63))
    cpu: Mapped[int]
    ram: Mapped[int]
    disk: Mapped[int]
    ssh_key: Mapped[str] = mapped_column(Text)
    auth_method: Mapped[str] = mapped_column(String(16), default="ssh_key")
    guest_username: Mapped[str] = mapped_column(String(32), default="ubuntu")
    ssh_password_login: Mapped[bool] = mapped_column(default=False)
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_reason: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("vm_templates.id"))
    # What approval fixed for cloning, unaffected by later template edits.
    template_vmid: Mapped[int | None]
    template_disk_device: Mapped[str | None] = mapped_column(String(16))
    # Shown in history even after the template itself is deleted.
    template_name: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VM(Base):
    __tablename__ = "vms"
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("vm_requests.id"), unique=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16), default="mock")
    vmid: Mapped[int | None] = mapped_column(unique=True)
    hostname: Mapped[str] = mapped_column(String(63))
    presence_previous_status: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")


class Job(Base):
    __tablename__ = "jobs"
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    vm_id: Mapped[int] = mapped_column(ForeignKey("vms.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    checkpoint: Mapped[str] = mapped_column(String(32), default="new")
    upid: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    # Shown to the owner when an admin closes a job that cannot continue.
    user_message: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # When the job stopped running: done, closed, or waiting for admin review.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VMIDAllocator(Base):
    __tablename__ = "vmid_allocator"
    id: Mapped[int] = mapped_column(primary_key=True)
    next_id: Mapped[int] = mapped_column(Integer)


class PortalConfiguration(Base):
    __tablename__ = "portal_configuration"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    token_encrypted: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=0)
    tested_revision: Mapped[int | None]
    enabled: Mapped[bool] = mapped_column(default=False)


class VMDeletionRequest(Base):
    __tablename__ = "vm_deletion_requests"
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    vm_id: Mapped[int] = mapped_column(ForeignKey("vms.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    reason: Mapped[str] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PasswordRecovery(Base):
    __tablename__ = "password_recoveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class VMPasswordReset(Base):
    __tablename__ = "vm_password_resets"
    retention_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    vm_id: Mapped[int] = mapped_column(ForeignKey("vms.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SessionPolicy(Base):
    __tablename__ = "session_policy"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_minutes: Mapped[int | None] = mapped_column(Integer)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QuotaDefaults(Base):
    __tablename__ = "quota_defaults"
    __table_args__ = (
        CheckConstraint(
            "quota_vms >= 0 AND quota_cpu >= 0 AND quota_ram >= 0 AND quota_disk >= 0"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    quota_vms: Mapped[int] = mapped_column(default=3)
    quota_cpu: Mapped[int] = mapped_column(default=8)
    quota_ram: Mapped[int] = mapped_column(default=16384)
    quota_disk: Mapped[int] = mapped_column(default=200)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


# Start retention when a record becomes terminal, never from its creation date.
RETENTION_STATES = {
    User: ("status", {"deleted"}),
    VM: ("status", {"deleted"}),
    Job: ("state", {"succeeded", "cancelled", "failed"}),
    VMRequest: ("status", {"rejected", "cancelled", "deleted"}),
    VMDeletionRequest: ("status", {"rejected", "cancelled", "completed"}),
    VMPasswordReset: ("status", {"rejected", "cancelled", "succeeded", "failed"}),
}


def track_retention(mapper, connection, target):
    field, terminal = RETENTION_STATES[type(target)]
    if getattr(target, field) not in terminal:
        target.retention_since = None
    elif (
        target.retention_since is None
        or inspect(target).attrs[field].history.has_changes()
    ):
        target.retention_since = now()


for model in RETENTION_STATES:
    event.listen(model, "before_insert", track_retention)
    event.listen(model, "before_update", track_retention)


# Shown to people as "อนุมัติเมื่อ … / เสร็จเมื่อ …"; stored in UTC, displayed in Thai time.
def track_decision(mapper, connection, target):
    # A new row has no status yet when its column default is "pending".
    if target.status not in (None, "pending") and target.decided_at is None:
        target.decided_at = now()


def track_finish(mapper, connection, target):
    if target.state in {None, "queued", "running"}:
        target.finished_at = None
    elif (
        target.finished_at is None
        or inspect(target).attrs["state"].history.has_changes()
    ):
        target.finished_at = now()


for model in (VMRequest, VMDeletionRequest, VMPasswordReset):
    event.listen(model, "before_insert", track_decision)
    event.listen(model, "before_update", track_decision)
event.listen(Job, "before_insert", track_finish)
event.listen(Job, "before_update", track_finish)
