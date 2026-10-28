# VM Portal — Proxmox Self-Service

ระบบให้ผู้ใช้ขอ VM บน Proxmox ผ่านเว็บ โดยมี Admin อนุมัติ: ผู้ใช้สมัคร → Admin อนุมัติบัญชี → ผู้ใช้เลือก Template และขอ VM → Admin อนุมัติ → ระบบ Clone, ตั้งค่า Cloud-Init, ขยาย Disk และเปิดเครื่องให้

FastAPI + PostgreSQL + Redis/Celery + React ติดตั้งบน Ubuntu โดยตรงเป็น systemd services ไม่ใช้ Docker และไม่ต้องใช้ Nginx (Portal เปิด HTTPS เอง)

## Quick start (Ubuntu 24.04 LTS)

```bash
git clone https://github.com/pongsatornnn/service-vmportal.git
cd service-vmportal
sudo bash setup-server.sh
```

The installer (English) asks for:

1. **URL path** the portal is served under, e.g. `/vmportal` → `https://server:443/vmportal/` (or `/` for the site root)
2. **HTTPS port** and the **hostname/IP** users open
3. **HTTPS certificate**: your certificate and key, or a generated self-signed one
4. **Database**: an existing PostgreSQL database/user, or create one on this server

It installs dependencies, builds the app into `/opt/vmportal`, runs migrations, starts the services and checks they are healthy. Then:

```bash
sudo cat /etc/vmportal/bootstrap-token   # one-time code to create the first admin
```

Open the URL shown, create the admin, then set up Proxmox and templates in the web UI.

Run `sudo bash setup-server.sh` again at any time to **change settings only** (no rebuild) or to **update the application**. Every change is listed with what it affects before anything is applied, the database is backed up first, and a failed run restores the previous setup.

## เอกสาร

- [คู่มือตัวติดตั้ง Server](docs/SERVER-INSTALLER.md) — คำถามทั้งหมด, การรันซ้ำ, ตำแหน่งไฟล์, backup
- [ใช้งานครั้งแรกและดูแลระบบ](docs/SETUP.md) — สร้าง Admin, เชื่อม Proxmox, เพิ่ม Template, จัดการ service
- [คู่มือผู้ดูแล](docs/ADMIN-GUIDE.md) และคู่มือในเว็บ (เมนู คู่มือผู้ดูแลระบบ) รวมวิธีสร้าง Template Ubuntu, Debian และ Windows Server
- [การจัดการ VM](docs/VM-MANAGEMENT.md) — IP, Console, Restart, คำขอลบ
- [รหัสผ่านและการกู้คืน](docs/PASSWORD-RECOVERY.md) — เปลี่ยนรหัส, โค้ดกู้คืน, รีเซ็ตรหัส Admin จาก Server
- [SSH Password Login](docs/SSH-PASSWORD-SETUP.md) และ [เตรียม Template พร้อม SSH Password](docs/TEMPLATE-SSH-PASSWORD.md)
- [Operations และการกู้งานค้าง](docs/OPERATIONS.md)

## สิ่งที่ต้องมี

- Ubuntu 24.04 LTS, sudo และ Internet ระหว่างติดตั้ง/อัปเดต (apt, pip, npm)
- Proxmox VE ที่มี API Token และ Template ที่มี Cloud-Init + QEMU Guest Agent
- เปิด TCP port HTTPS ที่เลือกใน firewall (ตัวติดตั้งไม่แก้ firewall ให้)
