"""Interactive system-service installer, invoked by ../setup-server.sh.

Only main() changes the host. Rendering, validation and credential helpers are
separate so tests can exercise them without installing or restarting services.
"""

import argparse
import base64
import fcntl
import grp
import ipaddress
import json
import os
import pwd
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.request
import warnings
from datetime import UTC, datetime
from getpass import GetPassWarning, getpass
from pathlib import Path

import psycopg
from cryptography.fernet import Fernet, InvalidToken
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import URL, make_url

SOURCE = Path(__file__).resolve().parents[1]
CONFIG = Path("/etc/vmportal")
STATE = Path("/var/lib/vmportal")
UNITS = Path("/etc/systemd/system")
BACKUPS = Path("/var/backups/vmportal")
PARTS = [f"vmportal-{name}.service" for name in ("redis", "api", "worker", "beat")]
# One name to start, stop, restart or check the whole portal; each part stays its own unit.
GROUP = "vmportal.service"
SERVICES = PARTS + [GROUP]
# Older installs put Nginx in front of the API; re-running removes it.
LEGACY_SERVICES = ["vmportal-web.service"]


class SetupError(Exception):
    pass


class DatabaseUnavailable(SetupError):
    pass


def run(args, *, private=False, **kwargs):
    try:
        return subprocess.run(
            [str(arg) for arg in args], check=True, capture_output=private, **kwargs
        )
    except subprocess.CalledProcessError:
        raise SetupError(
            f"Command {Path(str(args[0])).name} failed. Check the service or connection and run the installer again."
        ) from None


def ask(label, default=None):
    value = input(
        f"{label}" + (f" [{default}]" if default is not None else "") + ": "
    ).strip()
    return value or default or ""


def yes(label, default=False):
    while True:
        answer = ask(label + (" [Y/n]" if default else " [y/N]")).lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def choose(label, choices, default):
    for key, text in choices.items():
        print(f"  {key}) {text}")
    while True:
        answer = ask(label, default)
        if answer in choices:
            return answer
        print("Please choose one of the numbers shown.")


def valid_port(value):
    if not str(value).isdigit() or not 1 <= int(value) <= 65535:
        raise SetupError("Port must be a number from 1 to 65535.")
    return int(value)


def valid_host(value):
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if not re.fullmatch(
            r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", value
        ):
            raise SetupError(
                "Enter a hostname or IP address without https://, a path or a port."
            ) from None
        if any(
            not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
            for label in value.split(".")
        ):
            raise SetupError("Invalid hostname.") from None
        return value.lower()


def valid_location(path=None):
    """The cloned project is the installation; check it is a sensible place."""
    path = Path(path or SOURCE).resolve()
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)):
        raise SetupError(
            f"The project folder {path} must use only letters, digits, /, _, - or dots, with no spaces. Clone it somewhere like ~/service-vmportal."
        )
    if any(
        path.is_relative_to(Path(base))
        for base in ("/tmp", "/var/tmp", "/run", "/dev", "/proc", "/sys")
    ):
        raise SetupError(
            f"{path} is temporary. Clone the project to a permanent place such as ~/service-vmportal."
        )
    if path in {
        Path(p) for p in ("/", "/opt", "/srv", "/var", "/usr", "/etc", "/home", "/root")
    }:
        raise SetupError(
            "Clone the project into its own folder, such as ~/service-vmportal."
        )
    return str(path)


def service_account(path=None):
    """The account the portal runs as: whoever started the installer with sudo.

    It owns the clone, builds there and runs the services; nothing runs as root.
    """
    name = os.environ.get("SUDO_USER") or ""
    if not name or name == "root":
        name = pwd.getpwuid(Path(path or SOURCE).stat().st_uid).pw_name
    try:
        user = pwd.getpwnam(name)
    except KeyError:
        raise SetupError(f"The account {name} does not exist.") from None
    if user.pw_uid == 0:
        raise SetupError(
            "The portal must not run as root. Run the installer with sudo from the account that should run it, for example: sudo bash setup-server.sh"
        )
    return user.pw_name, grp.getgrgid(user.pw_gid).gr_name


def database_url(host, port, name, user, password):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", name) or not re.fullmatch(
        r"[A-Za-z0-9_.-]{1,63}", user
    ):
        raise SetupError(
            "Database and user names may use letters, digits, _, - or dots, up to 63 characters."
        )
    if not password or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise SetupError(
            "The database password must not be empty or contain control characters."
        )
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=valid_host(host),
        port=valid_port(port),
        database=name,
        query={
            "sslmode": "prefer"
            if host in {"localhost", "127.0.0.1", "::1"}
            else "require"
        },
    ).render_as_string(hide_password=False)


def connection_args(value):
    url = make_url(value)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise SetupError("Only PostgreSQL databases are supported.")
    return {
        "host": url.host,
        "port": url.port or 5432,
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
        "connect_timeout": 5,
    } | dict(url.query)


def connect(value):
    try:
        return psycopg.connect(**connection_args(value))
    except psycopg.Error:
        raise DatabaseUnavailable(
            "Cannot connect to PostgreSQL. Check the host, port, database, user, password and permissions."
        ) from None


def previous_settings():
    old = (
        json.loads((CONFIG / "install.json").read_text())
        if (CONFIG / "install.json").is_file()
        else {}
    )
    env = (
        dict(dotenv_values(CONFIG / "portal.env", interpolate=False))
        if (CONFIG / "portal.env").is_file()
        else {}
    )
    if env and not old:
        raise SetupError(
            "Found portal.env without install.json. Back up and move the old installation before using this installer."
        )
    if old and not all(
        env.get(key) for key in ("DATABASE_URL", "JWT_SECRET", "ENCRYPTION_KEY")
    ):
        raise SetupError(
            "The existing environment file is incomplete. Restore it from a backup before running the installer again."
        )
    return old, env


