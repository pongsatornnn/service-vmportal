# คู่มือครบ: Ubuntu 24.04 Template พร้อมเครื่องมือและ SSH Password

แนวทางนี้เตรียม SSH policy ภายใน Template ครั้งเดียว โดยยังให้ Portal กำหนด VM Username/Password แต่ละคำขอ ไม่มีการใช้ vendor snippet และไม่ต้องสร้าง portal-snippets storage

ขั้นตอนด้านล่างเป็นคู่มือสำหรับ Admin ไม่ได้รัน Clone, Start, แก้ Template หรือเปลี่ยน ACL บน Proxmox ให้โดยอัตโนมัติ VMID 9300 เป็นตัวอย่าง ต้องตรวจว่าเลขว่างและเปลี่ยนทุกจุดตามจริงถ้าเลือกเลขอื่น

## 1. แยกให้ออกว่ารันคำสั่งที่ไหน

| สถานที่ | งาน |
| --- | --- |
| Proxmox Web UI / Node3 Shell | Clone, ปรับ Cloud-Init settings, Convert Template และ ACL |
| Console ของ Ubuntu VM 9300 | apt, ตั้ง SSH, ล้างสถานะก่อนทำ Template |
| Portal (URL ที่ติดตั้ง) | เลือก Template ใหม่, ตรวจเชื่อมต่อ, ขอและอนุมัติ VM |

## 2. สร้างจาก Ubuntu 24.04 Cloud Image

Template ปัจจุบันคือ VMID **9200**, ชื่อ `ubuntu2404-template-portal` บน Node3, Storage `local-lvm`, boot `scsi0`, มี Cloud-Init drive `ide2` และเปิด QEMU Guest Agent แนวทางนี้ตั้ง SSH policy ภายในเครื่อง ไม่ใช้ vendor snippet

เตรียม Template ใหม่ด้วย VMID ตัวอย่าง **9300** โดยตรวจว่าเลขว่างก่อน ไม่รันคำสั่งสร้างทับ 9200 ค่าทรัพยากรต้องตรง Setup ปัจจุบัน

รันบน Shell ของ Node3:

```bash
pvesh get /cluster/resources --type vm
pvesm status
ip link show VLAN48
mkdir -p /var/lib/vz/template/iso/ubuntu-noble
cd /var/lib/vz/template/iso/ubuntu-noble
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
wget https://cloud-images.ubuntu.com/noble/current/SHA256SUMS
grep 'noble-server-cloudimg-amd64.img$' SHA256SUMS | sha256sum --check --status && echo 'Checksum OK'
```

ต้องตรวจได้ Checksum OK ก่อนทำต่อ หาก Node ดาวน์โหลดไม่ได้ให้ส่ง image และ checksum ชุดเดียวกันผ่าน SCP/SFTP

```bash
qm create 9300 --name ubuntu2404-template-portal --memory 2048 --cores 2 --scsihw virtio-scsi-pci --net0 virtio,bridge=VLAN48 --pool Portal-Service
qm set 9300 --scsi0 local-lvm:0,import-from=/var/lib/vz/template/iso/ubuntu-noble/noble-server-cloudimg-amd64.img
qm set 9300 --ide2 local-lvm:cloudinit --boot order=scsi0 --agent enabled=1 --ciuser ubuntu --ipconfig0 ip=dhcp
qm disk resize 9300 scsi0 20G
qm set 9300 --serial0 socket --vga serial0
qm config 9300
```

ขนาด 20 GiB เป็นตัวอย่างสำหรับเครื่องเตรียมใหม่ Template ปัจจุบัน 9200 มีดิสก์ 3584 MiB; ตั้ง Template disk ใน Portal ให้ไม่ต่ำกว่าขนาดจริง ไม่ต้องแก้ดิสก์ Template ปัจจุบันตามตัวอย่าง

VM9300 → Cloud-Init ตั้ง User `ubuntu`, Password ชั่วคราวผ่าน UI และ DHCP → Regenerate Image → Start → Console serial/xterm.js → Login ด้วย ubuntu ตรวจ `ip -br address` แล้วทำขั้นถัดไป

## 3. ติดตั้งเครื่องมือใน Ubuntu VM 9300

คำสั่งในส่วนนี้รันภายใน Ubuntu Guest เท่านั้น ไม่ใช่ Shell ของ Proxmox หรือ Server Portal

```bash
sudo cloud-init status --wait
sudo apt update
sudo apt install -y nano net-tools curl wget htop unzip zip jq dnsutils iputils-ping ca-certificates openssh-server cloud-init qemu-guest-agent
```

