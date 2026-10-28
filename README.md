# VM Portal — Proxmox Self-Service

ระบบให้ผู้ใช้ขอ VM บน Proxmox ผ่านเว็บ โดยมี Admin อนุมัติ: ผู้ใช้สมัคร → Admin อนุมัติบัญชี → ผู้ใช้เลือก Template และขอ VM → Admin อนุมัติ → ระบบ Clone, ตั้งค่า Cloud-Init, ขยาย Disk และเปิดเครื่องให้

FastAPI + PostgreSQL + Redis/Celery + React ติดตั้งบน Ubuntu เป็น systemd services

## วิธีติดตั้ง

### สิ่งที่ต้องมี

- เครื่อง **Ubuntu 24.04 LTS** ที่มีบัญชีที่ใช้ `sudo` ได้ และต่อ Internet ระหว่างติดตั้งหรืออัปเดต (apt, pip, npm)
- **Proxmox VE** ที่มี API Token และ Template ที่มี Cloud-Init กับ QEMU Guest Agent (ตั้งค่าในเว็บหลังติดตั้ง)
- port HTTPS ที่จะใช้ (เช่น 443 หรือ 8443) เปิดไว้ใน firewall ตัวติดตั้งไม่แก้ firewall ให้

### 1. Clone และรันตัวติดตั้ง

Login ด้วยบัญชีที่จะให้ Portal รัน (ไม่ใช่ root) แล้ว:

```bash
git clone https://github.com/pongsatornnn/service-vmportal.git
cd service-vmportal
sudo bash setup-server.sh
```

- **ไม่ต้องใช้ `sudo git clone`**: บริการทั้งหมดรันด้วยบัญชีที่สั่ง `sudo bash setup-server.sh` บัญชีนี้เป็นผู้ build และเป็นเจ้าของไฟล์ ถ้าโฟลเดอร์เป็นของบัญชีอื่น ตัวติดตั้งจะโอนความเป็นเจ้าของให้
- Portal **รันจากโฟลเดอร์ที่ clone ไว้** ห้ามลบหรือย้ายโฟลเดอร์นี้หลังติดตั้ง ถ้าย้าย ให้รันตัวติดตั้งซ้ำจากที่ใหม่
- ไม่ใช้ Docker และไม่ต้องใช้ Nginx เพราะ Portal เปิด HTTPS เอง

### 2. ตอบคำถามของตัวติดตั้ง

ตัวติดตั้งเป็นภาษาอังกฤษ กด Enter เพื่อใช้ค่าในวงเล็บ

| คำถาม | ตัวอย่าง |
|---|---|
| URL path users open | `/vmportal` จะได้ `https://server/vmportal/` หรือ `/` เพื่อให้อยู่ที่หน้าแรก |
| HTTPS port | `443` หรือ `8443` |
| Hostname or IP users will open | `portal.example.org` หรือ `192.168.1.10` |
| HTTPS certificate | ใช้ไฟล์ `.crt`/`.key` ของคุณ หรือให้สร้าง self-signed |
| Database | ใช้ PostgreSQL ที่มีอยู่ หรือให้สร้าง DB/User บนเครื่องนี้ |

ตัวติดตั้งจะแสดงสรุปให้ยืนยัน แล้วติดตั้ง packages, build หน้าเว็บ, สร้าง DB schema, เปิด systemd services และตรวจว่าเว็บตอบสนอง เมื่อเสร็จจะแสดง URL

### 3. สร้าง Admin คนแรก

```bash
sudo cat /etc/vmportal/bootstrap-token
```

เปิด URL ที่แสดง กรอกรหัสนี้พร้อม Username/Password ของ Admin รหัสใช้ได้ครั้งเดียว ถ้าใช้ self-signed browser จะเตือนเรื่องใบรับรอง

### 4. ตั้งค่าในเว็บ

1. **ตั้งค่า → Proxmox**: กรอก API Endpoint, Token และ CA แล้วเลือก Node, Storage, Pool และเครือข่าย → **บันทึกและตรวจสอบ** → **เปิดใช้งาน**
2. **ตั้งค่า → Template**: **+ เพิ่ม Template** ตั้งชื่อที่ผู้ใช้เห็น (เช่น Ubuntu 24.04) เลือก VMID → **ตรวจสอบ** → **เปิดให้ขอ**
3. ลองขอ VM หนึ่งเครื่องและอนุมัติ ก่อนเปิดให้ผู้ใช้ทั่วไป

วิธีเตรียม Template บน Proxmox ดูในเว็บที่เมนู **คู่มือผู้ดูแลระบบ**

## อัปเดตและเปลี่ยนค่า

```bash
cd ~/service-vmportal
git pull
sudo bash setup-server.sh
```

ตัวติดตั้งจะถามว่าจะทำอะไร:

- **1. Change settings only**: เปลี่ยน URL path, port, hostname, certificate หรือ DB โดยไม่ build ใหม่
- **2. Update the application**: ติดตั้งรุ่นที่เพิ่ง `git pull` มา

ก่อนลงมือ ตัวติดตั้งจะแสดงทุกค่าที่เปลี่ยนพร้อมผลกระทบ และสำรอง DB ไว้ที่ `/var/backups/vmportal/` ทุกครั้ง ถ้าขั้นใดล้มเหลวจะคืนค่าและบริการเดิมให้ แต่คืนโค้ดให้ไม่ได้ ถ้ารุ่นใหม่มีปัญหา ให้ `git checkout <commit เดิม>` แล้วรันตัวติดตั้งซ้ำ

## ดูแลระบบ

```bash
sudo systemctl status vmportal-api vmportal-worker vmportal-beat vmportal-redis
sudo systemctl restart vmportal-api vmportal-worker vmportal-beat
sudo journalctl -u vmportal-api -u vmportal-worker -f
```

| รายการ | ตำแหน่ง |
|---|---|
| โปรแกรม | โฟลเดอร์ที่ clone เช่น `~/service-vmportal` |
| ค่าตั้ง, secrets, certificate | `/etc/vmportal/` (สำรอง `portal.env` ไว้เสมอ เพราะมี Master Key) |
| ข้อมูลของ Portal และไฟล์หน้าเว็บ | `/var/lib/vmportal/` |
| Backup | `/var/backups/vmportal/` |

ลืมรหัส Admin ทุกบัญชี:

```bash
cd ~/service-vmportal
sudo .venv/bin/python scripts/reset_admin_password.py
```

## เอกสาร

- [คู่มือตัวติดตั้ง Server](docs/SERVER-INSTALLER.md): รายละเอียดทุกคำถาม, การรันซ้ำ, การคืนค่าเมื่อล้มเหลว
- [ใช้งานครั้งแรกและดูแลระบบ](docs/SETUP.md)
- [คู่มือการใช้งานสำหรับผู้ใช้](docs/USER-GUIDE.md) (ในเว็บที่เมนู คู่มือการใช้งาน)
- [คู่มือผู้ดูแล](docs/ADMIN-GUIDE.md): ระดับผู้ดูแล และคู่มือในเว็บ (วิธีสร้าง Template Ubuntu, Debian และ Windows Server)
- [การจัดการ VM](docs/VM-MANAGEMENT.md): IP, Console, Restart, คำขอลบ
- [รหัสผ่านและการกู้คืน](docs/PASSWORD-RECOVERY.md)
- [SSH Password Login](docs/SSH-PASSWORD-SETUP.md) และ [เตรียม Template พร้อม SSH Password](docs/TEMPLATE-SSH-PASSWORD.md)
- [Operations และการกู้งานค้าง](docs/OPERATIONS.md)
