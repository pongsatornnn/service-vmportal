"""Short-lived, single-use console sessions; the browser never connects to PVE."""

import asyncio
import json
import logging
import secrets
import time
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from redis import Redis
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect

from app.adapters.proxmox import ProxmoxError, make_adapter
from app.api.identifiers import PortalID
from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.core.security import bearer, credential_expiry, current_user
from app.models import User
from app.repositories.portal import PortalRepository
from app.services.configuration import ConfigurationService
from app.services.portal import PortalService

router = APIRouter(prefix="/api")


def redis_client():
    return Redis.from_url(
        settings().redis_url, socket_timeout=2, socket_connect_timeout=2
    )


def console_vm(db, user, vm_id):
    vm = PortalService(db).managed_vm(user, vm_id)
    cfg = ConfigurationService(db).runtime(require_enabled=True)
    owner = db.get(User, vm.owner_id)
    if owner.status in {"deleting", "deleted"}:
        raise HTTPException(409, "Account deletion is in progress")
    if vm.status != "ready" or vm.vmid is None or vm.provider != cfg.proxmox_mode:
        raise HTTPException(409, "VM is not ready")
    if cfg.proxmox_mode != "real":
        raise HTTPException(409, "Console is available only for real VMs")
    from app.services.presence import PresenceService

    PresenceService(db).check(user, vm.id)
    return vm, cfg


@router.post("/vms/{vm_id}/console")
def prepare_console(
    vm_id: PortalID,
    user=Depends(current_user),
    db: Session = Depends(get_db),
    credentials=Depends(bearer),
):
    vm, cfg = console_vm(db, user, vm_id)
    store = redis_client()
    # One console per account; reservation expires even if the process crashes.
    reservation = secrets.token_urlsafe(32)
    slot = f"console:slot:{user.id}"
    if not store.set(slot, reservation, nx=True, ex=45):
        raise HTTPException(
            409, "A console session is already active; close it or wait for expiry"
        )
    adapter = make_adapter(cfg)
    try:
        PortalRepository(db).audit(user.id, "proxmox.console.requested", vm.id)
        db.commit()
        adapter.identity(vm.vmid, vm.hostname)
        power = adapter.call("GET", adapter.node + f"/qemu/{vm.vmid}/status/current")
        if not isinstance(power, dict) or power.get("status") != "running":
            raise HTTPException(409, "Start VM before opening console")
        proxy = adapter.call(
            "POST", adapter.node + f"/qemu/{vm.vmid}/vncproxy", websocket=1
        )
        ticket = secrets.token_urlsafe(32)
        store.setex(
            "console:ticket:" + ticket,
            30,
            json.dumps(
                {
                    "user": user.id,
                    "auth_version": user.auth_version,
                    "expires_at": min(
                        time.time() + 900, credential_expiry(credentials)
                    ),
                    "vm": vm.id,
                    "port": proxy["port"],
                    "ticket": proxy["ticket"],
                    "reservation": reservation,
                }
            ),
        )
        PortalRepository(db).audit(user.id, "proxmox.console.accepted", vm.id)
        db.commit()
        return {"ticket": ticket, "password": proxy["ticket"], "expires_in": 30}
    except ProxmoxError as exc:
        release(store, slot, reservation)
        raise HTTPException(
            502,
            "Console unavailable: check VM.Console at /vms/"
            + str(vm.vmid)
            + "; "
            + str(exc),
        ) from None
    except Exception:
        release(store, slot, reservation)
        raise
    finally:
        adapter.close()


def release(store, slot, reservation):
    store.eval(
        "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end; return 0",
        1,
        slot,
        reservation,
    )


@router.websocket("/console/socket")
async def console_socket(ws: WebSocket):
    # No cookies or tokens in URLs. Require a same-origin handshake plus a one-use protocol ticket.
    origin = urlsplit(ws.headers.get("origin", ""))
    if origin.scheme != "https" or origin.netloc != ws.headers.get("host"):
        await ws.close(code=1008)
        return
    protocols = ws.headers.get("sec-websocket-protocol", "").split(",")
    protocols = [p.strip() for p in protocols]
    if (
        len(protocols) != 2
        or protocols[0] != "portal"
        or not 30 <= len(protocols[1]) <= 64
    ):
        await ws.close(code=1008)
        return
    store = redis_client()
    raw = store.getdel("console:ticket:" + protocols[1])
    if not raw:
        await ws.close(code=1008)
        return
    data = json.loads(raw)
    slot = f"console:slot:{data['user']}"
    adapter = None
    deadline = data.get("expires_at", time.time() + 900)
    try:
        if deadline <= time.time():
            await ws.close(code=1008)
            return
        if store.get(slot) != data["reservation"].encode():
            await ws.close(code=1008)
            return
        store.expire(slot, 900)
        with SessionLocal() as db:
            user = db.get(User, data["user"])
            if (
                not user
                or user.status != "approved"
                or user.auth_version != data.get("auth_version", 0)
            ):
                raise HTTPException(403, "Account not approved")
            vm, cfg = console_vm(db, user, data["vm"])
            adapter = make_adapter(cfg)
            adapter.identity(vm.vmid, vm.hostname)
            query = urlencode({"port": data["port"], "vncticket": data["ticket"]})
            url = cfg.proxmox_url.rstrip("/").replace("https://", "wss://", 1)
            url += f"/api2/json/{adapter.node}/qemu/{vm.vmid}/vncwebsocket?{query}"
            PortalRepository(db).audit(user.id, "proxmox.console.open", vm.id)
            db.commit()
        await ws.accept(subprotocol="portal")
        async with connect(
            url,
            ssl=adapter.tls_context,
            additional_headers={
                "Authorization": adapter.client.headers["Authorization"]
            },
            max_size=2**22,
            open_timeout=15,
        ) as remote:

            async def upstream():
                while True:
                    await remote.send(await ws.receive_bytes())

            async def downstream():
                async for message in remote:
                    await ws.send_bytes(
                        message if isinstance(message, bytes) else message.encode()
                    )

            async def authorization_guard():
                while True:
                    await asyncio.sleep(5)
                    if time.time() >= deadline:
                        return
                    with SessionLocal() as db:
                        user = db.get(User, data["user"])
                        if (
                            not user
                            or user.status != "approved"
                            or user.auth_version != data.get("auth_version", 0)
                        ):
                            return

            tasks = [
                asyncio.create_task(upstream()),
                asyncio.create_task(downstream()),
                asyncio.create_task(authorization_guard()),
            ]
            try:
                await asyncio.wait(
                    tasks,
                    timeout=max(0, min(900, deadline - time.time())),
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        # Never log upstream URL, VNC ticket, terminal contents or guest credentials.
        logging.getLogger("portal.console").warning(
            "console_connection_failed", extra={"error_type": type(exc).__name__}
        )
    finally:
        if adapter:
            adapter.close()
        release(store, slot, data["reservation"])
        with SessionLocal() as db:
            PortalRepository(db).audit(
                data["user"], "proxmox.console.closed", data["vm"]
            )
            db.commit()
        try:
            await ws.close(code=1000)
        except RuntimeError:
            pass
