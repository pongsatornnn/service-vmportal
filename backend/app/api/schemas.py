import string
import unicodedata
from datetime import datetime
from typing import Annotated, Literal

from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_username(value):
    return value.strip().lower() if isinstance(value, str) else value


Username = Annotated[
    str,
    BeforeValidator(normalize_username),
    Field(min_length=3, max_length=32, pattern=r"^[a-z0-9][a-z0-9_.-]*$"),
]


def validate_password(value, min_length=12):
    if (
        not min_length <= len(value) <= 128
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or not any("A" <= c <= "Z" for c in value)
        or not any("a" <= c <= "z" for c in value)
        or not any("0" <= c <= "9" for c in value)
        or not any(c in string.punctuation for c in value)
    ):
        raise ValueError(
            f"รหัสผ่านต้องยาว {min_length}–128 ตัว มี A–Z, a–z, ตัวเลข และอักขระพิเศษ"
        )
    return value


class Register(StrictModel):
    username: Username
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("password", "confirm_password")
    @classmethod
    def valid_password(cls, value):
        return validate_password(value, min_length=8)

    @field_validator("first_name", "last_name")
    @classmethod
    def valid_name(cls, value):
        value = unicodedata.normalize("NFC", value.strip())
        if not value or not any(unicodedata.category(c).startswith("L") for c in value):
            raise ValueError("Invalid personal name")
        if any(not (unicodedata.category(c)[0] in "LM" or c in " '-’.") for c in value):
            raise ValueError("Invalid personal name")
        return value

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Password confirmation does not match")
        return self


class DeleteUser(StrictModel):
    confirm_vm_ids: list[Annotated[int, Field(ge=1, le=2147483647, strict=True)]] = (
        Field(max_length=1000)
    )
    admin_password: SecretStr = Field(min_length=1, max_length=128)
    confirm_username: str = Field(min_length=3, max_length=32)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if not value.strip():
            raise ValueError("Reason is required")
        return value.strip()


class Login(StrictModel):
    username: Username
    password: str = Field(min_length=1, max_length=128)


RESERVED_GUEST_USERS = {
    "root",
    "daemon",
    "bin",
    "sys",
    "sync",
    "games",
    "man",
    "lp",
    "mail",
    "news",
    "uucp",
    "proxy",
    "www-data",
    "backup",
    "list",
    "irc",
    "gnats",
    "nobody",
    "_apt",
    "sshd",
    "messagebus",
    "systemd-network",
    "systemd-resolve",
    "systemd-timesync",
    "polkitd",
}

GuestUsername = Annotated[
    str,
    BeforeValidator(normalize_username),
    Field(min_length=3, max_length=32, pattern=r"^[a-z][a-z0-9_-]*$"),
]


class RequestVM(StrictModel):
    request_reason: str = Field(min_length=3, max_length=1000)

    @field_validator("request_reason", mode="before")
    @classmethod
    def trim_request_reason(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("request_reason")
    @classmethod
    def valid_request_reason(cls, value):
        if not any(c.isalnum() for c in value) or any(
            unicodedata.category(c) in {"Cc", "Cs"} and c not in "\n\t" for c in value
        ):
            raise ValueError("A meaningful VM request reason is required")
        return value

    hostname: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    cpu: int = Field(ge=1, le=32, strict=True)
    ram: int = Field(ge=512, le=131072, strict=True)
    disk: int = Field(ge=1, le=2048, strict=True)
    auth_method: Literal["ssh_key", "password"] = "ssh_key"
    ssh_key: str = Field(default="", max_length=8192)
    vm_password: SecretStr | None = None
    guest_username: GuestUsername = "ubuntu"
    ssh_password_login: bool = Field(default=False, strict=True)
    # Optional only while exactly one template is offered.
    template_id: int | None = Field(default=None, ge=1, le=2147483647, strict=True)

    @field_validator("ssh_key")
    @classmethod
    def valid_key(cls, value):
        if not value:
            return value
        if "\n" in value or not value.startswith(
            ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-nistp256 ")
        ):
            raise ValueError("Unsupported SSH public key")
        try:
            key = load_ssh_public_key(value.encode())
            if hasattr(key, "key_size") and key.key_size < 256:
                raise ValueError()
            if value.startswith("ssh-rsa ") and key.key_size < 2048:
                raise ValueError()
        except Exception as exc:
            raise ValueError("Invalid SSH public key") from exc
        return value

    @model_validator(mode="after")
    def valid_authentication(self):
        if self.guest_username in RESERVED_GUEST_USERS:
            raise ValueError("System and root guest usernames are not allowed")
        if self.ssh_password_login and self.auth_method != "password":
            raise ValueError("SSH password login requires password authentication")
        if self.auth_method == "ssh_key":
            if not self.ssh_key or self.vm_password is not None:
                raise ValueError(
                    "SSH key mode requires a public key and no VM password"
                )
        else:
            value = self.vm_password.get_secret_value() if self.vm_password else ""
            if self.ssh_key:
                raise ValueError("Password mode does not accept an SSH key")
            validate_password(value)
        return self


class VMRequestOut(BaseModel):
    request_reason: str | None

    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    hostname: str
    cpu: int
    ram: int
    disk: int
    auth_method: str
    # Only the owner sees the account inside their VM; approval does not need it.
    guest_username: str | None
    ssh_password_login: bool
    ssh_key: str
    status: str
    decided_by: int | None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    template_id: int | None = None
    template_name: str | None = None
    reason: str | None
    created_at: datetime


class Decision(StrictModel):
    approve: bool = Field(strict=True)
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def rejection_reason(self):
        self.reason = self.reason.strip()
        if not self.approve and not self.reason:
            raise ValueError("กรุณาระบุเหตุผลที่ปฏิเสธคำขอ")
        return self


class Action(StrictModel):
    action: Literal["start", "stop", "shutdown", "reboot"]


class Quota(StrictModel):
    quota_vms: int = Field(ge=0, le=1000, strict=True)
    quota_cpu: int = Field(ge=0, le=10000, strict=True)
    quota_ram: int = Field(ge=0, le=100000000, strict=True)
    quota_disk: int = Field(ge=0, le=10000000, strict=True)


class BulkQuota(Quota):
    user_ids: list[Annotated[int, Field(gt=0, strict=True)]] = Field(
        min_length=1, max_length=500
    )


class QuotaDefaultsUpdate(Quota):
    apply_to_existing: bool = Field(default=False, strict=True)
    role: Literal["user", "admin"] = "user"


class Bootstrap(StrictModel):
    username: Username
    password: str = Field(min_length=12, max_length=128)
    setup_token: str = Field(max_length=256)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value):
        return validate_password(value)


