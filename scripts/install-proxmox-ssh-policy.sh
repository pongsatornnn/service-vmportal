#!/usr/bin/env bash
# Run manually by a Proxmox administrator on Node3. No VM or template is changed.
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
  echo 'Run this reviewed installer as root on the Proxmox node.' >&2
  exit 1
fi
command -v pvesh >/dev/null
command -v pvesm >/dev/null
storage_id=portal-snippets
storage_path=/var/lib/vz/portal-snippets
node_name=$(hostname -s)
existing=$(pvesh get /storage --output-format json | python3 -c 'import json,sys; print(next((x["storage"] for x in json.load(sys.stdin) if x["storage"]=="portal-snippets"), ""))')
if [[ -z ${existing} ]]; then
  pvesm add dir "${storage_id}" --path "${storage_path}" --content snippets --nodes "${node_name}"
else
  pvesh get "/storage/${storage_id}" --output-format json | python3 -c 'import json,sys; c=json.load(sys.stdin); valid=c.get("type")=="dir" and c.get("path")=="/var/lib/vz/portal-snippets" and set(c.get("content", "").split(","))=={"snippets"}; sys.exit(0 if valid else "Existing portal-snippets storage differs; inspect it manually. Nothing overwritten.")'
fi
if [[ -L ${storage_path} || -L ${storage_path}/snippets ]]; then
  echo 'Refusing a symlinked snippets directory.' >&2
  exit 1
fi
install -d -m 0755 "${storage_path}/snippets"
policy_tmp=$(mktemp)
trap 'rm -- "$policy_tmp"' EXIT
cat > "${policy_tmp}" <<'POLICY'
#cloud-config
ssh_pwauth: true
disable_root: true
write_files:
  - path: /etc/ssh/sshd_config.d/00-vmportal-password.conf
    owner: root:root
    permissions: '0644'
    content: |
      PasswordAuthentication yes
      PermitRootLogin no
runcmd:
  - [sh, -c, '/usr/sbin/sshd -t && systemctl reload ssh']
POLICY
target="${storage_path}/snippets/portal-ssh-password.yaml"
if [[ -L ${target} ]]; then
  echo 'Refusing to replace a symlink.' >&2
  exit 1
fi
if [[ -e ${target} ]] && ! cmp -s "${policy_tmp}" "${target}"; then
  echo 'Existing policy differs; review it manually. Nothing overwritten.' >&2
  exit 1
fi
install -m 0644 "${policy_tmp}" "${target}"
echo "Installed policy on ${node_name}; no VM created, no template modified, no ACL changed."
sha256sum "${target}"
echo 'Portal Setup volume: portal-snippets:snippets/portal-ssh-password.yaml'
echo 'Administrator: grant Datastore.AllocateSpace only on /storage/portal-snippets to the service user/token as required, then verify in Portal Setup.'
