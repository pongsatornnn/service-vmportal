import ipaddress
import re
import ssl
import time
from typing import Protocol
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken

# Growing a freshly cloned disk can hold the HTTP response well past 30s.
RESIZE_TIMEOUT = 180
GIB = 1024**3
SIZE_UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": GIB, "T": 1024**4}


class ProxmoxAdapter(Protocol):
    def close(self): ...
    def check(self): ...
    def validate_template(self, request): ...
    def validate_existing_clone(self, vmid, request): ...
    def available(self, vmid: int) -> bool: ...
    def clone(self, vmid: int, name: str) -> str: ...
    def wait(self, upid: str): ...
    def task_status(self, upid: str) -> dict: ...
    def validate_password_reset(self, vmid: int): ...
    def reset_password(self, vmid: int, username: str, encrypted: str): ...
    def clear_cloudinit_password(self, vmid: int) -> bool: ...
    def configure(self, vmid: int, request): ...
    def verify_ssh_password_policy(self, vmid: int, guest_username: str): ...
    def regenerate_cloudinit(self, vmid: int): ...
    def resize(self, vmid: int, disk: int): ...
    def disk_bytes(self, vmid: int) -> int: ...
    def power(self, vmid: int, operation: str) -> str: ...
    def identity(self, vmid: int, hostname: str): ...
    def ensure_stopped(self, vmid: int): ...
    def runtime(self, vmid: int) -> dict: ...
    def inspect_presence(self, vmid: int, hostname: str) -> dict: ...
    def node_health(self) -> dict: ...
    def delete(self, vmid: int, hostname: str) -> str: ...


class ProxmoxError(RuntimeError):
    pass


class ProxmoxHTTPError(ProxmoxError):
    def __init__(self, status_code, method, path):
        self.status_code = status_code
        self.path = path
        super().__init__(
            f"Proxmox HTTP {status_code}: {method} {path}; inspect ACL and Proxmox task log"
        )