def runtime_env(old, db_url):
    values = {key: value for key, value in old.items() if value is not None}
    values.update(DATABASE_URL=db_url)
    if old.get("DATABASE_URL") and old["DATABASE_URL"] != db_url:
        values["JWT_SECRET"] = secrets.token_hex(48)
    for key, factory in {
        "JWT_SECRET": lambda: secrets.token_hex(48),
        "ENCRYPTION_KEY": lambda: base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "BOOTSTRAP_TOKEN": lambda: secrets.token_urlsafe(32),
    }.items():
        if not values.get(key):
            values[key] = factory()
    for key, value in {
        "REQUIRE_SETUP": "true",
        "PROXMOX_MODE": "real",
        "PROVISIONING_ENABLED": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }.items():
        values.setdefault(key, value)
    return values


def database_choice(old, old_env):
    if old_env.get("DATABASE_URL") and not yes(
        "Change the database connection?", False
    ):
        return old_env["DATABASE_URL"], old.get("database_mode", "existing"), False
    mode = choose(
        "Database",
        {
            "1": "Use an existing database and user that are already prepared",
            "2": "Create a new database and user in PostgreSQL on this server",
        },
        "2",
    )
    host = valid_host(ask("DB host", "127.0.0.1")) if mode == "1" else "127.0.0.1"
    port = valid_port(ask("DB port", "5432"))
    name, user = ask("Database name", "vmportal"), ask("Database user", "vmportal")
    password = getpass(
        "Database password" + (" (Enter = generate one)" if mode == "2" else "") + ": "
    )
    if mode == "2":
        if not password:
            password = secrets.token_urlsafe(32)
        else:
            if len(password) < 12 or password != getpass("Confirm database password: "):
                raise SetupError(
                    "A new database password needs at least 12 characters and the confirmation must match."
                )
    return (
        database_url(host, port, name, user, password),
        "managed" if mode == "2" else "existing",
        mode == "2",
    )


def ipv6_enabled():
    try:
        with socket.socket(socket.AF_INET6) as listener:
            listener.bind(("::", 0))
            return True
    except OSError:
        return False


def port_available(port):
    try:
        with socket.socket() as listener:
            listener.bind(("0.0.0.0", port))
            if ipv6_enabled():
                with socket.socket(socket.AF_INET6) as listener6:
                    listener6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    listener6.bind(("::", port))
        return True
    except OSError:
        return False


def ufw_rules():
    """UFW's rule listing when the firewall is active, otherwise None."""
    if not shutil.which("ufw"):
        return None
    result = subprocess.run(["ufw", "status"], capture_output=True, text=True)
    if result.returncode or not result.stdout.startswith("Status: active"):
        return None
    return result.stdout


def ufw_allows(rules, port):
    return bool(re.search(rf"^{port}(/tcp)?\s+ALLOW", rules, re.MULTILINE))


def firewall_choice(old, port):
    """Offer to open the HTTPS port when UFW would block it; returns the port to open."""
    rules = ufw_rules()
    if rules is None:
        return old.get("ufw_port") if old.get("ufw_port") == port else None
    if ufw_allows(rules, port):
        # Keep tracking a rule this installer added earlier.
        return port if old.get("ufw_port") == port else None
    if yes(f"UFW is active and blocks port {port}. Allow it so other machines can open the portal?", True):
        return port
    print(
        f"WARNING: other machines cannot reach the portal until port {port}/tcp is allowed in the firewall."
    )
    return None


def active(service):
    return (
        subprocess.run(
            ["systemctl", "is-active", "--quiet", service], capture_output=True
        ).returncode
        == 0
    )


def internal_port(old, key, default, service):
    if old.get(key) and (
        port_available(old[key])
        or (
            active(service)
            and not (
                service == "vmportal-api.service" and old.get("web_mode") == "direct"
            )
        )
    ):
        return old[key]
    for port in range(default, default + 100):
        if port_available(port):
            return port
    raise SetupError("No free internal port was found.")


BASE_PATH = re.compile(r"(?:/[a-z0-9][a-z0-9-]{0,62})*")


def valid_base_path(value):
    """URL path users open, e.g. /vmportal; "/" or empty means the site root."""
    value = value.strip() or "/"
    if not value.startswith("/"):
        value = "/" + value
    value = value.rstrip("/")
    if not BASE_PATH.fullmatch(value):
        raise SetupError(
            "The URL path must look like /vmportal: lowercase letters, digits and hyphens, separated by /."
        )
    return value


def portal_url(host, port, base=""):
    return f"https://{host}:{port}{base}/"


def web_root(path=None):
    """Published website files, kept apart from the clone so updates swap in cleanly."""
    return STATE / "www"


