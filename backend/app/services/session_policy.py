from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models import SessionPolicy
from app.repositories.portal import PortalRepository


class SessionPolicyService:
    def __init__(self, db):
        self.db = db

    def public(self):
        row = self.db.get(SessionPolicy, 1)
        return {
            "token_minutes": row.token_minutes
            if row and row.token_minutes is not None
            else settings().token_minutes,
            "min_minutes": 5,
            "max_minutes": 1440,
            "applies_to": "new_logins",
        }

    def save(self, actor, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        row = self.db.scalar(
            select(SessionPolicy).where(SessionPolicy.id == 1).with_for_update()
        )
        if row is None:
            raise HTTPException(503, "Session policy schema missing; run migrations")
        old = self.public()["token_minutes"]
        row.token_minutes, row.updated_by, row.updated_at = (
            data.token_minutes,
            actor.id,
            datetime.now(UTC),
        )
        PortalRepository(self.db).audit(
            actor.id,
            "settings.session_duration.changed",
            1,
            old_minutes=old,
            new_minutes=row.token_minutes,
        )
        self.db.commit()
        return self.public()
