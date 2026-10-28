from sqlalchemy import select

from app.models import AuditLog, User, VMIDAllocator, VMRequest


class PortalRepository:
    def __init__(self, db):
        self.db = db

    def lock_user(self, user_id):
        return self.db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def usage(self, user_id, include_pending=False):
        # Pending requests reserve quota so a user cannot queue more than allowed.
        statuses = ["approved", "pending"] if include_pending else ["approved"]
        rows = self.db.scalars(
            select(VMRequest).where(
                VMRequest.owner_id == user_id, VMRequest.status.in_(statuses)
            )
        ).all()
        return dict(
            vms=len(rows),
            cpu=sum(r.cpu for r in rows),
            ram=sum(r.ram for r in rows),
            disk=sum(r.disk for r in rows),
        )

    def display_names(self, ids):
        """Readable names of the admins who decided or reviewed records."""
        ids = {i for i in ids if i is not None}
        if not ids:
            return {}
        return {
            u.id: " ".join(filter(None, [u.first_name, u.last_name])) or u.username
            for u in self.db.scalars(select(User).where(User.id.in_(ids)))
        }

    def allocate_vmid(self):
        row = self.db.scalar(
            select(VMIDAllocator).where(VMIDAllocator.id == 1).with_for_update()
        )
        if row is None:
            raise RuntimeError("VMID allocator missing; run migrations")
        value = row.next_id
        row.next_id += 1
        self.db.flush()
        return value

    def audit(self, actor, action, target, **details):
        self.db.add(
            AuditLog(actor_id=actor, action=action, target=str(target), details=details)
        )