def collect(old, old_env, action="install"):
    # The portal runs from the folder the project was cloned into.
    path = valid_location()
    user, group = service_account(path)
    print(f"The portal will run as {user} from {path}.")
    if action == "settings" and old.get("path") and path != old["path"]:
        print(f"The portal will now run from {path}, so it is built there too.")
        action = "update"
    base = valid_base_path(
        ask(
            "URL path users open (for example /vmportal, or / for the site root)",
            old.get("base_path") or "/",
        )
    )
    if action == "settings" and base != old.get("base_path", ""):
        print(
            "The web pages must be rebuilt for a new URL path, so the application will be updated too."
        )
        action = "update"
    port = valid_port(ask("HTTPS port", str(old.get("port", 443))))
    # The portal may already hold this port: directly, or through an older Nginx front end.
    own_port = old.get("port") == port and (
        active("vmportal-api.service") or active("vmportal-web.service")
    )
    if not port_available(port) and not own_port:
        raise SetupError(
            "That HTTPS port is used by another service. Choose a different port."
        )
    host = valid_host(
        ask("Hostname or IP users will open", old.get("host", socket.gethostname()))
    )
    if ":" in host:
        raise SetupError("Use an IPv4 address or a hostname that resolves to IPv4.")
    ufw_port = firewall_choice(old, port)
    tls_mode = choose(
        "HTTPS certificate",
        (
            {
                "1": "Keep the current certificate",
                "2": "Use a certificate and private key I provide",
                "3": "Generate a self-signed certificate",
            }
            if old
            else {
                "2": "Use a certificate and private key I provide",
                "3": "Generate a self-signed certificate",
            }
        ),
        "1" if old and (CONFIG / "tls/portal.crt").is_file() else "3",
    )
    cert = str(CONFIG / "tls/portal.crt") if tls_mode == "1" else ""
    key = str(CONFIG / "tls/portal.key") if tls_mode == "1" else ""
    if tls_mode == "2":
        cert, key = ask("Certificate path (.crt/.pem)"), ask("Private key path (.key)")
    url, mode, create = database_choice(old, old_env)
    redis_port = internal_port(
        old, "redis_port", 56380 if port == 56379 else 56379, "vmportal-redis.service"
    )
    if port == redis_port:
        raise SetupError(
            "The HTTPS port clashes with the internal Redis port. Choose another port."
        )
    env = runtime_env(old_env, url)
    if not env.get("REDIS_URL"):
        env["REDIS_URL"] = f"redis://:{secrets.token_hex(32)}@127.0.0.1:{redis_port}/0"
    # The dedicated Redis endpoint is stable across re-runs.
    if make_url(env["REDIS_URL"]).port != redis_port:
        redis_url = make_url(env["REDIS_URL"])
        env["REDIS_URL"] = redis_url.set(port=redis_port).render_as_string(
            hide_password=False
        )
    env["PORTAL_STATIC_DIR"] = str(web_root())
    env["PORTAL_BASE_PATH"] = base
    return dict(
        action=action,
        web_mode="direct",
        path=path,
        user=user,
        group=group,
        base_path=base,
        port=port,
        host=host,
        tls_mode=tls_mode,
        cert=cert,
        key=key,
        database_mode=mode,
        create_db=create,
        redis_port=redis_port,
        ufw_port=ufw_port,
        redis_namespace=(
            old.get("redis_namespace") if old_env.get("DATABASE_URL") == url else None
        )
        or secrets.token_hex(8),
        env=env,
    )


def database_label(value):
    url = make_url(value)
    return f"{url.host}:{url.port or 5432}/{url.database} (user {url.username})"


def describe_changes(old, old_env, plan):
    """Each changed setting with what it affects, for the operator to confirm."""
    if not old:
        return []
    changes = []

    if plan["action"] == "update":
        changes.append(
            (
                "Application",
                "a new version is built from this folder",
                "Database migrations run and all portal services restart (about a minute of downtime).",
            )
        )
    if old.get("path") and plan["path"] != old["path"]:
        changes.append(
            (
                "Location",
                f"{old['path']} -> {plan['path']}",
                f"Services will run from {plan['path']}. {old['path']} is left in place; delete it yourself once the portal works.",
            )
        )
    if old.get("user", "vmportal") != plan["user"]:
        changes.append(
            (
                "Service account",
                f"{old.get('user', 'vmportal')} -> {plan['user']}",
                f"The services, the build in {plan['path']} and the portal's data under {STATE} now belong to {plan['user']}.",
            )
        )
    before = portal_url(old.get("host"), old.get("port"), old.get("base_path", ""))
    after = portal_url(plan["host"], plan["port"], plan.get("base_path", ""))
    if before != after:
        warning = (
            "Users must open the new address; old bookmarks and links stop working."
        )
        if plan["port"] != old.get("port") and not plan.get("ufw_port"):
            warning += f" Allow TCP {plan['port']} in any firewall or security group."
        if plan["host"] != old.get("host") and plan["tls_mode"] == "1":
            warning += f" The current certificate must also cover {plan['host']}."
        if plan.get("base_path", "") != old.get("base_path", ""):
            warning += " The web pages are rebuilt for the new URL path; opening the site root redirects there."
        changes.append(("Address", f"{before} -> {after}", warning))
    if plan["tls_mode"] != "1":
        changes.append(
            (
                "Certificate",
                "replaced"
                + (
                    " with a new self-signed certificate"
                    if plan["tls_mode"] == "3"
                    else ""
                ),
                "Browsers see a different certificate"
                + (
                    "; users must accept the self-signed warning again."
                    if plan["tls_mode"] == "3"
                    else "."
                ),
            )
        )
    if old_env.get("DATABASE_URL") != plan["env"]["DATABASE_URL"]:
        changes.append(
            (
                "Database",
                f"{database_label(old_env['DATABASE_URL'])} -> {database_label(plan['env']['DATABASE_URL'])}",
                "The portal will show the data in the selected database; nothing is copied from the old one. Everyone is signed out.",
            )
        )
    if plan.get("ufw_port") and plan["ufw_port"] != old.get("ufw_port"):
        changes.append(
            (
                "Firewall",
                f"UFW allows TCP {plan['ufw_port']}",
                "Other machines on the network can reach the portal on this port.",
            )
        )
    if old.get("ufw_port") and old["ufw_port"] != plan.get("ufw_port"):
        changes.append(
            (
                "Firewall",
                f"the UFW rule for TCP {old['ufw_port']} added by this installer is removed",
                f"Port {old['ufw_port']} is closed again unless another rule allows it.",
            )
        )
    if old.get("web_mode", "nginx") != "direct":
        changes.append(
            (
                "Web server",
                "Nginx -> served directly by the portal",
                "vmportal-web (Nginx) is stopped and removed. The Nginx package itself stays installed for other sites.",
            )
        )
    return changes