class RestProxmox:
    def __init__(self, config):
        self.config = config
        if (
            not config.proxmox_token_id
            or not config.proxmox_token_secret.get_secret_value()
        ):
            raise ProxmoxError("Proxmox token credentials missing")
        context = (
            ssl.create_default_context(cadata=config.proxmox_ca_pem)
            if config.proxmox_ca_pem
            else ssl.create_default_context(cafile=config.proxmox_ca)
        )
        self.tls_context = context
        self.client = httpx.Client(
            base_url=config.proxmox_url.rstrip("/") + "/api2/json/",
            verify=context,
            headers={
                "Authorization": f"PVEAPIToken={config.proxmox_token_id}={config.proxmox_token_secret.get_secret_value()}"
            },
            timeout=30,
            follow_redirects=False,
        )
        self.node = f"nodes/{config.proxmox_node}"

    def call(self, method, path, request_timeout=None, **data):
        # A connect timeout occurs before any HTTP request is sent. Retry it
        # once for VM configuration only; ambiguous write/read failures stop.
        config_connect_retry = method == "PUT" and bool(
            re.fullmatch(r"nodes/[^/]+/qemu/[0-9]+/config", path)
        )
        attempts = 3 if method == "GET" else 2 if config_connect_retry else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(
                    method,
                    path,
                    params=data if method == "GET" else None,
                    data=data if method != "GET" else None,
                    **({"timeout": request_timeout} if request_timeout else {}),
                )
                break
            except httpx.TransportError as exc:
                if (method == "GET" and attempt < 2) or (
                    config_connect_retry
                    and isinstance(exc, httpx.ConnectTimeout)
                    and attempt == 0
                ):
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise ProxmoxError(
                    f"Proxmox connection interrupted: {method} {path}; "
                    + (
                        "read retries exhausted"
                        if method == "GET"
                        else "outcome uncertain; admin review required"
                    )
                ) from None
        if response.is_error:
            # Do not expose response bodies or credentials to the portal.
            raise ProxmoxHTTPError(response.status_code, method, path)
        return response.json()["data"]

    def close(self):
        self.client.close()

    def check(self):
        if self.config.ssh_password_snippet:
            self.validate_ssh_password_snippet()
        return {
            "version": self.call("GET", "version"),
            "node": self.call("GET", self.node + "/status"),
        }

    def validate_template(self, request):
        cfg = self.call(
            "GET", self.node + f"/qemu/{self.config.proxmox_template}/config"
        )
        if int(cfg.get("template", 0)) != 1:
            raise ProxmoxError("Configured source is not a template")
        self._validate_provision_config(cfg, request)

    def validate_existing_clone(self, vmid, request):
        cfg = self.call("GET", self.node + f"/qemu/{vmid}/config")
        if cfg.get("template") or cfg.get("lock"):
            raise ProxmoxError("Existing clone is locked or is a template")
        self._validate_provision_config(cfg, request)

    def _validate_provision_config(self, cfg, request):
        networks = self.network_bridges()
        allowed_nics = {f"net{index}" for index in range(len(networks))}
        if len(networks) > 1 and re.search(
            r"(?:^|,)network=", str(cfg.get("cicustom", ""))
        ):
            raise ProxmoxError(
                "Custom Cloud-Init network overrides DHCP; review template"
            )
        if any(
            re.fullmatch(r"net[0-9]+", key) and key not in allowed_nics for key in cfg
        ):
            raise ProxmoxError("Template network devices exceed configured interfaces")
        if not any("cloudinit" in str(value).lower() for value in cfg.values()):
            raise ProxmoxError("Template Cloud-Init drive missing")
        if getattr(request, "auth_method", "ssh_key") == "password":
            if re.search(r"(?:^|,)user=", str(cfg.get("cicustom", ""))):
                raise ProxmoxError(
                    "Custom Cloud-Init user-data overrides VM passwords; review template"
                )
            self.authentication_params(
                request
            )  # Fail before cloning if password cannot be decrypted.
        if getattr(request, "ssh_password_login", False):
            expected = "vendor=" + self.config.ssh_password_snippet
            if cfg.get("cicustom") and cfg["cicustom"] != expected:
                raise ProxmoxError(
                    "Template custom Cloud-Init conflicts with the portal SSH password policy"
                )
            self.validate_ssh_password_snippet()
        disk = str(cfg.get(self.config.disk_device, ""))
        size = re.search(r"(?:^|,)size=([0-9.]+)([KMGT])(?:,|$)", disk)
        if not size:
            raise ProxmoxError("Cannot verify template disk size")
        gib = (
            float(size[1])
            * {"K": 1 / 1048576, "M": 1 / 1024, "G": 1, "T": 1024}[size[2]]
        )
        if request.disk < gib:
            raise ProxmoxError("Requested disk smaller than actual template disk")

    def validate_ssh_password_snippet(self):
        volume = self.config.ssh_password_snippet
        if not re.fullmatch(
            r"[A-Za-z0-9_.-]+:snippets/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.ya?ml", volume
        ):
            raise ProxmoxError(
                "Admin must configure a valid SSH password vendor snippet in Setup"
            )
        storage = volume.split(":", 1)[0]
        try:
            status = self.call("GET", self.node + f"/storage/{storage}/status")
        except ProxmoxError:
            raise ProxmoxError(
                f"Cannot inspect SSH policy storage; check Datastore.AllocateSpace for snippet access at /storage/{storage} and snippets content support"
            ) from None
        if (
            not status.get("active")
            or not status.get("enabled")
            or "snippets" not in status.get("content", "").split(",")
        ):
            raise ProxmoxError(
                "SSH policy storage is inactive or does not support snippets"
            )
        # Listing snippet files may require Datastore.Allocate on some PVE releases.
        # Do not widen permissions: the installer checks the file, and regeneration checks it before start.

    def verify_ssh_password_policy(self, vmid, guest_username):
        # PVE's dump API supports only user/network/meta, not vendor contents.
        # Verify the applied reference and user; the administrator installs the reviewed static file.
        config = self.call("GET", self.node + f"/qemu/{vmid}/config")
        if (
            config.get("cicustom") != "vendor=" + self.config.ssh_password_snippet
            or config.get("ciuser") != guest_username
        ):
            raise ProxmoxError(
                "SSH password policy reference or guest username was not applied; VM was not started"
            )

    def regenerate_cloudinit(self, vmid):
        return self.call("PUT", self.node + f"/qemu/{vmid}/cloudinit")

    def available(self, vmid):
        response = self.client.get("cluster/nextid", params={"vmid": vmid})
        if response.status_code == 400 and "already exists" in response.text.lower():
            return False
        if response.is_error:
            raise ProxmoxError(
                f"VMID preflight HTTP {response.status_code}; requires cluster nextid access"
            )
        return int(response.json()["data"]) == vmid

    def clone(self, vmid, name):
        return self.call(
            "POST",
            self.node + f"/qemu/{self.config.proxmox_template}/clone",
            newid=vmid,
            name=name,
            full=1,
            pool=self.config.proxmox_pool,
            storage=self.config.proxmox_storage,
            target=self.config.proxmox_node,
        )

    def task_status(self, upid):
        return self.call(
            "GET", self.node + "/tasks/" + quote(upid, safe="") + "/status"
        )

    def wait(self, upid):
        for _ in range(600):
            result = self.call(
                "GET", self.node + "/tasks/" + quote(upid, safe="") + "/status"
            )
            if result["status"] == "stopped":
                if result.get("exitstatus") != "OK":
                    raise ProxmoxError("Proxmox task failed; inspect task log and ACL")
                return
            time.sleep(2)
        raise ProxmoxError("Task wait timeout; admin reconciliation required")

    def authentication_params(self, request):
        if getattr(request, "auth_method", "ssh_key") == "password":
            try:
                password = (
                    Fernet(self.config.encryption_key.get_secret_value().encode())
                    .decrypt(request.password_encrypted.encode())
                    .decode()
                )
            except (InvalidToken, ValueError, AttributeError, TypeError):
                raise ProxmoxError(
                    "Cannot prepare VM password; check encryption key and request credential"
                ) from None
            return {"cipassword": password, "delete": "sshkeys"}
        return {"sshkeys": quote(request.ssh_key, safe=""), "delete": "cipassword"}

    def network_bridges(self):
        networks = getattr(self.config, "proxmox_network_bridges", None) or [
            self.config.proxmox_bridge
        ] + (
            [self.config.proxmox_secondary_bridge]
            if getattr(self.config, "proxmox_secondary_bridge", "")
            else []
        )
        if not 1 <= len(networks) <= 32:
            raise ProxmoxError("Invalid network interface count")
        for index, bridge in enumerate(networks):
            if (
                not isinstance(bridge, str)
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", bridge)
                or bridge not in self.config.bridge_allowlist.split(",")
            ):
                raise ProxmoxError(
                    "Secondary bridge not allowed" if index else "Bridge not allowed"
                )
        return networks

    def configure(self, vmid, request):
        policy = {}
        for index, bridge in enumerate(self.network_bridges()):
            policy[f"net{index}"] = f"virtio,bridge={bridge}"
            policy[f"ipconfig{index}"] = "ip=dhcp"
        if getattr(request, "ssh_password_login", False):
            policy["cicustom"] = "vendor=" + self.config.ssh_password_snippet
        return self.call(
            "PUT",
            self.node + f"/qemu/{vmid}/config",
            cores=request.cpu,
            sockets=1,
            memory=request.ram,
            balloon=0,
            ciuser=getattr(request, "guest_username", "ubuntu"),
            onboot=0,
            agent=1,
            **self.authentication_params(request),
            **policy,
        )

    def resize(self, vmid, disk):
        return self.call(
            "PUT",
            self.node + f"/qemu/{vmid}/resize",
            disk=self.config.disk_device,
            size=f"{disk}G",
            request_timeout=RESIZE_TIMEOUT,
        )

    def disk_bytes(self, vmid):
        cfg = self.call("GET", self.node + f"/qemu/{vmid}/config")
        match = re.search(
            r"(?:^|,)size=([0-9]+)([KMGT]?)(?:,|$)",
            str(cfg.get(self.config.disk_device, "")),
        )
        if not match:
            raise ProxmoxError("Cannot read VM disk size; admin review required")
        return int(match.group(1)) * SIZE_UNITS[match.group(2)]

    def power(self, vmid, operation):
        if operation not in {"start", "stop", "shutdown", "reboot"}:
            raise ValueError("Unsupported action")
        return self.call("POST", self.node + f"/qemu/{vmid}/status/{operation}")

    def identity(self, vmid, hostname):
        cfg = self.call("GET", self.node + f"/qemu/{vmid}/config")
        if cfg.get("template") or cfg.get("name") != hostname or cfg.get("lock"):
            raise ProxmoxError("VM identity mismatch; admin review required")

    def inspect_presence(self, vmid, hostname):
        """Read-only, on-demand proof. A filtered inventory alone never proves absence."""
        self._presence_deadline = time.monotonic() + 15
        config_read = False
        try:
            cfg = self._presence_read(self.node + f"/qemu/{vmid}/config")
            config_read = True
        except ProxmoxError:
            cfg = None
        if config_read:
            if not isinstance(cfg, dict):
                return {"state": "unverified", "reason": "invalid_response"}
            if cfg.get("template") or cfg.get("name") != hostname:
                return {"state": "unverified", "reason": "identity_mismatch"}
            if cfg.get("lock"):
                return {"state": "unverified", "reason": "locked"}
            return {"state": "present"}
        try:
            resources = self._presence_read("cluster/resources", type="vm")
            if not isinstance(resources, list):
                return {"state": "unverified", "reason": "invalid_response"}
            if any(not isinstance(r, dict) for r in resources):
                return {"state": "unverified", "reason": "invalid_response"}
            matches = [
                r
                for r in resources
                if isinstance(r, dict) and str(r.get("vmid")) == str(vmid)
            ]
            if matches:
                record = matches[0]
                if (
                    len(matches) != 1
                    or record.get("type") != "qemu"
                    or record.get("name") != hostname
                ):
                    return {"state": "unverified", "reason": "identity_mismatch"}
                if record.get("node") != self.config.proxmox_node:
                    return {"state": "unverified", "reason": "moved"}
                return {"state": "unverified", "reason": "config_unreadable"}
            # /cluster/nextid?vmid uses the unfiltered cluster VMID namespace.
            # Demand successful, exact responses twice; HTTP errors are not proof.
            self._confirm_unused_vmid(vmid)
            first = self._healthy_cluster()
            self._presence_template_anchor()
            node_status = self._presence_read(self.node + "/status")
            if (
                not isinstance(node_status, dict)
                or not isinstance(node_status.get("uptime"), (int, float))
                or node_status["uptime"] <= 0
            ):
                return {"state": "unverified", "reason": "invalid_response"}
            second_resources = self._presence_read("cluster/resources", type="vm")
            if not isinstance(second_resources, list):
                return {"state": "unverified", "reason": "invalid_response"}
            if any(not isinstance(r, dict) for r in second_resources):
                return {"state": "unverified", "reason": "invalid_response"}
            if any(str(r.get("vmid")) == str(vmid) for r in second_resources):
                return {"state": "unverified", "reason": "changed_during_check"}
            if self._healthy_cluster() != first:
                return {"state": "unverified", "reason": "changed_during_check"}
            self._confirm_unused_vmid(vmid)
            return {"state": "missing", "reason": "cluster_vmid_unused_twice"}
        except ProxmoxHTTPError as exc:
            reason = "provider_error"
            if exc.status_code in {401, 403}:
                reason = (
                    "cluster_permission"
                    if exc.path == "cluster/status"
                    else "permission"
                )
            return {"state": "unverified", "reason": reason}
        except (ProxmoxError, ValueError, TypeError, KeyError):
            return {"state": "unverified", "reason": "connection_or_cluster"}

    def _presence_template_anchor(self):
        # A known configured VM must still be readable AND allocated. This rejects
        # an empty/stale VMID index during startup or a malformed API response.
        template = self.config.proxmox_template
        data = self._presence_read(self.node + f"/qemu/{template}/config")
        if (
            not isinstance(data, dict)
            or data.get("template") != 1
            or not data.get(self.config.disk_device)
        ):
            raise ProxmoxError("Template anchor cannot be verified")
        try:
            self._presence_read("cluster/nextid", vmid=template)
        except ProxmoxHTTPError as exc:
            if exc.status_code != 400:
                raise
        else:
            raise ProxmoxError("Cluster VMID index is inconsistent with template")

    def _confirm_unused_vmid(self, vmid):
        value = self._presence_read("cluster/nextid", vmid=vmid)
        if type(value) is not int or value != vmid:
            raise ProxmoxError("VMID absence cannot be verified")

    def _healthy_cluster(self):
        result = self._presence_read("cluster/status")
        if not isinstance(result, list) or any(not isinstance(r, dict) for r in result):
            raise ProxmoxError("Cluster status unavailable")
        nodes = [r for r in result if r.get("type") == "node"]
        clusters = [r for r in result if r.get("type") == "cluster"]
        names = [r.get("name") for r in nodes]
        if (
            not nodes
            or any(not isinstance(n, str) or not n for n in names)
            or len(set(names)) != len(names)
            or self.config.proxmox_node not in names
            or any(r.get("online") != 1 for r in nodes)
        ):
            raise ProxmoxError("Cluster nodes are not all online")
        if clusters:
            if (
                len(clusters) != 1
                or clusters[0].get("quorate") != 1
                or clusters[0].get("nodes") != len(nodes)
            ):
                raise ProxmoxError("Cluster quorum cannot be verified")
        elif len(nodes) != 1 or nodes[0].get("local") != 1:
            raise ProxmoxError("Standalone node identity cannot be verified")
        return (
            tuple(sorted(names)),
            tuple((r.get("name"), r.get("version")) for r in clusters),
        )

    def presence_task_status(self, upid):
        return self._presence_read(
            self.node + "/tasks/" + quote(upid, safe="") + "/status"
        )

    def _presence_read(self, path, **params):
        try:
            remaining = (
                getattr(self, "_presence_deadline", time.monotonic() + 15)
                - time.monotonic()
            )
            if remaining <= 0:
                raise ProxmoxError("Presence check deadline exceeded")
            response = self.client.get(path, params=params, timeout=min(5, remaining))
            if response.is_error:
                raise ProxmoxHTTPError(response.status_code, "GET", path)
            return response.json()["data"]
        except (httpx.TransportError, ValueError, TypeError, KeyError):
            raise ProxmoxError("Presence read unavailable") from None

    def node_health(self):
        from app.services.monitoring import number

        status = self.call("GET", self.node + "/status")
        memory = status.get("memory") or {}
        root = status.get("rootfs") or {}
        swap = status.get("swap") or {}
        storage_name = self.config.proxmox_storage
        storage_error = None
        try:
            storage = self.call(
                "GET",
                self.node + "/storage/" + quote(storage_name, safe="") + "/status",
            )
            if not storage.get("active") or not storage.get("enabled"):
                storage_error = "Storage สำหรับ VM ยังไม่เปิดใช้งานหรือไม่พร้อมใช้งาน"
        except ProxmoxError:
            storage = {}
            storage_error = (
                "อ่านพื้นที่ VM ไม่สำเร็จ กรุณาตรวจการเชื่อมต่อและสิทธิ์ Datastore.Audit บน /storage/"
                + storage_name
            )
        return {
            "cpu_percent": round(min(1, number(status.get("cpu"))) * 100, 1),
            "cpu_count": int(number((status.get("cpuinfo") or {}).get("cpus"))),
            "memory_used": int(number(memory.get("used"))),
            "memory_total": int(number(memory.get("total"))),
            "swap_used": int(number(swap.get("used"))),
            "swap_total": int(number(swap.get("total"))),
            "storage_name": storage_name,
            "storage_total": int(number(storage.get("total")))
            if not storage_error
            else None,
            "storage_used": int(number(storage.get("used")))
            if not storage_error
            else None,
            "storage_available": int(number(storage.get("avail")))
            if not storage_error
            else None,
            "storage_error": storage_error,
            "root_used": int(number(root.get("used"))),
            "root_total": int(number(root.get("total"))),
            "uptime_seconds": int(number(status.get("uptime"))),
        }

    def runtime(self, vmid):
        status = self.call("GET", self.node + f"/qemu/{vmid}/status/current")
        from app.services.monitoring import vm_metrics

        result = {
            "power": status.get("status", "unknown"),
            "ips": [],
            "ip_error": None,
            **vm_metrics(status),
        }
        if result["power"] != "running":
            return result
        try:
            interfaces = self.call(
                "GET", self.node + f"/qemu/{vmid}/agent/network-get-interfaces"
            )
            for nic in interfaces.get("result", []):
                for item in nic.get("ip-addresses", []):
                    try:
                        ip = ipaddress.ip_address(item["ip-address"])
                    except (ValueError, KeyError):
                        continue
                    if not (
                        ip.is_loopback
                        or ip.is_link_local
                        or ip.is_unspecified
                        or ip.is_multicast
                    ):
                        result["ips"].append(str(ip))
            result["ips"] = sorted(set(result["ips"]))
        except ProxmoxError as exc:
            result["ip_error"] = (
                "ต้องมี VM.GuestAgent.Audit ที่ /vms/" + str(vmid)
                if "HTTP 403" in str(exc)
                else "ตรวจ QEMU Guest Agent: ต้องเปิดใน Proxmox และติดตั้ง/รันใน VM"
            )
        return result

    def validate_password_reset(self, vmid):
        scope = f"/vms/{vmid}"
        response = self.client.get("access/permissions", params={"path": scope})
        if response.is_error or "VM.GuestAgent.Unrestricted" not in response.json().get(
            "data", {}
        ).get(scope, {}):
            raise ProxmoxError(
                f"Password reset requires VM.GuestAgent.Unrestricted at {scope}; administrator must review this broad guest permission"
            )
        state = self.call("GET", self.node + f"/qemu/{vmid}/status/current")
        if state.get("status") != "running":
            raise ProxmoxError("VM must be running for Guest Agent password reset")
        try:
            info = self.call("GET", self.node + f"/qemu/{vmid}/agent/info")
        except ProxmoxError:
            raise ProxmoxError(
                "Guest Agent is unavailable; check agent=1, running service and VM.GuestAgent.Audit"
            ) from None
        supported = info.get("result", {}).get("supported_commands", [])
        if not any(
            c.get("name") == "guest-set-user-password" and c.get("enabled")
            for c in supported
        ):
            raise ProxmoxError("Guest Agent does not enable guest-set-user-password")

    def reset_password(self, vmid, username, encrypted):
        # The service supplies the recorded, validated non-root guest username.
        from pydantic import TypeAdapter

        from app.api.schemas import RESERVED_GUEST_USERS, GuestUsername

        username = TypeAdapter(GuestUsername).validate_python(username)
        if username in RESERVED_GUEST_USERS:
            raise ProxmoxError("System guest account password reset is forbidden")
        try:
            password = (
                Fernet(self.config.encryption_key.get_secret_value().encode())
                .decrypt(encrypted.encode())
                .decode()
            )
        except (InvalidToken, ValueError, AttributeError):
            raise ProxmoxError("Cannot decrypt VM reset credential") from None
        return self.call(
            "POST",
            self.node + f"/qemu/{vmid}/agent/set-user-password",
            username=username,
            password=password,
            crypted=0,
        )

    def clear_cloudinit_password(self, vmid):
        # A later Cloud-Init regenerate must not restore the pre-reset password.
        cfg = self.call("GET", self.node + f"/qemu/{vmid}/config")
        if "cipassword" not in cfg:
            return False
        self.call("PUT", self.node + f"/qemu/{vmid}/config", delete="cipassword")
        return True

    def ensure_stopped(self, vmid):
        state = self.call("GET", self.node + f"/qemu/{vmid}/status/current")
        if state.get("status") != "stopped":
            raise ProxmoxError(
                "VM must be stopped before approved deletion; no force stop performed"
            )

    def delete(self, vmid, hostname):
        self.identity(vmid, hostname)
        self.ensure_stopped(vmid)
        return self.call("DELETE", self.node + f"/qemu/{vmid}")


