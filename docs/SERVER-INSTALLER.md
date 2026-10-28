# ติดตั้ง Server ด้วยไฟล์เดียว

รองรับ **Ubuntu 24.04 LTS**, systemd และบัญชีที่ใช้ sudo ได้ ต้องมี Internet สำหรับ apt, pip และ npm ในขั้นติดตั้ง/อัปเดต Runtime ใช้งานใน LAN ได้ตามปกติ

```bash
git clone https://github.com/pongsatornnn/vmportal.git
cd vmportal
sudo bash setup-server.sh
```

ตัวติดตั้งดาวน์โหลด dependencies จาก Ubuntu package sources, ติดตั้ง Python packages ตาม lockfile และ build frontend โดยไม่ต้องเรียกคำสั่งติดตั้งอื่นเอง ข้อความในตัวติดตั้งเป็นภาษาอังกฤษ

## คำถามระหว่างติดตั้ง

1. **URL path** ที่เว็บเปิดอยู่ เช่น `/vmportal` จะได้ `https://server:port/vmportal/` หรือ `/` ถ้าต้องการให้อยู่ที่หน้าแรกของ server ใช้ได้เฉพาะตัวพิมพ์เล็ก ตัวเลข และขีดกลาง คั่นด้วย `/` ถ้าเปิดหน้าแรกของ server จะพาไปที่ path นี้เอง โปรแกรมติดตั้งไว้ที่ `/opt/vmportal` เสมอ ไม่ต้องเลือก
2. **HTTPS port** ค่าเริ่มต้น `443` เลือก `8443` หรือ port อื่นที่ว่างได้
3. **Hostname/IP** ที่ผู้ใช้เปิดเว็บ เช่น `portal.example.org` หรือ `192.168.1.10` (IPv4)
4. **ใบรับรอง HTTPS** เลือก certificate/private key ที่เตรียมไว้ หรือให้สร้าง self-signed certificate ที่ตรงกับ Domain/IP
5. **ฐานข้อมูล** เลือกก่อนกรอกข้อมูล:
   - **มี Database และ User แล้ว**: ระบุ host, port, database, username และ password ระบบตรวจการเชื่อมต่อและสิทธิ์ก่อนใช้ ไม่เปลี่ยนรหัส User ใน PostgreSQL
   - **ยังไม่มี**: ระบุชื่อ Database/User ใหม่และ password ระบบติดตั้ง PostgreSQL บนเครื่องนี้และสร้างให้ หากเว้น password ว่างจะสุ่มให้ หากกรอกเองต้องยาวอย่างน้อย 12 ตัวและยืนยันอีกครั้ง ไม่เขียนทับชื่อ Database/User ที่มีอยู่
6. ตรวจสรุป URL และ DB แล้วกดยืนยัน Password ใช้ hidden prompt และไม่แสดงในสรุป

Portal เปิด HTTPS เองโดยตรง (Uvicorn) และเสิร์ฟหน้าเว็บ, API และ Console WebSocket ผ่าน port เดียวกัน ไม่ต้องติดตั้งหรือผูกกับ Nginx

DB ที่เตรียมไว้ต้องว่างหรือเป็น DB ของ VM Portal และ User ต้องมีสิทธิ์สร้าง/แก้ไขตารางของ Portal ใน schema `public` กรณี DB ภายนอกจะเชื่อมต่อด้วย TLS (`sslmode=require`) ต้องมี PostgreSQL client ที่รองรับเวอร์ชัน Server สำหรับ `pg_dump` ด้วย

ระบบเปิดเว็บด้วย HTTPS เท่านั้น ไม่สร้าง HTTP endpoint ของ Portal ตัว API เปิดรับ HTTPS โดยตรง (IPv4) ส่วน Redis รับเฉพาะ loopback หากมี firewall หรือ security group ให้เปิด TCP port HTTPS ที่เลือก ตัวติดตั้งไม่แก้ firewall rule ของเครื่อง

Self-signed ใช้เข้ารหัส HTTPS ได้ แต่ browser จะยังแจ้งว่าไม่เชื่อถือ ให้ใช้ใบรับรององค์กร/โดเมนเมื่อพร้อม; รันตัวติดตั้งซ้ำเพื่อเลือก certificate ใหม่ได้ ตัวติดตั้งตรวจวันหมดอายุ ชื่อ Domain/IP และตรวจว่า private key ตรงกับ certificate