def postgres_sql(statement, port):
    return run(
        [
            "runuser",
            "-u",
            "postgres",
            "--",
            "psql",
            "-X",
            "-qAt",
            "--no-password",
            "--host",
            "/var/run/postgresql",
            "--username",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-p",
            port,
            "-d",
            "postgres",
        ],
        input=statement.as_string(),
        text=True,
        private=True,
    ).stdout.strip()


def create_database(value):
    params = connection_args(value)
    run(
        ["apt-get", "-o", "DPkg::Lock::Timeout=600", "install", "-y", "postgresql"],
        env=os.environ | {"DEBIAN_FRONTEND": "noninteractive"},
    )
    run(["systemctl", "start", "postgresql"])
    for table, column, name in [
        ("pg_roles", "rolname", params["user"]),
        ("pg_database", "datname", params["dbname"]),
    ]:
        exists = postgres_sql(
            sql.SQL("SELECT 1 FROM {} WHERE {} = {}").format(
                sql.Identifier(table), sql.Identifier(column), sql.Literal(name)
            ),
            params["port"],
        )
        if exists:
            raise SetupError(
                "That database user or database already exists. Choose 'existing database' or enter new names; the existing user's password was not changed."
            )
    postgres_sql(
        sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}"
        ).format(sql.Identifier(params["user"]), sql.Literal(params["password"])),
        params["port"],
    )
    postgres_sql(
        sql.SQL(
            "CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0"
        ).format(sql.Identifier(params["dbname"]), sql.Identifier(params["user"])),
        params["port"],
    )


def verify_database(plan):
    value = plan["env"]["DATABASE_URL"]
    encrypted = []
    with connect(value) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
        }
        if tables and not {"users", "vms", "vm_requests", "alembic_version"}.issubset(
            tables
        ):
            raise SetupError(
                "The selected database must be empty or a VM Portal database."
            )
        # Own the public schema or have the permissions required by migrations.
        if not db.execute(
            "SELECT has_schema_privilege(current_user, 'public', 'USAGE') AND has_schema_privilege(current_user, 'public', 'CREATE')"
        ).fetchone()[0]:
            raise SetupError(
                "The database user needs USAGE and CREATE on schema public to run migrations."
            )
        for table, column in [
            ("portal_configuration", "token_encrypted"),
            ("vm_requests", "password_encrypted"),
            ("vm_password_resets", "password_encrypted"),
        ]:
            exists = db.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                (table, column),
            ).fetchone()
            if exists:
                record = db.execute(
                    sql.SQL(
                        "SELECT {} FROM {} WHERE {} IS NOT NULL AND {} <> '' LIMIT 1"
                    ).format(
                        sql.Identifier(column),
                        sql.Identifier(table),
                        sql.Identifier(column),
                        sql.Identifier(column),
                    )
                ).fetchone()
                if record:
                    encrypted.append(record[0])
    if encrypted:

        def matches(key):
            try:
                cipher = Fernet(key.encode())
                for item in encrypted:
                    cipher.decrypt(item.encode())
                return True
            except (ValueError, InvalidToken):
                return False

        if not matches(plan["env"]["ENCRYPTION_KEY"]):
            key = getpass(
                "This database already holds portal data. Enter its original ENCRYPTION_KEY: "
            )
            if not matches(key):
                raise SetupError(
                    "That ENCRYPTION_KEY does not match the data in the database."
                )
            plan["env"]["ENCRYPTION_KEY"] = key


def require_idle(value):
    if not value:
        return
    with connect(value) as db:
        if db.execute("SELECT to_regclass('public.jobs')").fetchone()[0]:
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]
            if count:
                raise SetupError(
                    f"{count} VM job(s) are queued or running. Wait for them to finish, then run the installer again."
                )


def check_previous_database(plan, old_env):
    old = old_env.get("DATABASE_URL")
    if not old:
        return
    try:
        require_idle(old)
    except DatabaseUnavailable:
        if old == plan["env"]["DATABASE_URL"]:
            raise
        if not yes(
            "The old database is unreachable, so its jobs cannot be checked or backed up. Stop the current services and use the new database anyway?",
            False,
        ):
            raise SetupError("Database change cancelled.") from None
        plan["skip_old_database"] = True


def private_write(path, content, mode=0o600, group=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        if group is not None:
            os.chown(temporary, 0, group)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def environment_text(values):
    for key, value in values.items():
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key) or any(
            c in str(value) for c in "\r\n\x00"
        ):
            raise SetupError("An environment value has an unsupported format.")
    return "".join(
        f"{key}={json.dumps(str(value), ensure_ascii=False)}\n"
        for key, value in values.items()
    )


