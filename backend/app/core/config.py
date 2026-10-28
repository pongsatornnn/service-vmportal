from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    portal_static_dir: str = ""
    # URL path the portal is served under, e.g. "/vmportal"; empty means the site root.
    portal_base_path: str = ""
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: SecretStr
    token_minutes: int = Field(default=30, ge=5, le=1440)
    require_setup: bool = True
    encryption_key: SecretStr = SecretStr("")
    bootstrap_token: SecretStr = SecretStr("")
    proxmox_ca_pem: str = ""
    proxmox_mode: str = "mock"
    proxmox_url: str = "https://10.80.48.6:8006"
    proxmox_token_id: str = ""
    proxmox_token_secret: SecretStr = SecretStr("")
    proxmox_ca: str = "/etc/vmportal/certs/proxmox-ca.pem"
    proxmox_node: str = "Node3"
    proxmox_pool: str = "Portal-Service"
    proxmox_template: int = 9000
    proxmox_storage: str = "local-lvm"
    proxmox_bridge: str = "VLAN48"
    proxmox_secondary_bridge: str = ""
    proxmox_network_bridges: list[str] = Field(default_factory=list, max_length=32)
    bridge_allowlist: str = "VLAN48"
    template_disk_gb: int = 20
    disk_device: str = "scsi0"
    ssh_password_snippet: str = ""
    vmid_start: int = 10000
    provisioning_enabled: bool = False

    @model_validator(mode="after")
    def validate_security(self):
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET requires at least 32 characters")
        if self.proxmox_mode not in {"mock", "real"}:
            raise ValueError("PROXMOX_MODE must be mock or real")
        if self.proxmox_bridge not in self.bridge_allowlist.split(","):
            raise ValueError("Bridge not allowed")
        if (
            self.proxmox_secondary_bridge
            and self.proxmox_secondary_bridge not in self.bridge_allowlist.split(",")
        ):
            raise ValueError("Secondary bridge not allowed")
        if any(
            bridge not in self.bridge_allowlist.split(",")
            for bridge in self.proxmox_network_bridges
        ):
            raise ValueError("Bridge not allowed")
        if not self.proxmox_url.startswith("https://"):
            raise ValueError("Proxmox requires HTTPS")
        return self


@lru_cache
def settings():
    return Settings()