## หลังติดตั้ง

ตัวติดตั้งรัน migration, เริ่มบริการ และตรวจ `/api/health` ผ่าน HTTPS ก่อนแสดง URL พร้อมใช้งาน บริการเริ่มอัตโนมัติหลังรีบูต:

```bash
sudo systemctl status vmportal-api vmportal-worker vmportal-beat vmportal-redis
sudo journalctl -u vmportal-api -u vmportal-worker -n 100 --no-pager
```

API รันด้วย service user `vmportal` พร้อม certificate/key มีการบีบอัดไฟล์หน้าเว็บ, cache ไฟล์ที่ไม่เปลี่ยน, security headers และจำกัด body 128 KiB

เปิด URL ที่แสดง สร้าง Admin ครั้งแรกด้วย setup code:

```bash
sudo cat /etc/vmportal/bootstrap-token
```

จากนั้นตั้ง Proxmox, ตรวจการเชื่อมต่อ และเปิดการใช้งาน VM ที่หน้า Setup ตาม [คู่มือ Setup](SETUP.md) ถ้าใช้ DB Portal เดิม บัญชีและการตั้งค่าเดิมยังอยู่

ตำแหน่งสำคัญ:

| รายการ | ตำแหน่ง |
|---|---|
| Application ที่ใช้งาน | `<path>/current` |
| แต่ละรุ่นที่ build | `<path>/releases/<timestamp>` |
| ไฟล์หน้าเว็บที่เปิดให้ผู้ใช้ | `<path>/www` |
| Environment และ secrets | `/etc/vmportal/portal.env` (root:vmportal, 0640) |
| ค่าตัวติดตั้ง | `/etc/vmportal/install.json` |
| Certificate และ private key | `/etc/vmportal/tls/` |
| ข้อมูล Redis/Beat | `/var/lib/vmportal/` |
| Backup | `/var/backups/vmportal/<timestamp>/` |

## รันซ้ำเพื่อเปลี่ยนค่า หรืออัปเดตโค้ด

รัน `sudo bash setup-server.sh` จาก repository ที่อัปเดตแล้ว หรือรันจาก installation:

```bash
sudo bash /opt/vmportal/current/setup-server.sh
```

เมื่อพบการติดตั้งเดิม ตัวติดตั้งจะถามก่อนว่าจะทำอะไร:

1. **Change settings only** (ค่าเริ่มต้น): ใช้โค้ดรุ่นที่ติดตั้งอยู่ ไม่ build ใหม่ เหมาะกับการเปลี่ยน port, hostname, certificate หรือ DB (ถ้าเปลี่ยน URL path ระบบจะ build หน้าเว็บใหม่ให้) ถ้าไม่ได้เปลี่ยนอะไรเลย ตัวติดตั้งจะจบโดยไม่แตะระบบ
2. **Update the application**: build รุ่นใหม่จากโฟลเดอร์ที่รัน แล้วให้ตรวจค่าทั้งหมดอีกครั้ง

ทุกคำถามขึ้นค่าเดิมให้ กด Enter เพื่อคงค่าเดิม ก่อนลงมือ ตัวติดตั้งจะแสดงรายการสิ่งที่เปลี่ยนพร้อมผลกระทบ (WARNING) และถ้ามีการเปลี่ยนที่กระทบผู้ใช้ ค่าเริ่มต้นของการยืนยันจะเป็น No:

| สิ่งที่เปลี่ยน | ผลกระทบที่ตัวติดตั้งเตือน |
|---|---|
| URL path / HTTPS port / Hostname | ผู้ใช้ต้องเปิด URL ใหม่ ลิงก์เดิมใช้ไม่ได้ ต้องเปิด port ใหม่ใน firewall, certificate ต้องครอบคลุม hostname ใหม่ และถ้าเปลี่ยน URL path ระบบจะ build หน้าเว็บใหม่ให้ |
| Certificate | Browser เห็นใบรับรองใหม่ ถ้าเป็น self-signed ผู้ใช้ต้องกดยอมรับใหม่ |
| Database | Portal จะแสดงข้อมูลของ DB ใหม่ ไม่ย้ายข้อมูลจาก DB เดิม และทุกคนต้อง Login ใหม่ |
| ติดตั้งเดิมใช้ Nginx | หยุดและลบ `vmportal-web.service` ของ Portal แล้วให้ Portal เปิด HTTPS เอง แพ็กเกจ Nginx ยังอยู่สำหรับเว็บอื่น |
| Update application | รัน migration และรีสตาร์ทบริการ (หยุดให้บริการประมาณหนึ่งนาที) |