def service_identity(plan):
    user = pwd.getpwnam(plan["user"])
    if user.pw_uid == 0:
        raise SetupError("The portal must not run as root.")
    STATE.mkdir(parents=True, exist_ok=True)
    STATE.chmod(0o755)
    os.chown(STATE, 0, 0)
    (STATE / "redis").mkdir(exist_ok=True)
    (STATE / "redis").chmod(0o755)
    os.chown(STATE / "redis", 0, 0)
    for directory in (STATE / "home", STATE / "beat"):
        directory.mkdir(exist_ok=True)
        directory.chmod(0o700)
        run(
            [
                "chown",
                "-R",
                "--no-dereference",
                f"{user.pw_uid}:{user.pw_gid}",
                directory,
            ]
        )
    CONFIG.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG, 0o750)
    os.chown(CONFIG, 0, user.pw_gid)
    return user.pw_uid, user.pw_gid


def build_in_place(plan):
    """Install dependencies and build the web pages inside the clone.

    Everything is built by the account that runs the portal, so the folder never
    collects root-owned files and git pull keeps working.
    """
    root = Path(plan["path"])
    user = pwd.getpwnam(plan["user"])
    owner = f"{user.pw_name}:{plan['group']}"
    if root.stat().st_uid != user.pw_uid:
        # For example a clone made with sudo git clone.
        print(f"Giving {user.pw_name} ownership of {root}...")
        run(["chown", "-R", "--no-dereference", owner, root])
    else:
        # Files a sudo git pull may have left behind.
        run(["chown", "-R", "--no-dereference", "--from=root", owner, root])
    if subprocess.run(
        ["runuser", "-u", user.pw_name, "--", "test", "-w", root],
        capture_output=True,
    ).returncode:
        raise SetupError(
            f"{user.pw_name} cannot write to {root}; check the permissions of the folders above it."
        )
    as_owner = [
        "runuser",
        "-u",
        user.pw_name,
        "--",
        "/usr/bin/env",
        f"HOME={user.pw_dir}",
        "PYTHONDONTWRITEBYTECODE=1",
    ]
    python = root / ".venv/bin/python"
    if not python.exists():
        run([*as_owner, "/usr/bin/python3", "-m", "venv", root / ".venv"], cwd=root)
    pip = [*as_owner, python, "-m", "pip", "install", "--disable-pip-version-check"]
    run([*pip, "pip>=26.2.2,<27"], cwd=root)
    run([*pip, "-r", root / "backend/requirements.lock.txt"], cwd=root)
    frontend = root / "frontend"
    run([*as_owner, "/usr/bin/npm", "ci", "--no-audit", "--no-fund"], cwd=frontend)
    # The web pages are built for the URL path they will be served under.
    run(
        [
            *as_owner,
            f"PORTAL_BASE_PATH={plan.get('base_path', '')}",
            "/usr/bin/npm",
            "run",
            "build",
        ],
        cwd=frontend,
    )
    validate_assets(frontend / "dist")
    return root


def prepare_tls(plan, staging):
    cert, key = staging / "portal.crt", staging / "portal.key"
    if plan["tls_mode"] == "3":
        names = {"DNS:localhost", "IP:127.0.0.1"}
        try:
            ipaddress.ip_address(plan["host"])
            names.add("IP:" + plan["host"])
        except ValueError:
            names.add("DNS:" + plan["host"])
        run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-keyout",
                key,
                "-out",
                cert,
                "-days",
                "365",
                "-subj",
                "/CN=" + plan["host"],
                "-addext",
                "subjectAltName=" + ",".join(sorted(names)),
            ],
            private=True,
        )
    else:
        for source, destination in [(plan["cert"], cert), (plan["key"], key)]:
            if not Path(source).is_file():
                raise SetupError("Certificate or private key file not found.")
            shutil.copyfile(source, destination)
    key.chmod(0o600)
    run(["openssl", "x509", "-in", cert, "-noout", "-checkend", "0"], private=True)
    try:
        ipaddress.ip_address(plan["host"])
        check = "-checkip"
    except ValueError:
        check = "-checkhost"
    checked = run(
        ["openssl", "x509", "-in", cert, "-noout", check, plan["host"]], private=True
    )
    # OpenSSL x509 -checkhost reports a mismatch on stdout but still exits 0.
    if b"does match certificate" not in checked.stdout:
        raise SetupError("The certificate does not cover the chosen hostname or IP.")
    public_cert = run(
        ["openssl", "x509", "-in", cert, "-pubkey", "-noout"], private=True
    ).stdout
    public_key = run(
        ["openssl", "pkey", "-in", key, "-passin", "pass:", "-pubout"], private=True
    ).stdout
    if public_cert != public_key:
        raise SetupError("The certificate and private key do not match.")
    return cert, key


def service_names(plan):
    return list(SERVICES)


def tls_access(plan):
    # The API reads the key itself; an older Nginx install kept it root-only.
    direct = plan.get("web_mode", "nginx") == "direct"
    (CONFIG / "tls").chmod(0o750 if direct else 0o700)
    (CONFIG / "tls/portal.key").chmod(0o640 if direct else 0o600)
    if direct:
        group = plan.get("group", "vmportal")
        run(["chown", f"root:{group}", CONFIG / "tls", CONFIG / "tls/portal.key"])