ต้องมี Ubuntu package mirror ที่ VM เข้าถึงได้ในขั้นเตรียม Image เครื่องที่ Clone ภายหลังจะมี packages ที่ติดตั้งไว้พร้อมใช้

## 4. ตั้ง Cloud-Init และ OpenSSH ภายใน Ubuntu Guest

```bash
sudo tee /etc/cloud/cloud.cfg.d/99-portal-ssh.cfg >/dev/null <<'CLOUD'
ssh_pwauth: true
disable_root: true
ssh_deletekeys: true
CLOUD
```

```bash
sudo tee /etc/ssh/sshd_config.d/00-portal-ssh.conf >/dev/null <<'SSH'
PasswordAuthentication yes
PubkeyAuthentication yes
PermitRootLogin no
SSH
```

```bash
sudo /usr/sbin/sshd -t
sudo systemctl enable --now ssh
sudo systemctl reload ssh
sudo /usr/sbin/sshd -T | grep -E '^(passwordauthentication|permitrootlogin) '
```

ต้องได้ `passwordauthentication yes` และ `permitrootlogin no` หากไม่ตรง ให้ตรวจ /etc/ssh/sshd_config และ drop-ins ที่มาก่อน รวมถึง Match/AllowUsers ของ Template; Ubuntu ใช้ค่าแรกที่อ่านสำหรับตัวเลือกส่วนใหญ่

หาก Guest เปิด UFW อยู่ ให้ตรวจและอนุญาต OpenSSH ภายใน Guest ตามนโยบายของ LAN ไม่เปลี่ยน Firewall ของ Proxmox ตามคำสั่ง Guest นี้:

```bash
sudo ufw status
# เฉพาะเมื่อ UFW active และยังไม่อนุญาต SSH:
sudo ufw allow OpenSSH
```

## 5. ทดสอบ SSH ของ VM เตรียมเครื่อง

ภายใน VM:

```bash
ip -4 -br addr
```

จากคอมพิวเตอร์/Portal Server ที่เข้าถึง VLAN48 ได้:

```bash
ssh ubuntu@<IP-VM-9300>
```

Login ด้วย Password ชั่วคราวให้สำเร็จก่อน Clean หากเข้าไม่ได้ให้ตรวจ DHCP, routing, port 22 และ Guest/Proxmox firewall ก่อน

## 6. ล้างสถานะก่อนทำ Template

ภายใน Ubuntu VM 9300 เข้า Root shell ครั้งเดียวก่อนล็อกรหัสชั่วคราว:

```bash
sudo -i
```

จาก Root shell ภายใน Guest:

```bash
passwd -l ubuntu
if [ -f /home/ubuntu/.ssh/authorized_keys ]; then
    truncate -s 0 /home/ubuntu/.ssh/authorized_keys
fi
apt-get clean
cloud-init clean --logs --machine-id
poweroff
```

ล็อกรหัสของบัญชีเตรียมเครื่องและล้าง Public Key ที่อาจติดมาจาก Template เดิม ไม่ฝังรหัสร่วมไว้ให้ทุก Clone Cloud-Init ของ VM ใหม่จะตั้ง Username/Password ตามคำขอใหม่ ส่วน `ssh_deletekeys: true` ทำให้ cloud-init สร้าง SSH Host Keys ใหม่เมื่อเริ่มเป็น instance ใหม่

หลัง Clean ให้ปิดทันทีและอย่า Start 9300 อีกก่อน Convert Template

## 7. Convert Template บน Proxmox

กลับไป Proxmox → Node3 → Shell หลัง VM 9300 หยุดแล้ว:

```bash
qm status 9300
qm set 9300 --delete cipassword
# ลบ sshkeys และ cicustom แยกเฉพาะฟิลด์ที่มีและไม่ใช้จริง
qm cloudinit update 9300
qm template 9300
```

คำสั่งนี้ทำกับ VM เตรียมเครื่อง 9300 ล้างค่า Cloud-Init ชั่วคราวและ Custom Cloud-Init ที่ไม่ใช้สำหรับแนวทางนี้ ไม่เปลี่ยน Template 9200

## 8. สิทธิ์ของ Service User / Token