ถ้าขั้นใดล้มเหลว ตัวติดตั้งจะคืน config และบริการเดิม (รวม Nginx ของการติดตั้งเก่า) ให้อัตโนมัติ เมื่อถาม **Change the database connection? [y/N]**:

- กด Enter / ตอบ `n`: เก็บการเชื่อมต่อ DB เดิม ไม่ถาม user/password DB ซ้ำ
- ตอบ `y`: เลือกใช้ DB ที่มีอยู่หรือสร้าง DB/User ใหม่ แล้วกรอกการเชื่อมต่อใหม่

การเลือก DB ใหม่คือให้ระบบใช้ข้อมูลใน DB ปลายทาง ไม่ย้ายหรือรวมข้อมูลจาก DB เดิมให้เอง หาก DB ปลายทางมีข้อมูลเข้ารหัสอยู่และใช้ Master Key ต่างกัน ตัวติดตั้งจะถาม `ENCRYPTION_KEY` เดิมของ DB นั้นและตรวจให้ตรงก่อนติดตั้ง

การเปลี่ยนเฉพาะ URL path/port/certificate เก็บ JWT secret และ Master Key เดิม การเปลี่ยนการเชื่อมต่อ DB จะเปลี่ยน JWT secret ให้ Login ใหม่ และแยก Redis state เพื่อไม่ให้งานจาก DB เดิมไหลไปยัง DB ใหม่

หาก DB เดิมติดต่อไม่ได้และเลือกเปลี่ยนไป DB ใหม่ ตัวติดตั้งจะขอให้ยืนยันแยก เพราะไม่สามารถตรวจงานหรือสำรอง DB เดิมได้ ค่าเริ่มต้นคือยกเลิก หากยืนยัน จะยังตรวจและสำรอง DB ปลายทางตามปกติ

ก่อนสลับบริการต้องไม่มีงาน VM `queued`/`running` หากมี ตัวติดตั้งจะแจ้งให้รอแล้วรันใหม่ โดย build release ใหม่แยกจากรุ่นที่ใช้งานก่อนหยุดบริการ สำรอง config และ DB เดิมก่อน migration (`pg_dump --format=custom`) รวมถึงสำรอง DB ปลายทางถ้าเปลี่ยน DB

หากเปิดบริการรุ่นใหม่ไม่สำเร็จ จะคืน config/unit และเริ่มบริการรุ่นเดิม พร้อมเก็บ backup สำหรับกู้ข้อมูล การคืน config ไม่ downgrade schema หรือ restore DB อัตโนมัติ; backup อยู่ในตำแหน่งที่แจ้ง การรันครั้งแรกที่ล้มเหลวหลังเริ่ม migration จะเก็บคีย์และค่าที่กรอกไว้สำหรับรันซ้ำ หากสร้าง DB/User สำเร็จแต่ยังไม่ถึงขั้นบันทึกค่า ให้เลือกว่า DB มีอยู่แล้วในการรันครั้งถัดไป

ตัวติดตั้งนี้จัดการ **system services** ของตัวเองผ่าน `/etc/vmportal/install.json` การติดตั้งแบบ user services รุ่นเดิมใน `~/.config/vmportal` ยังใช้ได้ แต่ต้องวางแผนย้าย config/DB แยก ไม่ใช้ตัวติดตั้งนี้ทับการติดตั้งคนละแบบ

## รีเซ็ตรหัส Admin บน Server ที่ติดตั้ง

```bash
sudo /opt/vmportal/current/.venv/bin/python /opt/vmportal/current/scripts/reset_admin_password.py --env-file /etc/vmportal/portal.env
```

โปรแกรมติดตั้งไว้ที่ `/opt/vmportal` เสมอ สคริปต์ถามรหัสใหม่และยืนยันแบบ hidden prompt