def service_units(plan, release):
    python = release / ".venv/bin/python"
    dependency = "vmportal-redis.service" + (
        " postgresql.service" if plan["database_mode"] == "managed" else ""
    )
    # The API serves HTTPS, the website and the console WebSocket on one port.
    endpoint = f"--host 0.0.0.0 --port {plan['port']} --ssl-certfile {CONFIG}/tls/portal.crt --ssl-keyfile {CONFIG}/tls/portal.key --no-proxy-headers --limit-concurrency 200"
    commands = {
        "redis": f"/usr/bin/redis-server {CONFIG}/redis.conf --daemonize no",
        "api": f"{python} -m uvicorn app.main:app {endpoint} --workers 2 --no-access-log",
        "worker": f"{python} -m celery -A app.tasks.worker:celery worker --loglevel=INFO --concurrency=2",
        "beat": f"{python} -m celery -A app.tasks.worker:celery beat --loglevel=INFO --schedule={STATE}/beat/celerybeat-schedule",
    }
    result = {}
    for name, command in commands.items():
        deps = "" if name == "redis" else dependency
        capabilities = (
            "AmbientCapabilities=CAP_NET_BIND_SERVICE\nCapabilityBoundingSet=CAP_NET_BIND_SERVICE"
            if name == "api" and plan["port"] < 1024
            else "CapabilityBoundingSet="
        )
        result[f"vmportal-{name}.service"] = f"""[Unit]
Description=VM Portal {name}
After=network-online.target {deps}
Wants=network-online.target
{("Requires=" + deps) if deps else ""}
PartOf={GROUP}

[Service]
Type=simple
User={plan["user"]}
Group={plan["group"]}
WorkingDirectory={release}/backend
Environment=HOME={STATE}/home
{("EnvironmentFile=" + str(CONFIG / "portal.env")) if name in {"api", "worker", "beat"} else ""}
{("ExecStartPre=" + str(python) + " " + str(release / "scripts/wait_dependencies.py")) if name == "api" else ""}
ExecStart={command}
{capabilities}
Restart=on-failure
RestartSec=5
TimeoutStopSec=1500
KillMode=mixed
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
# The account may own a home folder and the code; the services can only read
# them and write nothing but the portal's own data.
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={STATE}
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
ProtectKernelLogs=true
ProtectClock=true
ProtectHostname=true
ProtectProc=invisible
RestrictSUIDSGID=true
RestrictNamespaces=true
RestrictRealtime=true
LockPersonality=true
RemoveIPC=true
# Network clients and servers only: no raw sockets or other kernel interfaces.
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK
SystemCallArchitectures=native
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
"""
    parts = " ".join(PARTS)
    result[GROUP] = f"""[Unit]
Description=VM Portal (all services: {parts})
Wants={parts}
After={parts}

[Service]
# Holds the parts together: they follow its stop and restart via PartOf.
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecReload=/bin/true

[Install]
WantedBy=multi-user.target
"""
    return result


def backup_configs(old):
    if not old:
        return None
    backup = BACKUPS / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup.mkdir(parents=True, mode=0o700)
    BACKUPS.chmod(0o700)
    shutil.copytree(CONFIG, backup / "config")
    (backup / "units").mkdir()
    for name in SERVICES + LEGACY_SERVICES:
        if (UNITS / name).is_file():
            shutil.copy2(UNITS / name, backup / "units" / name)
    return backup


def dump_database(value, destination):
    params = connection_args(value)
    env = os.environ | {
        "PGPASSWORD": params["password"] or "",
        "PGSSLMODE": params.get("sslmode", "prefer"),
    }
    run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--host",
            params["host"],
            "--port",
            params["port"],
            "--username",
            params["user"],
            "--file",
            destination,
            params["dbname"],
        ],
        env=env,
        private=True,
    )
    destination.chmod(0o600)


def validate_assets(directory):
    if directory.is_symlink() or not (directory / "index.html").is_file():
        raise SetupError("No complete frontend build was found.")
    if any(path.is_symlink() for path in directory.rglob("*")):
        raise SetupError("The frontend build must not contain symlinks.")


def publish_assets(release, target, index=True):
    validate_assets(release / "frontend/dist")
    target.mkdir(parents=True, exist_ok=True)
    target.chmod(0o755)
    for item in (release / "frontend/dist").iterdir():
        if item.name == "index.html":
            continue
        if item.is_dir():
            shutil.copytree(item, target / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target / item.name)
    for path in target.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    if index:
        private_write(
            target / "index.html",
            (release / "frontend/dist/index.html").read_text(),
            0o644,
        )


def health(port, services=None, base=""):
    # Only the loopback readiness probe accepts the configured self-signed cert.
    # Public HTTPS and all Proxmox certificate verification remain unchanged.
    context = ssl._create_unverified_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )
    for _ in range(45):
        try:
            with opener.open(
                f"https://127.0.0.1:{port}{base}/api/health", timeout=3
            ) as response:
                if json.load(response).get("status") == "ok" and all(
                    active(name) for name in (services or SERVICES)
                ):
                    return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise SetupError(
        "The services did not become ready. Check them with: systemctl status vmportal-api vmportal-worker vmportal-beat vmportal-redis"
    )


def remove_legacy_web():
    """Stop and remove the Nginx front end an older install created."""
    for name in LEGACY_SERVICES:
        if (UNITS / name).exists():
            subprocess.run(["systemctl", "stop", name], capture_output=True)
            run(["systemctl", "disable", name])
            (UNITS / name).unlink()


def tidy_legacy_files(plan):
    """After a successful switch, drop files only the old Nginx layout used."""
    (CONFIG / "nginx.conf").unlink(missing_ok=True)
    for directory in (STATE / "www", STATE / "nginx"):
        if directory.is_dir() and directory != web_root():
            shutil.rmtree(directory)


