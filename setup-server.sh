#!/usr/bin/env bash
# Interactive Ubuntu installer. Run this file from a cloned repository.
set -Eeuo pipefail
umask 077

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'HELP'
Usage: sudo bash setup-server.sh

Interactive installer for Ubuntu 24.04 LTS:
  - URL path the portal is served under (e.g. /vmportal), HTTPS port and hostname
  - Existing PostgreSQL user/database or creation of a local user/database
  - HTTPS served directly by the portal (no Nginx needed)
  - HTTPS certificate/key or generated self-signed certificate
  - Runs from this cloned folder as the account that started sudo (never root):
    dependencies, the web build and the portal data belong to that account
  - Persistent systemd services, migrations, frontend build and health check

Run again to change settings only (no rebuild) or to update the application.
Every change is listed with what it affects before anything is applied.
Existing database settings and encryption keys are kept unless you change them.
An older install that used Nginx is switched to direct HTTPS automatically.
HELP
  exit 0
fi
if (( $# )); then
  printf '%s\n' 'Unknown option. Use --help.' >&2
  exit 2
fi
if (( EUID != 0 )); then
  exec sudo -- bash "${BASH_SOURCE[0]}"
fi
setup_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if [[ ! -f "$setup_repo/backend/requirements.lock.txt" || ! -f "$setup_repo/scripts/setup_server.py" ]]; then
  printf '%s\n' 'Run setup-server.sh from the complete cloned project.' >&2
  exit 1
fi
# shellcheck source=/dev/null
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 ]]; then
  printf '%s\n' 'This installer supports Ubuntu 24.04 LTS.' >&2
  exit 1
fi
printf '%s\n' 'Installing prerequisites from Ubuntu package sources…'
export DEBIAN_FRONTEND=noninteractive
# Wait for apt jobs that start on their own (apt-daily, unattended-upgrades).
apt_wait=(-o DPkg::Lock::Timeout=600)
apt-get "${apt_wait[@]}" update
# The portal runs its own Redis; the package's default instance is only kept if
# it was already installed for something else.
stock_redis_new=0
dpkg-query -W -f='${Status}' redis-server 2>/dev/null | grep -q 'install ok installed' || stock_redis_new=1
apt-get "${apt_wait[@]}" install -y python3 python3-venv python3-dev build-essential libpq-dev \
  postgresql-client redis-server nodejs npm openssl rsync ca-certificates
if (( stock_redis_new )); then
  systemctl disable --now redis-server.service >/dev/null 2>&1 || true
fi
python3 -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ is required"'
node -e 'if(Number(process.versions.node.split(".")[0])<18)process.exit(1)'
setup_bootstrap=$(mktemp -d /var/tmp/vmportal-setup.XXXXXXXX)
trap 'rm -rf -- "$setup_bootstrap"' EXIT
python3 -m venv "$setup_bootstrap/venv"
"$setup_bootstrap/venv/bin/python" -m pip install --disable-pip-version-check "pip>=26.2.2,<27"
"$setup_bootstrap/venv/bin/python" -m pip install --disable-pip-version-check \
  -r "$setup_repo/backend/requirements.lock.txt"
"$setup_bootstrap/venv/bin/python" "$setup_repo/scripts/setup_server.py"