class ConnectionSettings(StrictModel):
    mode: Literal["mock", "real"] = "real"
    url: str = Field(max_length=512)
    token_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+$")
    # SecretStr has no validation that could echo its value in error output.
    token_secret: SecretStr | None = None
    ca_pem: str = Field(default="", max_length=65536)
    node: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,63}$")
    pool: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,63}$")
    # Templates now live in their own list; these remain for older saved setups.
    template: int | None = Field(default=None, ge=100, le=999999999, strict=True)
    storage: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,63}$")
    bridge: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,63}$")
    secondary_bridge: str = Field(default="", pattern=r"^(?:[A-Za-z0-9_.-]{1,63})?$")
    network_bridges: (
        list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,63}$")]] | None
    ) = Field(default=None, min_length=1, max_length=32)
    bridge_allowlist: list[str] = Field(min_length=1, max_length=32)
    template_disk_gb: int | None = Field(default=None, ge=1, le=2048, strict=True)
    disk_device: str | None = Field(
        default=None, pattern=r"^(scsi|sata|virtio)[0-9]{1,2}$"
    )
    ssh_password_snippet: str = Field(
        default="",
        max_length=200,
        pattern=r"^(?:[A-Za-z0-9_.-]+:snippets/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.ya?ml)?$",
    )


class TemplateIn(StrictModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    vmid: int = Field(ge=100, le=999999999, strict=True)
    disk_device: str = Field(pattern=r"^(scsi|sata|virtio)[0-9]{1,2}$")
    min_disk_gb: int = Field(ge=1, le=2048, strict=True)

    @field_validator("name", "description")
    @classmethod
    def tidy(cls, value):
        value = " ".join(value.split())
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("Control characters are not allowed")
        return value

    @field_validator("name")
    @classmethod
    def named(cls, value):
        if not value:
            raise ValueError("Template name required")
        return value


class TemplateToggle(StrictModel):
    enabled: bool = Field(strict=True)


class ResourceDiscovery(StrictModel):
    url: str = Field(max_length=512)
    token_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+![A-Za-z0-9_.-]+$")
    token_secret: SecretStr | None = None
    ca_pem: str = Field(max_length=65536)
    node: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,63}$")
    template: int | None = Field(default=None, ge=100, le=999999999, strict=True)


class Activation(StrictModel):
    enabled: bool = Field(strict=True)
    confirm_real_execution: bool = Field(default=False, strict=True)


class DeleteVM(StrictModel):
    reason: str = Field(min_length=3, max_length=1000)


class RetryDelete(StrictModel):
    confirm_hostname: str = Field(min_length=1, max_length=63)


class CloseJob(RetryDelete):
    message: str = Field(min_length=3, max_length=1000)


class NewPassword(StrictModel):
    new_password: SecretStr

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value):
        validate_password(value.get_secret_value())
        return value


class ChangePassword(NewPassword):
    current_password: SecretStr = Field(max_length=128)


class RedeemRecovery(NewPassword):
    code: SecretStr = Field(min_length=32, max_length=128)


class IssueRecovery(StrictModel):
    admin_password: SecretStr = Field(min_length=1, max_length=128)


class RequestSeen(StrictModel):
    entries: dict[
        Annotated[str, Field(pattern=r"^(create|delete|reset|job)-[0-9]{1,10}$")],
        Annotated[str, Field(max_length=64)],
    ] = Field(max_length=1000)


class ChangeRole(IssueRecovery):
    role: Literal["admin", "user"]
    confirm_username: str = Field(min_length=3, max_length=32)


class ChangePrimary(IssueRecovery):
    primary_admin: bool = Field(strict=True)
    confirm_username: str = Field(min_length=3, max_length=32)


class ResetVMPassword(NewPassword):
    reason: str = Field(min_length=3, max_length=1000)


class VMPasswordResetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vm_id: int
    owner_id: int
    job_id: int | None
    status: str
    reason: str
    decision_reason: str | None
    decided_by: int | None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    created_at: datetime


class DeleteDecision(Decision):
    confirm_hostname: str | None = Field(default=None, max_length=63)


class SessionPolicyUpdate(StrictModel):
    token_minutes: int = Field(ge=5, le=1440, strict=True)
