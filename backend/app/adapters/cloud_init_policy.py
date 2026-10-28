"""Portal-owned vendor policy: no user input or passwords in this document."""

SSH_PASSWORD_VENDOR_DATA = """#cloud-config
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
"""
