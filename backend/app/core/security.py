from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = passwords.hash("dummy-password-for-timing")


def token(user, minutes=None):
    return jwt.encode(
        {
            "sub": str(user.id),
            "ver": user.auth_version,
            "exp": datetime.now(UTC)
            + timedelta(
                minutes=settings().token_minutes if minutes is None else minutes
            ),
        },
        settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    try:
        payload = jwt.decode(
            credentials.credentials if credentials else "",
            settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        user = db.get(User, int(payload["sub"]))
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired; sign in again") from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Session invalid; sign in again") from None
    if user and payload.get("ver", 0) != user.auth_version:
        raise HTTPException(401, "Session expired; sign in again")
    if not user or user.status != "approved":
        raise HTTPException(403, "Account not approved")
    request.state.user_role = user.role
    return user


def admin(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user


def primary_admin(user: User = Depends(admin)):
    if not user.primary_admin:
        raise HTTPException(403, "Primary administrator required")
    return user


def manages_all(user):
    """Primary admins may operate any VM; other users only their own."""
    return user.role == "admin" and user.primary_admin


def credential_expiry(credentials):
    try:
        payload = jwt.decode(
            credentials.credentials if credentials else "",
            settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["exp"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired; sign in again") from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "Session invalid; sign in again") from None
