import secrets
import ssl
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from app.adapters.proxmox import ProxmoxError, make_adapter
from app.core.config import settings
from app.core.security import passwords
from app.models import VM, Job, PortalConfiguration, User, VMTemplate
from app.repositories.portal import PortalRepository

IDENTITY_FIELDS = {
    "mode",
    "url",
    "node",
    "pool",
    "storage",
}
# Older setups chose one template here; templates now have their own list.
LEGACY_TEMPLATE_FIELDS = ("template", "template_disk_gb", "disk_device")


class ConfigurationService:
    def __init__(self, db):
        self.db = db
        self.repo = PortalRepository(db)

    def row(self, lock=False):
        query = (
            select(PortalConfiguration)
            .where(PortalConfiguration.id == 1)
            .execution_options(populate_existing=True)
        )
        if lock:
            query = query.with_for_update()
        row = self.db.scalar(query)
        if not row:
            raise HTTPException(503, "Setup schema missing; run migrations")
        return row

    def has_admin(self):
        return (
            self.db.scalar(select(User.id).where(User.role == "admin").limit(1))
            is not None
        )

    def status(self):
        row = self.row()
        return {
            "first_admin_required": not self.has_admin(),
            "configured": bool(row.data),
            "connection_verified": bool(row.data)
            and row.tested_revision == row.revision,
            "enabled": row.enabled,
        }

    def bootstrap(self, data):
        self.row(lock=True)
        if self.has_admin():
            raise HTTPException(409, "Initial administrator already exists")
        expected = settings().bootstrap_token.get_secret_value()
        if not expected or not secrets.compare_digest(data.setup_token, expected):
            raise HTTPException(403, "Invalid setup token")
        user = User(
            username=str(data.username).lower(),
            password_hash=passwords.hash(data.password),
            role="admin",
            primary_admin=True,
            status="approved",
        )
        self.db.add(user)
        self.db.flush()
        self.repo.audit(user.id, "setup.admin.created", user.id)
        self.db.commit()
        return {"ok": True}

    def cipher(self):
        try:
            return Fernet(settings().encryption_key.get_secret_value().encode())
        except (ValueError, TypeError):
            raise HTTPException(
                503, "Server encryption key is not configured"
            ) from None

    def public(self):
        row = self.row()
        return {
            "values": row.data,
            "has_token_secret": bool(row.token_encrypted),
            "revision": row.revision,
            "connection_verified": bool(row.data)
            and row.revision == row.tested_revision,
            "enabled": row.enabled,
        }

    def save(self, actor, data):
        row = self.row(lock=True)
        if self.db.scalar(select(Job.id).where(Job.state == "running").limit(1)):
            raise HTTPException(
                409, "Wait for running jobs before changing configuration"
            )
        values = data.model_dump(exclude={"token_secret"})
        networks = (
            data.network_bridges
            if data.network_bridges is not None
            else [data.bridge]
            + ([data.secondary_bridge] if data.secondary_bridge else [])
        )
        values.update(
            network_bridges=networks,
            bridge=networks[0],
            secondary_bridge=networks[1] if len(networks) > 1 else "",
        )
        url = urlsplit(values["url"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise HTTPException(
                422, "Endpoint must be an HTTPS origin without credentials or path"
            )
        values["url"] = values["url"].rstrip("/")
        for key in LEGACY_TEMPLATE_FIELDS:
            if values[key] is None:
                values[key] = row.data.get(key)

        previous_networks = row.data.get("network_bridges") or [
            row.data.get("bridge", "")
        ] + ([row.data["secondary_bridge"]] if row.data.get("secondary_bridge") else [])
        if previous_networks != networks and self.db.scalar(
            select(Job.id)
            .where(Job.operation == "provision", Job.state.in_(["queued", "running"]))
            .limit(1)
        ):
            raise HTTPException(
                409, "Wait for pending provisioning jobs before changing network"
            )
        if any(bridge not in data.bridge_allowlist for bridge in networks):
            raise HTTPException(422, "Bridge must belong to the allowlist")
        if data.mode == "real":
            try:
                ssl.create_default_context(cadata=data.ca_pem)
            except (ssl.SSLError, ValueError):
                raise HTTPException(422, "A valid trusted CA PEM is required") from None
            if not data.ca_pem.strip():
                raise HTTPException(422, "CA PEM required")
        if self.db.scalar(select(VM.id).limit(1)) and any(
            row.data.get(key) != values[key] for key in IDENTITY_FIELDS
        ):
            raise HTTPException(
                409,
                "Infrastructure identity is locked while VM records exist; use a separate portal for another cluster",
            )
        secret = data.token_secret.get_secret_value() if data.token_secret else ""
        if len(secret) > 4096 or "\n" in secret or "\r" in secret:
            raise HTTPException(422, "Invalid token secret")
        if secret:
            row.token_encrypted = self.cipher().encrypt(secret.encode()).decode()
        if data.mode == "real" and not row.token_encrypted:
            raise HTTPException(422, "Token secret required for real connection")
        row.data = values
        row.revision += 1
        row.tested_revision = None
        row.enabled = False
        self.repo.audit(actor.id, "setup.connection.saved", row.revision)
        self.db.commit()
        return self.public()

    def runtime(self, lock=False, require_enabled=False):
        base = settings()
        if not base.require_setup:
            return base
        row = self.row(lock)
        if not row.data:
            raise HTTPException(409, "Complete system setup first")
        if require_enabled and (not row.enabled or row.tested_revision != row.revision):
            raise HTTPException(
                409, "Verify connection and enable the system in Setup first"
            )
        values = row.data
        patch = {
            "proxmox_" + key: values[key]
            for key in ("url", "node", "pool", "storage", "bridge")
        }
        patch.update(
            proxmox_mode=values["mode"],
            proxmox_secondary_bridge=values.get("secondary_bridge", ""),
            proxmox_network_bridges=values.get("network_bridges")
            or [values["bridge"]]
            + ([values["secondary_bridge"]] if values.get("secondary_bridge") else []),
            bridge_allowlist=",".join(values["bridge_allowlist"]),
            proxmox_ca_pem=values["ca_pem"],
            **self.default_template(row, values, base),
            ssh_password_snippet=values.get("ssh_password_snippet", ""),
            provisioning_enabled=row.enabled,
        )
        if row.token_encrypted:
            try:
                patch["proxmox_token_secret"] = SecretStr(
                    self.cipher().decrypt(row.token_encrypted.encode()).decode()
                )
            except InvalidToken:
                raise HTTPException(
                    503,
                    "Cannot decrypt API secret; restore the original encryption key",
                ) from None
        patch["proxmox_token_id"] = values["token_id"]
        return base.model_copy(update=patch)

    def default_template(self, row, values, base):
        """Clone source for checks not tied to one request (e.g. VMID anchoring)."""
        rows = self.db.scalars(select(VMTemplate).order_by(VMTemplate.id)).all()

        def verified(t):
            return (
                t.verified_revision == t.revision
                and t.verified_config_revision == row.revision
            )

        chosen = next(
            (t for t in rows if t.enabled and verified(t)),
            next((t for t in rows if verified(t)), rows[0] if rows else None),
        )
        if chosen:
            return {
                "proxmox_template": chosen.vmid,
                "disk_device": chosen.disk_device,
                "template_disk_gb": chosen.min_disk_gb,
            }
        return {
            "proxmox_template": values.get("template") or base.proxmox_template,
            "disk_device": values.get("disk_device") or base.disk_device,
            "template_disk_gb": values.get("template_disk_gb") or base.template_disk_gb,
        }

    def check(self, actor):
        row = self.row(lock=True)
        config = self.runtime()
        self.repo.audit(actor.id, "proxmox.readonly.check", row.revision)
        adapter = None
        try:
            adapter = make_adapter(config)
            # Connection only; each template is verified on its own page.
            adapter.check()
            row.tested_revision = row.revision
            self.repo.audit(actor.id, "proxmox.readonly.verified", row.revision)
            self.db.commit()
            return {
                "ok": True,
                "mode": config.proxmox_mode,
                "tls_verified": config.proxmox_mode == "real",
            }
        except Exception as exc:
            row.tested_revision = None
            row.enabled = False
            self.repo.audit(
                actor.id,
                "proxmox.readonly.failed",
                row.revision,
                error_type=type(exc).__name__,
            )
            self.db.commit()
            raise HTTPException(
                502,
                str(exc)
                if isinstance(exc, ProxmoxError)
                else "Connection failed; check endpoint, CA and token",
            ) from None
        finally:
            if adapter:
                adapter.close()

    def activate(self, actor, data):
        row = self.row(lock=True)
        if data.enabled:
            if not row.data or row.tested_revision != row.revision:
                raise HTTPException(
                    409, "Read-only verification required for current configuration"
                )
            if row.data["mode"] == "real" and not data.confirm_real_execution:
                raise HTTPException(
                    422, "Explicit confirmation required for real VM operations"
                )
        row.enabled = data.enabled
        self.repo.audit(
            actor.id, "setup.execution.changed", row.revision, enabled=data.enabled
        )
        self.db.commit()
        return self.public()