class MockProxmox:
    def __init__(self):
        self.calls = []
        self.used = set()
        self.disks = {}

    def close(self):
        pass

    def check(self):
        return {"mode": "mock", "tls_verified": False}

    def validate_template(self, request):
        pass

    def validate_existing_clone(self, vmid, request):
        pass

    def available(self, vmid):
        return vmid not in self.used

    def clone(self, vmid, name):
        self.calls.append(("clone", vmid, name, "Portal-Service"))
        if vmid in self.used:
            raise ProxmoxError("Collision")
        self.used.add(vmid)
        return "UPID:mock:clone"

    def task_status(self, upid):
        return {"status": "stopped", "exitstatus": "OK", "type": "qmclone"}

    def wait(self, upid):
        self.calls.append(("wait", upid))

    def configure(self, vmid, request):
        self.calls.append(
            ("configure", vmid, request.cpu, request.ram, request.ssh_key)
        )

    def verify_ssh_password_policy(self, vmid, guest_username):
        self.calls.append(("verify_ssh_password_policy", vmid, guest_username))

    def regenerate_cloudinit(self, vmid):
        self.calls.append(("cloudinit_regenerate", vmid))

    def resize(self, vmid, disk):
        self.calls.append(("resize", vmid, disk))
        self.disks[vmid] = disk * SIZE_UNITS["G"]

    def disk_bytes(self, vmid):
        return self.disks.get(vmid, 3584 * SIZE_UNITS["M"])

    def power(self, vmid, operation):
        self.calls.append((operation, vmid))
        return "UPID:mock:" + operation

    def identity(self, vmid, hostname):
        pass

    def runtime(self, vmid):
        return {
            "power": "running",
            "ips": ["192.0.2.10"],
            "ip_error": None,
            "cpu_percent": 12.5,
            "cpu_count": 2,
            "memory_used": 1073741824,
            "memory_total": 2147483648,
            "uptime_seconds": 3600,
            "net_in": 4096,
            "net_out": 8192,
        }

    def node_health(self):
        return {
            "cpu_percent": 25.0,
            "cpu_count": 16,
            "memory_used": 17179869184,
            "memory_total": 68719476736,
            "swap_used": 0,
            "swap_total": 8589934592,
            "storage_name": "local-lvm",
            "storage_total": 6000000000000,
            "storage_used": 200000000000,
            "storage_available": 5800000000000,
            "storage_error": None,
            "root_used": 21474836480,
            "root_total": 107374182400,
            "uptime_seconds": 86400,
        }

    def validate_password_reset(self, vmid):
        pass

    def reset_password(self, vmid, username, encrypted):
        self.calls.append(("reset_password", vmid, username))
        return None

    def clear_cloudinit_password(self, vmid):
        self.calls.append(("clear_cloudinit_password", vmid))
        return True

    def ensure_stopped(self, vmid):
        pass

    def delete(self, vmid, hostname):
        self.calls.append(("delete", vmid))
        return "UPID:mock:delete"


def make_adapter(config):
    return MockProxmox() if config.proxmox_mode == "mock" else RestProxmox(config)