def apply(plan, old, old_env, release, cert, key, gid):
    value = plan["env"]["DATABASE_URL"]
    old_value = None if plan.get("skip_old_database") else old_env.get("DATABASE_URL")
    for url in {value, old_value} - {None}:
        require_idle(url)
    backup = backup_configs(old)
    stopped = False
    try:
        if old:
            stopped = True
            for name in ("web", "beat", "api"):
                if (UNITS / f"vmportal-{name}.service").is_file():
                    run(["systemctl", "stop", f"vmportal-{name}"])
            require_idle(old_value)
            if (UNITS / "vmportal-worker.service").is_file():
                run(["systemctl", "stop", "vmportal-worker"])
        if backup:
            if old_value:
                dump_database(old_value, backup / "previous-database.dump")
            if value != old_value:
                dump_database(value, backup / "selected-database.dump")
        else:
            # Back up an existing target database before applying migrations.
            with connect(value) as db:
                has_tables = db.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE')"
                ).fetchone()[0]
            if has_tables:
                backup = BACKUPS / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
                backup.mkdir(parents=True, mode=0o700)
                BACKUPS.chmod(0o700)
                dump_database(value, backup / "selected-database.dump")
        manifest = {
            key: plan[key]
            for key in (
                "path",
                "user",
                "group",
                "base_path",
                "port",
                "host",
                "redis_port",
                "database_mode",
                "redis_namespace",
            )
        }
        manifest.update(
            release=str(release),
            status="installing",
            web_mode="direct",
            ufw_port=plan.get("ufw_port"),
        )
        if not old:
            private_write(
                CONFIG / "portal.env", environment_text(plan["env"]), 0o640, gid
            )
            private_write(
                CONFIG / "install.json", json.dumps(manifest, indent=2) + "\n"
            )
        env = os.environ | plan["env"] | {"HOME": str(STATE / "home")}
        prefix = [
            "runuser",
            "-u",
            plan["user"],
            "--",
            "/usr/bin/env",
            f"HOME={STATE}/home",
        ]
        run(
            [*prefix, release / ".venv/bin/python", "-m", "alembic", "upgrade", "head"],
            cwd=release / "backend",
            env=env,
        )
        (CONFIG / "tls").mkdir(mode=0o700, exist_ok=True)
        private_write(CONFIG / "tls/portal.crt", cert.read_text(), 0o644)
        private_write(CONFIG / "tls/portal.key", key.read_text(), 0o640, gid)
        tls_access(plan)
        private_write(CONFIG / "portal.env", environment_text(plan["env"]), 0o640, gid)
        private_write(CONFIG / "bootstrap-token", plan["env"]["BOOTSTRAP_TOKEN"] + "\n")
        redis_password = make_url(plan["env"]["REDIS_URL"]).password
        if not redis_password or not re.fullmatch(r"[A-Za-z0-9_-]+", redis_password):
            raise SetupError("The existing Redis password format is not supported.")
        redis_directory = STATE / "redis" / plan["redis_namespace"]
        if redis_directory.is_symlink():
            raise SetupError("The Redis state directory must not be a symlink.")
        redis_directory.mkdir(mode=0o700, exist_ok=True)
        run(
            [
                "chown",
                "-R",
                "--no-dereference",
                f"{plan['user']}:{plan['group']}",
                redis_directory,
            ]
        )
        private_write(
            CONFIG / "redis.conf",
            f"bind 127.0.0.1\nport {plan['redis_port']}\nprotected-mode yes\nrequirepass {redis_password}\nappendonly yes\ndir {redis_directory}\nsave 900 1\n",
            0o640,
            gid,
        )
        remove_legacy_web()
        for name, text in service_units(plan, release).items():
            private_write(UNITS / name, text, 0o644)
        target = web_root()
        # New hashed assets first; the page that references them goes live after the health check.
        publish_assets(release, target, index=False)
        run(["systemctl", "daemon-reload"])
        run(
            [
                "systemctl",
                "restart",
                "vmportal-redis",
                "vmportal-api",
                "vmportal-worker",
                "vmportal-beat",
                "vmportal",
            ]
        )
        health(plan["port"], service_names(plan), plan.get("base_path", ""))
        run(["systemctl", "enable", *service_names(plan)])
        open_firewall(plan, old)
        publish_assets(release, target)
        manifest["status"] = "ready"
        private_write(CONFIG / "install.json", json.dumps(manifest, indent=2) + "\n")
        tidy_legacy_files(plan)
    except (Exception, KeyboardInterrupt):
        if old and backup and (backup / "config").is_dir():
            print(
                "Installation failed; restoring the previous configuration and services..."
            )
            for name in SERVICES + LEGACY_SERVICES:
                subprocess.run(["systemctl", "stop", name], capture_output=True)
            shutil.copytree(backup / "config", CONFIG, dirs_exist_ok=True)
            for name in SERVICES + LEGACY_SERVICES:
                if not (backup / "units" / name).exists():
                    (UNITS / name).unlink(missing_ok=True)
            shutil.copytree(backup / "units", UNITS, dirs_exist_ok=True)
            if (CONFIG / "tls/portal.key").is_file():
                tls_access(old)
            run(["systemctl", "daemon-reload"])
            if stopped:
                previous = [
                    name
                    for name in SERVICES + LEGACY_SERVICES
                    if (backup / "units" / name).is_file()
                ]
                if previous:
                    run(["systemctl", "enable", *previous])
                    run(["systemctl", "start", *previous])
        elif not old:
            for name in SERVICES:
                if (UNITS / name).is_file():
                    subprocess.run(["systemctl", "stop", name], capture_output=True)
        raise
    return backup


