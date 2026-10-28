from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import rank
from app.models import QuotaDefaults, User
from app.repositories.portal import PortalRepository

KEYS = ("quota_vms", "quota_cpu", "quota_ram", "quota_disk")
# One defaults row per account role.
ROWS = {"user": 1, "admin": 2}


class QuotaDefaultsService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def row(self, lock=False, role="user"):
        query = (
            select(QuotaDefaults)
            .where(QuotaDefaults.id == ROWS[role])
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if row is None:
            raise HTTPException(503, "Quota defaults schema missing; run migrations")
        return row

    def values(self, lock=False, role="user"):
        row = self.row(lock, role)
        return {key: getattr(row, key) for key in KEYS}

    def public(self, role="user"):
        row = self.row(role=role)
        return {
            "role": role,
            **{key: getattr(row, key) for key in KEYS},
            "updated_at": row.updated_at,
        }

    def save(self, actor, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        # Admin defaults reach admin accounts, so they need a level above admin.
        if data.role == "admin" and rank(actor) <= 1:
            raise HTTPException(403, "Only accounts below your level can be managed")
        row = self.row(lock=True, role=data.role)
        before = {key: getattr(row, key) for key in KEYS}
        values = data.model_dump(exclude={"apply_to_existing", "role"})
        for key, value in values.items():
            setattr(row, key, value)
        updated, skipped = [], []
        if data.apply_to_existing:
            users = self.db.scalars(
                select(User)
                .where(
                    User.role == data.role,
                    User.quota_customized.is_(False),
                    User.status.in_(["pending", "approved", "rejected"]),
                )
                .order_by(User.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
            for user in users:
                # Customized accounts, and admins at or above the actor, keep theirs.
                if user.quota_customized or rank(user) >= rank(actor):
                    continue
                usage = self.repo.usage(user.id)
                if any(values[key] < usage[key.removeprefix("quota_")] for key in KEYS):
                    skipped.append(user.id)
                    continue
                for key, value in values.items():
                    setattr(user, key, value)
                updated.append(user.id)
                self.repo.audit(
                    actor.id, "account.quota.default_applied", user.id, **values
                )
        row.updated_by, row.updated_at = actor.id, datetime.now(UTC)
        self.repo.audit(
            actor.id,
            "settings.quota_defaults.changed",
            row.id,
            before=before,
            after=values,
            apply_to_existing=data.apply_to_existing,
            updated_user_ids=updated,
            skipped_user_ids=skipped,
        )
        self.db.commit()
        return {
            **self.public(data.role),
            "updated_count": len(updated),
            "skipped_count": len(skipped),
        }

    def apply_role_defaults(self, actor, user):
        """A role change moves an uncustomized account onto its new role's defaults."""
        if user.quota_customized:
            return
        values = self.values(role=user.role)
        usage = self.repo.usage(user.id)
        # Never shrink below what the account already holds.
        if any(values[key] < usage[key.removeprefix("quota_")] for key in KEYS):
            return
        for key, value in values.items():
            setattr(user, key, value)
        self.repo.audit(actor.id, "account.quota.default_applied", user.id, **values)
