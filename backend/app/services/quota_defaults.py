from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import manages_all
from app.models import QuotaDefaults, User
from app.repositories.portal import PortalRepository

KEYS = ("quota_vms", "quota_cpu", "quota_ram", "quota_disk")


class QuotaDefaultsService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def row(self, lock=False):
        query = (
            select(QuotaDefaults)
            .where(QuotaDefaults.id == 1)
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if row is None:
            raise HTTPException(503, "Quota defaults schema missing; run migrations")
        return row

    def values(self, lock=False):
        row = self.row(lock)
        return {key: getattr(row, key) for key in KEYS}

    def public(self):
        row = self.row()
        return {
            **{key: getattr(row, key) for key in KEYS},
            "updated_at": row.updated_at,
        }

    def save(self, actor, data):
        if not manages_all(actor):
            raise HTTPException(403, "Primary administrator required")
        row = self.row(lock=True)
        before = {key: getattr(row, key) for key in KEYS}
        values = data.model_dump(exclude={"apply_to_existing"})
        for key, value in values.items():
            setattr(row, key, value)
        updated, skipped = [], []
        if data.apply_to_existing:
            users = self.db.scalars(
                select(User)
                .where(
                    User.role == "user",
                    User.quota_customized.is_(False),
                    User.status.in_(["pending", "approved", "rejected"]),
                )
                .order_by(User.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
            for user in users:
                if user.quota_customized:
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
            1,
            before=before,
            after=values,
            apply_to_existing=data.apply_to_existing,
            updated_user_ids=updated,
            skipped_user_ids=skipped,
        )
        self.db.commit()
        return {
            **self.public(),
            "updated_count": len(updated),
            "skipped_count": len(skipped),
        }