def open_firewall(plan, old):
    """Allow the HTTPS port in UFW and drop a rule this installer added for an old port."""
    if plan.get("ufw_port"):
        run(["ufw", "allow", f"{plan['ufw_port']}/tcp", "comment", "vmportal"])
    previous = old.get("ufw_port")
    if previous and previous != plan.get("ufw_port") and shutil.which("ufw"):
        subprocess.run(["ufw", "delete", "allow", f"{previous}/tcp"], capture_output=True)


def current_release(old, plan):
    """The build already in the clone, reusable when only settings change."""
    root = Path(plan["path"])
    if (
        old.get("path") == plan["path"]
        and (root / ".venv/bin/python").exists()
        and (root / "frontend/dist/index.html").is_file()
    ):
        return root
    return None


def main():
    argparse.ArgumentParser(
        description="Interactive installer; normally run: sudo bash setup-server.sh"
    ).parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Run: sudo bash setup-server.sh")
    # "a+" keeps the running installer's PID readable for a second attempt.
    lock = open("/run/lock/vmportal-setup.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.seek(0)
        pid = lock.read().strip()
        raise SystemExit(
            f"Another installer run is already in progress (PID {pid or 'unknown'}).\n"
            "If an SSH session dropped, it may still be working: check with\n"
            f"  ps -o pid,etime,args --ppid {pid or '<PID>'} -p {pid or '<PID>'}\n"
            "and wait for it to finish. If it is stuck, stop it so it can restore the previous state:\n"
            f"  sudo kill -INT {pid or '<PID>'}\n"
            "Run the installer inside tmux (tmux new -s vmportal) so a dropped connection does not stop it."
        ) from None
    lock.seek(0)
    lock.truncate()
    lock.write(f"{os.getpid()}\n")
    lock.flush()
    warnings.filterwarnings("error", category=GetPassWarning)
    print("\nVM Portal server setup (HTTPS only)\n")
    try:
        old, old_env = previous_settings()
        action = "install"
        if old:
            print(f"Existing installation found at {old.get('path')}.")
            choice = choose(
                "What do you want to do",
                {
                    "1": "Change settings only (keep the installed version)",
                    "2": "Update the application from this folder and review settings",
                },
                "1",
            )
            action = "settings" if choice == "1" else "update"
        plan = collect(old, old_env, action)
        if plan["action"] == "settings" and not current_release(old, plan):
            print(
                "The installed release cannot be reused, so the application will be rebuilt."
            )
            plan["action"] = "update"
        environment_text(plan["env"])
        changes = describe_changes(old, old_env, plan)
        if old and not changes and plan["action"] == "settings":
            print("\nNothing changed. The installation was left as it is.")
            return
        print(
            f"\nURL: {portal_url(plan['host'], plan['port'], plan['base_path'])}\nInstalled in: {plan['path']}\nRuns as: {plan['user']}\nDatabase: {database_label(plan['env']['DATABASE_URL'])}\nCreate new database: {'yes' if plan['create_db'] else 'no'}"
        )
        if changes:
            print("\nChanges and what they affect:")
            for name, change, impact in changes:
                print(f"  * {name}: {change}\n    WARNING: {impact}")
            print(
                "  * All portal services restart; users may see a short interruption."
            )
        impactful = any(name != "Application" for name, change, impact in changes)
        if not yes("\nApply these settings", not impactful):
            raise SetupError("Cancelled. Nothing was changed.")
        check_previous_database(plan, old_env)
        with tempfile.TemporaryDirectory(prefix="vmportal-candidate-") as temporary:
            staging = Path(temporary)
            print("Checking the HTTPS certificate...")
            cert, key = prepare_tls(plan, staging)
            if plan["create_db"]:
                print("Creating the database and user...")
                create_database(plan["env"]["DATABASE_URL"])
            verify_database(plan)
            require_idle(plan["env"]["DATABASE_URL"])
            uid, gid = service_identity(plan)
            if plan["action"] == "settings":
                release = current_release(old, plan)
                print(f"Keeping the current build in {release}")
            else:
                print(f"Installing dependencies and building in {plan['path']}...")
                release = build_in_place(plan)
            print("Backing up, updating the database schema and starting services...")
            backup = apply(plan, old, old_env, release, cert, key, gid)
        print(
            f"\nReady: {portal_url(plan['host'], plan['port'], plan['base_path'])}\nSetup code: sudo cat {CONFIG}/bootstrap-token\nSettings: {CONFIG}/portal.env\nRun setup-server.sh again to change settings or update the application."
        )
        if plan["tls_mode"] == "3":
            print(
                "A self-signed certificate is in use; browsers will warn about it. Run the installer again to switch to your organisation's or domain's certificate."
            )
        if backup:
            print(f"Backup: {backup}")
    except (SetupError, OSError, ValueError, psycopg.Error) as exc:
        # psycopg errors can include connection details; never print them raw.
        message = (
            str(exc)
            if isinstance(exc, SetupError)
            else "Setup failed. Check files, permissions and services, then run the installer again."
        )
        raise SystemExit(message) from None
    except (KeyboardInterrupt, EOFError, GetPassWarning):
        raise SystemExit("Setup cancelled.") from None
    finally:
        lock.close()


if __name__ == "__main__":
    main()
