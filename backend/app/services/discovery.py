"""Read-only resource choices using draft credentials; never saves or enables setup."""

import math
import re
import ssl
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import SecretStr

from app.adapters.proxmox import RestProxmox
from app.core.config import settings
from app.services.configuration import ConfigurationService


def template_disks(config):
    disks = []
    for device, value in config.items():
        if not re.fullmatch(r"(?:scsi|sata|virtio)\d{1,2}", device) or not isinstance(
            value, str
        ):
            continue
        if (
            "cloudinit" in value
            or "media=cdrom" in value
            or value.split(",")[0] == "none"
        ):
            continue
        size = re.search(r"(?:^|,)size=(\d+(?:\.\d+)?)([KMGT]?)\b", value)
        gib = None
        if size:
            gib = max(
                1,
                math.ceil(
                    float(size[1])
                    * {
                        "": 1 / 1024**3,
                        "K": 1 / 1024**2,
                        "M": 1 / 1024,
                        "G": 1,
                        "T": 1024,
                    }[size[2]]
                ),
            )
        disks.append({"id": device, "minimum_gib": gib})
    order = str(config.get("boot", "")).removeprefix("order=").split(",")[0].split(";")
    known = {disk["id"] for disk in disks}
    boot = next((device for device in order if device in known), None)
    if (
        not boot
        and isinstance(config.get("bootdisk"), str)
        and config["bootdisk"] in known
    ):
        boot = config["bootdisk"]
    if not boot and len(disks) == 1:
        boot = disks[0]["id"]
    return sorted(disks, key=lambda d: d["id"]), boot


class DiscoveryService:
    def __init__(self, db):
        self.configuration = ConfigurationService(db)

    def discover(self, actor, data):
        if actor.role != "admin":
            raise HTTPException(403, "Admin required")
        url = urlsplit(data.url)
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
        try:
            if not data.ca_pem.strip():
                raise ValueError()
            ssl.create_default_context(cadata=data.ca_pem)
        except (ssl.SSLError, ValueError):
            raise HTTPException(422, "A valid trusted CA PEM is required") from None
        secret = data.token_secret.get_secret_value() if data.token_secret else ""
        if not secret:
            row = self.configuration.row()
            if (
                row.data.get("url", "").rstrip("/") != data.url.rstrip("/")
                or row.data.get("token_id") != data.token_id
                or not row.token_encrypted
            ):
                raise HTTPException(422, "Enter token secret for this connection")
            from cryptography.fernet import InvalidToken

            try:
                secret = (
                    self.configuration.cipher()
                    .decrypt(row.token_encrypted.encode())
                    .decode()
                )
            except InvalidToken:
                raise HTTPException(
                    503,
                    "Cannot decrypt API secret; restore the original encryption key",
                ) from None
        if len(secret) > 4096 or "\n" in secret or "\r" in secret:
            raise HTTPException(422, "Invalid token secret")
        config = settings().model_copy(
            update={
                "proxmox_url": data.url.rstrip("/"),
                "proxmox_token_id": data.token_id,
                "proxmox_token_secret": SecretStr(secret),
                "proxmox_ca_pem": data.ca_pem,
                "proxmox_node": data.node or "",
                "proxmox_mode": "real",
            }
        )
        adapter = RestProxmox(config)
        deadline = time.monotonic() + 40
        warnings = {}

        def read(section, path, expected=list, **params):
            # Reads only: retry a transient transport failure once, within the
            # shared discovery budget. Never retry ACL or malformed responses.
            for attempt in range(2):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    warnings[section] = "timeout"
                    return None
                try:
                    response = adapter.client.get(
                        path, params=params, timeout=min(7, remaining)
                    )
                    if response.status_code in {401, 403}:
                        warnings[section] = "permission"
                        return None
                    if response.status_code != 200:
                        warnings[section] = "unavailable"
                        return None
                    value = response.json().get("data")
                    if not isinstance(value, expected) or (
                        expected is list and any(not isinstance(v, dict) for v in value)
                    ):
                        warnings[section] = "invalid_response"
                        return None
                    return value
                except httpx.TransportError:
                    if attempt == 0:
                        continue
                    warnings[section] = "connection"
                    return None
                except (httpx.HTTPError, ValueError, AttributeError):
                    warnings[section] = "invalid_response"
                    return None

        def choices(rows, key):
            return sorted(
                {
                    row[key]
                    for row in rows or []
                    if isinstance(row.get(key), str)
                    and re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", row[key])
                }
            )

        try:
            nodes = read("nodes", "nodes")
            pools = read("pools", "pools")
            result = {
                "nodes": choices(nodes, "node"),
                "pools": choices(pools, "poolid"),
                "storages": [],
                "bridges": [],
                "templates": [],
                "disks": [],
                "boot_disk": None,
                "warnings": warnings,
            }
            if data.node:
                base = f"nodes/{data.node}"
                storage = read(
                    "storages", base + "/storage", content="images", enabled=1
                )
                result["storages"] = choices(
                    [
                        s
                        for s in storage or []
                        if s.get("active") in (1, True)
                        and "images" in str(s.get("content", "")).split(",")
                    ],
                    "storage",
                )
                network = read("bridges", base + "/network")
                result["bridges"] = choices(
                    [
                        n
                        for n in network or []
                        if n.get("type") in {"bridge", "OVSBridge", "vnet"}
                    ],
                    "iface",
                )
                vms = read("templates", base + "/qemu")
                result["templates"] = sorted(
                    [
                        {"id": v["vmid"], "name": str(v.get("name", ""))[:128]}
                        for v in vms or []
                        if v.get("template") in (1, True)
                        and type(v.get("vmid")) is int
                        and 100 <= v["vmid"] <= 999999999
                    ],
                    key=lambda v: v["id"],
                )
                if data.template:
                    cfg = read(
                        "disks", base + f"/qemu/{data.template}/config", expected=dict
                    )
                    if cfg is not None:
                        if cfg.get("template") in (1, True):
                            result["disks"], result["boot_disk"] = template_disks(cfg)
                        else:
                            warnings["disks"] = "not_template"
            return result
        finally:
            adapter.close()
