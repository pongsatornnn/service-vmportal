# เปลี่ยนและกู้คืนรหัสผ่าน

## 1. ผู้ใช้เปลี่ยนรหัส Portal

Login → เมนู **รหัสผ่าน Portal** → กรอกรหัสปัจจุบัน, รหัสใหม่ และยืนยันรหัสใหม่ ระบบบันทึก Argon2 hash และเพิ่ม auth_version เพื่อยกเลิก JWT เดิมทุกอุปกรณ์ ต้อง Login ใหม่ รหัส VM ไม่เปลี่ยน Console session เดิมตรวจเวอร์ชันซ้ำทุก 5 วินาทีและจะปิดเมื่อเวอร์ชันไม่ตรง

รหัสใหม่ยาว 12–128 ตัวอักษร ต้องมี A–Z, a–z, ตัวเลข และอักขระพิเศษตาม checklist และการเปลี่ยนรหัสปกติต้องใช้รหัสต่างจากปัจจุบัน ไม่มีการเก็บ plaintext หรือส่งรหัสใน Audit Logs

## 2. ลืมรหัส Portal โดยไม่ใช้อีเมล

1. เจ้าของบัญชีติดต่อ Admin เพื่อยืนยันตัวตนผ่านช่องทางที่องค์กรใช้อยู่
2. Admin → **ผู้ใช้ / Accounts** → เลือกบัญชี approved → **ออกโค้ดกู้คืน Portal**
3. Admin กรอกรหัส Portal ของตนเองเพื่อยืนยัน ระบบแสดงโค้ดเพียงครั้งนี้ มีอายุ 15 นาที ส่งให้เจ้าของผ่านช่องทางส่วนตัว
4. เจ้าของเปิดหน้า Login → **ลืมรหัส Portal / ใช้โค้ดจาก Admin** → กรอกโค้ดและตั้งรหัสใหม่ แล้ว Login ตามปกติ

โค้ดสุ่ม 256 บิต เก็บเฉพาะ SHA-256 digest ใน DB, ใช้ได้ครั้งเดียว มี expiry และล็อก transaction ป้องกันใช้ซ้ำพร้อมกัน การออกโค้ดใหม่/เปลี่ยนรหัสจะเพิกถอนโค้ดเก่า หลังใช้โค้ดสำเร็จ JWT เดิมทั้งหมดถูกเพิกถอน ไม่มี temporary password ที่ใช้ Login ได้ และไม่มีการส่งข้อความ/อีเมลอัตโนมัติ API มี rate limiting และ no-store responses

ถ้า Admin ทุกคนเข้าไม่ได้ ผู้ดูแล Ubuntu Portal Server ใช้ offline operator CLI ผ่าน wrapper ที่อ่าน ENV ของ native service โดยไม่แสดง secrets:

```bash
sudo /opt/vmportal/current/.venv/bin/python /opt/vmportal/current/scripts/portal_cli.py reset-password <username>
```

CLI ถามรหัสใหม่ผ่าน hidden prompt และยืนยันอีกครั้ง ไม่ใส่รหัสใน command line/history ใช้ DATABASE_URL/JWT_SECRET/ENCRYPTION_KEY จาก service environment เดิม ไม่สร้างบัญชี Administrator ใหม่ให้เอง บันทึก operator audit และเพิกถอน Session/โค้ดเดิม งานนี้เปลี่ยนเฉพาะบัญชี Portal ไม่ติดต่อ Proxmox

### สคริปต์รีเซ็ตรหัส Admin แบบถามรหัสใหม่ทันที

รันบนเครื่อง Portal ด้วย environment ของบริการเดิม:

```bash
sudo /opt/vmportal/current/.venv/bin/python /opt/vmportal/current/scripts/reset_admin_password.py
```

หากมี Admin ที่ใช้งานอยู่บัญชีเดียว สคริปต์แสดงชื่อแล้วถาม `New password:` และ `Confirm new password:` โดยไม่แสดงตัวอักษร รหัสต้องผ่านกฎเดียวกับเว็บ หากไม่ตรงกันหรือไม่ผ่านกฎจะให้กรอกใหม่ กด Ctrl+C เพื่อยกเลิกก่อนบันทึกได้

