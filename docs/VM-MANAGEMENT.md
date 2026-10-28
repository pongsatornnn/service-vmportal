# VM Management

ผู้ใช้เห็นและสั่งงานได้เฉพาะ VM ที่ Backend บันทึกว่าเป็นเจ้าของ Admin เห็นและจัดการ VM ของผู้ใช้ทุกคนใน Portal ได้ มีช่องค้นหาชื่อเครื่อง/VMID/Owner, งานและ Audit Logs และคำขอลบพร้อมเหตุผล VM นอก Portal ยังไม่ถูกนำเข้าหรือเปิดให้สั่งงาน

## IP และสถานะ

หน้า VM อ่าน Power/IP เมื่อเปิดรายการและเมื่อสถานะงานเปลี่ยน (อัตโนมัติสูงสุด 20 เครื่องต่อรอบ, ขนานไม่เกิน 3) หรือกดตรวจ IP/สถานะรายเครื่อง Backend อ่าน `status/current` และ `agent/network-get-interfaces` ไม่มีการเดา IP จากค่า DHCP และไม่ส่ง Token ให้ Browser

ต้องมี QEMU Guest Agent ติดตั้งและรันใน Guest และเปิดใน Proxmox VM Options เครื่องใหม่ Portal จะตั้ง `agent=1` ให้ แต่ไม่ได้ติดตั้ง package ภายใน Guest ให้เอง ควรใส่ `qemu-guest-agent` ใน Template:

```bash
# ภายใน Ubuntu Guest/เครื่องที่กำลังเตรียมเป็น Template
sudo apt update
sudo apt install -y qemu-guest-agent
```

บน Node3 ให้เปิด Guest Agent ใน Options ของ VM และอาจต้อง Shutdown/Start เพื่อเพิ่มอุปกรณ์ Guest Agent ก่อนใช้ อย่าสั่งปิดเครื่องที่ใช้งานอยู่โดยไม่วางแผน ตรวจใน Guest:

```bash
sudo systemctl start qemu-guest-agent
sudo systemctl status qemu-guest-agent
```

PVE 9 ต้องมี `VM.GuestAgent.Audit` บน `/vms/<vmid>` หรือสืบทอดจาก `/pool/Portal-Service` ทั้ง Service User และ Token ตาม Privilege Separation Agent ไม่ได้เพิ่ม ACL ให้อัตโนมัติ และไม่ต้องให้ Administrator

## Console / Shell

ใช้ noVNC ที่ bundle ภายในระบบ เปิดหน้าจอ Guest ผ่าน Backend WebSocket แล้ว Login ด้วยบัญชี Guest ของ VM เป็น Guest Console ไม่ใช่ Shell ของ Proxmox Node ต้องมี `VM.Console` บน VM/Pool; หาก Guest ใช้ serial console เท่านั้น ต้องเตรียมจอ Guest ให้เหมาะกับ VNC ก่อน

Browser ติดต่อเฉพาะ Portal ผ่าน HTTPS/WSS Backend เชื่อม Proxmox ด้วย CA เดิม Token Secret ไม่ออกไป Browser ระบบใช้ console ticket อายุ 30 วินาที ใช้ครั้งเดียว ตรวจ Origin และสิทธิ์เจ้าของซ้ำก่อนต่อ จำกัดหนึ่ง session ต่อบัญชีและครั้งละ 15 นาที Console ticket/password ชั่วคราวไม่ใช่ Proxmox API Token ไม่มีการเก็บ guest password หรือบันทึกเนื้อหา console

Console ใช้ WebSocket ผ่าน port HTTPS เดียวกับเว็บ Portal รองรับเองโดยไม่ต้องตั้ง Nginx

## Restart และลบ

Restart เรียก Proxmox `POST /nodes/<node>/qemu/<vmid>/status/reboot` ผ่าน Celery หลังตรวจ ownership, execution mode, readiness และไม่ให้มีงานซ้อน

ผู้ใช้ส่งคำขอลบพร้อมเหตุผล Admin อนุมัติ/ปฏิเสธ เมื่ออนุมัติจึงสร้างงาน Celery `delete` การอนุมัติและสร้างงานบันทึกใน transaction เดียว ก่อนลบ Worker ตรวจว่าอนุมัติจริง, VM name ตรงกับ record, ไม่ใช่ Template และ VM หยุดแล้ว จึงเรียก `DELETE /nodes/<node>/qemu/<vmid>` โดยไม่ force stop และไม่ลบ disk ที่ไม่เกี่ยวข้อง ไม่มีการลบเพราะ provisioning ล้มเหลว

Quota คืนหลัง Proxmox task ยืนยันสำเร็จ เก็บ record VM/คำขอ/Audit ต่อไว้ สถานะ deleted ไม่ถูกนำไปนับ usage ถ้าล้มเหลวหรือผลไม่แน่นอนให้ needs_review และไม่คืน quota/ไม่ retry delete อัตโนมัติ

การทดสอบ integration จริงครั้งนี้จำกัด read-only: VM 10000 running, provisioning/shutdown/start สำเร็จ IP ยังอ่านไม่ได้ (403 และ agent ยังไม่ได้เปิด) สิทธิ์ VM.Console และ VM.GuestAgent.Audit ยังไม่มี ไม่มีการทดลอง reboot/delete/console จริง


## งานลบค้างเพราะ VM ยังเปิดอยู่

ก่อน Admin อนุมัติ ระบบตรวจ VM identity/lock และ stopped ผ่าน Read-only API หาก VM ยังเปิดอยู่จะตอบ 409 และเก็บคำขอเป็น pending ให้ Shutdown ก่อนแล้วค่อยอนุมัติ Worker ตรวจซ้ำอีกครั้งก่อนส่ง DELETE

สำหรับงานเก่าที่ needs_review เพราะข้อความ `VM must be stopped before approved deletion; no force stop performed` และยังไม่ได้รับ UPID: Admin ใช้ปุ่ม **ตรวจและลองลบอีกครั้ง (Admin)** ในรายการคำขอลบ พิมพ์ hostname ให้ตรง ระบบตรวจ identity/lock/stopped และสร้าง Job ใหม่ เก็บ Job เดิมไว้ตรวจย้อนหลัง ไม่มี retry อัตโนมัติ ถ้าเป็น timeout, HTTP error หรือผลลบไม่แน่นอน endpoint นี้จะไม่ยอม retry ต้องให้ Admin reconcile ก่อน

## ทำงานต่อเมื่อ Clone สำเร็จแต่การอ่าน Task สะดุด

Backend ลองซ้ำเฉพาะ GET เมื่อเกิด transport error แบบจำกัดจำนวน ไม่ส่ง Clone/Configure/Start/Delete ซ้ำอัตโนมัติ ถ้าหยุดที่ `clone_accepted` ให้ Admin เปิด Activity แล้วเลือก **ตรวจและทำต่อจาก Clone เดิม (Admin)** พิมพ์ hostname ให้ตรง ระบบตรวจ original UPID เป็น qmclone ที่ stopped/OK, VM identity/lock, stopped และสิทธิ์/credentials เดิมก่อน requeue จาก `resume_after_clone` Worker ตรวจซ้ำและข้ามการจัด VMID/Clone จากนั้น Configure → Resize → Start ตาม flow เดิม ไม่อนุญาต resume อัตโนมัติหรือ resume checkpoint ที่ผลไม่แน่นอน