Template ปัจจุบัน 9200 ต้องมี VM.Clone/VM.Audit ทั้ง Service User และ Token เมื่อเตรียม Template ใหม่ 9300 ให้เพิ่มสิทธิ์บน /vms/9300 ตามด้านล่าง ส่วน Pool/Storage/Node/Bridge ใช้สิทธิ์ตาม [คู่มือ Admin](ADMIN-GUIDE.md#สิทธิ์-proxmox)

ทำใน Proxmox Web UI:

1. Datacenter → Permissions → Roles → Create role เช่น `PortalTemplateClone` เลือกเฉพาะ `VM.Clone`, `VM.Audit`
2. Datacenter → Permissions → Add → User Permission: Path `/vms/9300`, User `vmportal@pve`, Role `PortalTemplateClone`
3. หาก Token เปิด Privilege Separation ให้ Add → API Token Permission ที่ Path `/vms/9300`, Token `vmportal@pve!portal-api`, Role เดียวกัน
4. คงสิทธิ์ Pool/Storage/Node/Bridge ที่มีอยู่ ไม่เพิ่ม Administrator หรือสิทธิ์ทั่วทั้ง /vms

Privilege separation ใช้สิทธิ์ร่วมของ User และ Token การให้เฉพาะ Token จะไม่ขยายเกินสิทธิ์ User; ถ้าปิด separation Token ใช้สิทธิ์ของ User ไม่ต้องปิด separation เพื่อแก้ปัญหา

ผู้ใช้ Portal ทั่วไปไม่ต้องมีบัญชี Proxmox/API Token แยกคน และ VM Username ที่เลือกจะสร้างภายใน Guest ผ่าน Cloud-Init ไม่ใช่บัญชีบน Proxmox

วิธีนี้ไม่ต้องใช้ Datastore.AllocateSpace บน portal-snippets/local เพิ่ม เพราะไม่ได้ใช้ snippet

## 9. ตั้ง Portal ให้ใช้ 9300

Portal → Setup:

- Endpoint/CA/Token ใช้ค่าที่ตรวจผ่านเดิม
- Node Node3, Pool Portal-Service, Storage local-lvm
- Bridge และ Allowlist VLAN48
- Template VMID **9300**
- Boot Disk Device และ Template Disk GiB ตรงกับ Hardware ของ 9300 จริง
- SSH password vendor snippet **เว้นว่าง**
- บันทึก → ตรวจ Read-only/TLS → เปิดใช้งานเมื่อ Admin พร้อมรับงานจริง

การเปลี่ยน Template ต้องไม่มีคำขอ pending หรือ provision job queued/running ส่วน Node/Pool/Storage/Bridge ยังล็อกตามทรัพยากรเดิม ไม่แก้ DB เพื่อข้ามข้อจำกัด

## 10. ขอ VM ด้วยนโยบายจาก Template

หน้า Requests:

- VM username: ชื่อที่ต้องการ เช่น developer01 (ไม่ใช้ root/บัญชีระบบ)
- วิธีเข้า VM: Password
- ตั้งและยืนยัน Password อย่างน้อย 12 ตัวอักษร
- ใช้นโยบาย SSH จาก Template ไม่ต้องกำหนด vendor snippet เพิ่ม

ระบบใช้ SSH policy จาก Template ที่เพิ่งเตรียม และส่ง Username/Password เฉพาะคำขอผ่าน ciuser/cipassword ตามปกติ จากนั้น Admin อนุมัติคำขอหนึ่งเครื่องเพื่อทำ acceptance จริง

หลัง Guest บูตและ Cloud-Init จบ:

```bash
ssh developer01@<IP-VM-ใหม่>
```

ตรวจว่า Login ด้วยรหัสของคำขอได้, root SSH ถูกปิด, packages อยู่ครบ, CPU/RAM/Disk/Pool ถูกต้อง และผู้ใช้อื่นจัดการ VM นี้ไม่ได้

## อ้างอิง

- [Ubuntu OpenSSH](https://ubuntu.com/server/docs/how-to/security/openssh-server/)
- [Cloud-Init password/SSH modules](https://docs.cloud-init.io/en/latest/reference/modules.html)
- [Cloud-Init clean CLI](https://docs.cloud-init.io/en/latest/reference/cli.html)
- [Proxmox user/token permissions](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc)
- [Proxmox Cloud-Init](https://github.com/proxmox/pve-docs/blob/master/qm-cloud-init.adoc)

## หาก Template ขาด Guest Agent

ใช้ขั้นตอนสร้างใหม่จาก Cloud Image ด้านบนให้ครบก่อน Convert ไม่ Boot หรือแก้ Template ปัจจุบันโดยตรง Portal ตั้ง agent=1 ให้ VM ใหม่ แต่ package ต้องติดตั้งอยู่ใน Template ส่วน VM ที่สร้างไปแล้วไม่เปลี่ยนตาม Template ต้องจัดการ Agent แยกในแต่ละเครื่อง