หากมี Admin หลายบัญชี จะถามชื่อบัญชีก่อน หรือระบุด้วย `--username admin` ได้ สคริปต์รับเฉพาะบัญชี Admin สถานะ approved เท่านั้น ไม่สร้างบัญชีใหม่หรือเปิดใช้บัญชีที่ถูกลบ/ระงับ บันทึก Argon2 hash, Audit และเพิกถอน Session/โค้ดกู้คืนเดิมของบัญชีนั้น

โดยปกติอ่านค่า `/etc/vmportal/portal.env` ของเครื่องที่ติดตั้งด้วย `setup-server.sh` (จึงต้องรันด้วย sudo) และ `.env` ของโปรเจกต์เมื่อไม่พบไฟล์บริการ หากใช้ตำแหน่งอื่นให้ระบุ `--env-file /path/to/portal.env` ไม่ต้องใส่รหัสผ่านในคำสั่ง

## 3. ขอรีเซ็ตรหัสภายใน VM

หน้า VM → **ขอรีเซ็ตรหัส VM** → ตั้งรหัสใหม่พร้อมยืนยันและเหตุผล → รอ Admin อนุมัติที่รายการ **คำขอรีเซ็ตรหัส VM** ผู้ใช้ยกเลิกคำขอ pending ได้ Admin สามารถส่งคำขอแทนเจ้าของ แต่ต้องอนุมัติก่อนทำงานเช่นกัน

Backend ใช้ guest_username ที่บันทึกตอนสร้าง VM เท่านั้น ไม่มีช่องเปลี่ยนบัญชีเป้าหมายหรือเลือก root/system accounts รหัสใหม่เก็บเข้ารหัสด้วย Master Key จนใช้ จากนั้นลบทิ้งเมื่อสำเร็จ/ปฏิเสธ/ยกเลิก/ล้มเหลว ไม่คืนค่าใน API และไม่ลง Queue หรือ Audit

Admin อนุมัติได้เมื่อ:

- VM เป็น ready และตรง execution mode, owner approved และไม่มีงานอื่น queued/running
- VM identity ตรงกับ record และไม่เป็น Template/locked
- VM running, Guest Agent ติดตั้ง/เปิดและรองรับ guest-set-user-password
- Service User และ API Token มี `VM.GuestAgent.Unrestricted` บน `/vms/<VMID>` หรือสืบทอดจาก `/pool/Portal-Service` และมีสิทธิ์อ่าน Agent ตามเดิม

**VM.GuestAgent.Unrestricted เป็นสิทธิ์กว้างภายใน Guest รวมการรันคำสั่งและเข้าถึงไฟล์** ให้ Admin พิจารณาขอบเขต VM/Pool ก่อนเพิ่ม Role ให้ทั้ง User/Token ตาม Privilege Separation Portal ไม่เพิ่มสิทธิ์นี้เองและไม่ต้องให้ Administrator หากยังไม่มีสิทธิ์จะเก็บคำขอ pending และแจ้ง privilege/path ที่ขาด

เมื่ออนุมัติ Celery ใช้ `POST /nodes/<node>/qemu/<vmid>/agent/set-user-password` เฉพาะ username ที่บันทึกไว้ ไม่แก้ Cloud-Init credentials ของเครื่องเดิม ไม่ restart VM และไม่รัน shell command ทั่วไป Worker ตรวจ readiness/privilege/agent ซ้ำก่อนส่ง หากผลไม่แน่นอนให้ needs_review, purge credential และไม่ retry อัตโนมัติ รหัสอาจเปลี่ยนแล้วแม้ Backend ไม่ได้รับผลตอบกลับ ต้องตรวจสอบก่อนส่งคำขอใหม่

อ้างอิง API และสิทธิ์: [Proxmox QEMU Agent API source](https://github.com/proxmox/qemu-server/blob/master/src/PVE/API2/Qemu/Agent.pm)

## ยืนยันการลบ VM

Admin ต้องพิมพ์ชื่อ VM ให้ตรงทั้งตอนอนุมัติลบครั้งแรกและตอน retry ลบ Backend ตรวจซ้ำและปฏิเสธเมื่อชื่อไม่ตรง/ไม่ส่งชื่อ คำขอ reject ไม่ต้องพิมพ์ชื่อ ระบบยังต้องตรวจ stopped และไม่ force stop
