"""Offline operator commands; never performs Proxmox mutations."""

import argparse
from getpass import getpass

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.api.schemas import NewPassword, Username
from app.core.db import SessionLocal
from app.core.security import passwords
from app.models import VM, Job, User, VMPasswordReset
from app.repositories.portal import PortalRepository


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("username")
    reset = sub.add_parser("reset-password")
    reset.add_argument("username")
    review = sub.add_parser("mark-interrupted")
    review.add_argument("job_id", type=int)
    args = parser.parse_args()
    with SessionLocal() as db:
        repo = PortalRepository(db)
        if args.command == "create-admin":
            try:
                args.username = TypeAdapter(Username).validate_python(args.username)
            except ValidationError:
                raise SystemExit(
                    "Username must be 3-32 characters: a-z, 0-9, underscore, dot or hyphen"
                ) from None
            password = getpass("Admin password (12+ characters): ")
            try:
                NewPassword(new_password=password)
            except ValidationError:
                raise SystemExit(
                    "Password requires 12-128 characters, uppercase, lowercase, digit and special character"
                ) from None
            if db.scalar(
                select(User).where(
                    User.username == args.username.lower(), User.status != "deleted"
                )
            ):
                raise SystemExit("Username already exists")
            user = User(
                username=args.username.lower(),
                password_hash=passwords.hash(password),
                role="admin",
                primary_admin=True,
                status="approved",
            )
            db.add(user)
            db.flush()
            repo.audit(user.id, "admin.bootstrap", user.id)
        elif args.command == "reset-password":
            from app.services.passwords import PasswordService

            user = db.scalar(
                select(User)
                .where(
                    User.username == args.username.strip().lower(),
                    User.status != "deleted",
                )
                .with_for_update()
            )
            if not user or user.status != "approved":
                raise SystemExit("Approved account not found")
            password = getpass("New Portal password: ")
            if password != getpass("Confirm new password: "):
                raise SystemExit("Passwords do not match")
            try:
                NewPassword(new_password=password)
            except ValidationError:
                raise SystemExit(
                    "Password requires 12-128 characters, uppercase, lowercase, digit and special character"
                ) from None
            user.password_hash = passwords.hash(password)
            user.auth_version += 1
            PasswordService(db).invalidate_codes(user.id)
            repo.audit(None, "operator.password.reset", user.id)
        else:
            job = db.get(Job, args.job_id, with_for_update=True)
            if not job or job.state != "running":
                raise SystemExit("Job must be running")
            job.state, job.error = (
                "needs_review",
                "Operator marked interrupted job for reconciliation",
            )
            if job.operation == "provision":
                db.get(VM, job.vm_id).status = "needs_review"
            if job.operation == "reset_password":
                reset = db.scalar(
                    select(VMPasswordReset).where(VMPasswordReset.job_id == job.id)
                )
                if reset:
                    reset.status, reset.password_encrypted = "needs_review", None
            repo.audit(None, "operator.mark_interrupted", job.id)
        db.commit()


if __name__ == "__main__":
    main()
