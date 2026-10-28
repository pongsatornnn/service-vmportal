#!/usr/bin/env python3
"""Reset an existing Portal administrator password from the server terminal."""

import argparse
import os
import sys
import warnings
from getpass import GetPassWarning, getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = "รหัสผ่านต้องยาว 12–128 ตัว มี A–Z, a–z, ตัวเลข และอักขระพิเศษ"


def prompt_password():
    from app.api.schemas import validate_password

    print(POLICY)
    while True:
        # Never let getpass fall back to echoing a password into redirected input.
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("New password: ")
            confirmation = getpass("Confirm new password: ")
        if password != confirmation:
            print("รหัสผ่านไม่ตรงกัน กรุณากรอกใหม่")
            continue
        try:
            return validate_password(password)
        except ValueError:
            print(POLICY)


def reset_admin(db, username=None):
    from app.core.security import passwords
    from app.models import User
    from app.repositories.portal import PortalRepository
    from app.services.passwords import PasswordService
    from sqlalchemy import select

    admins = db.scalars(
        select(User)
        .where(User.role == "admin", User.status == "approved")
        .order_by(User.id)
    ).all()
    if not admins:
        raise SystemExit("ไม่พบบัญชี Admin ที่ใช้งานอยู่")
    if username is None and len(admins) > 1:
        print("มี Admin หลายบัญชี: " + ", ".join(user.username for user in admins))
        username = input("Admin username: ").strip()
    selected = next(
        (
            user
            for user in admins
            if username is None or user.username == username.strip().lower()
        ),
        None,
    )
    if selected is None:
        raise SystemExit("ไม่พบบัญชี Admin ที่ใช้งานอยู่ตามชื่อที่ระบุ")
    print(f"Admin: {selected.username}")
    password_hash = passwords.hash(prompt_password())
    # Recheck and lock after prompting so a concurrent account change cannot
    # reset a deleted, suspended, or non-administrator account.
    user = db.scalar(
        select(User)
        .where(User.id == selected.id, User.role == "admin", User.status == "approved")
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise SystemExit("สถานะบัญชีเปลี่ยนแล้ว ยกเลิกการรีเซ็ตรหัสผ่าน")
    user.password_hash = password_hash
    user.auth_version += 1
    PasswordService(db).invalidate_codes(user.id)
    PortalRepository(db).audit(
        None, "operator.password.reset", user.id, source="reset_admin_password.py"
    )
    db.commit()
    print(f"ตั้งรหัสผ่านใหม่ให้ {user.username} แล้ว กรุณาเข้าสู่ระบบใหม่ทุกอุปกรณ์")


def main():
    parser = argparse.ArgumentParser(
        description="Reset an existing Portal admin password using hidden prompts."
    )
    parser.add_argument(
        "--username",
        help="Admin username; optional when there is only one administrator",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Service environment file (default: native portal.env or project .env)",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from dotenv import dotenv_values
        from pydantic import ValidationError
        from sqlalchemy.exc import SQLAlchemyError

        private = args.env_file or Path.home() / ".config/vmportal/portal.env"
        if args.env_file and not private.is_file():
            raise SystemExit("ไม่พบไฟล์ตั้งค่าที่ระบุ")
        if not private.is_file():
            private = Path("/etc/vmportal/portal.env")
        if not private.is_file():
            private = ROOT / ".env"
        if private.is_file():
            values = dotenv_values(private, interpolate=False)
            os.environ.update(
                {key: value for key, value in values.items() if value is not None}
            )
        try:
            from app.core.db import SessionLocal

            with SessionLocal() as db:
                reset_admin(db, args.username)
        except ValidationError:
            raise SystemExit(
                "การตั้งค่า Server ไม่ครบหรือไม่ถูกต้อง กรุณาตรวจไฟล์ environment"
            ) from None
        except SQLAlchemyError:
            raise SystemExit(
                "เชื่อมต่อหรือบันทึกฐานข้อมูลไม่สำเร็จ กรุณาตรวจการตั้งค่าและบริการฐานข้อมูล"
            ) from None
    except ImportError:
        raise SystemExit(
            "กรุณารันด้วย .venv/bin/python และติดตั้ง dependencies ของ Backend ก่อน"
        ) from None
    except (KeyboardInterrupt, EOFError, GetPassWarning):
        raise SystemExit("ยกเลิกแล้ว ยังไม่ได้เปลี่ยนรหัสผ่าน") from None


if __name__ == "__main__":
    main()
