# ใช้งานครั้งแรกและดูแลระบบ

คู่มือนี้สำหรับเครื่องที่ติดตั้งด้วย `sudo bash setup-server.sh` (ดู [คู่มือตัวติดตั้ง](SERVER-INSTALLER.md)) Portal รันเป็น systemd services ของระบบ เริ่มพร้อมเครื่อง และเปิด HTTPS เองโดยไม่ต้องใช้ Nginx

| รายการ | ตำแหน่ง |
|---|---|
| URL | ตามที่ตอบตอนติดตั้ง เช่น `https://portal.example:443/vmportal/` |
| โปรแกรมที่ใช้งาน | โฟลเดอร์ที่ clone ไว้ เช่น `~/service-vmportal` |
| ไฟล์หน้าเว็บที่เปิดให้ผู้ใช้ | `/var/lib/vmportal/www` |
| Environment, secrets, TLS | `/etc/vmportal/` |
| Redis/Beat state | `/var/lib/vmportal/` |
| Backup ก่อนติดตั้ง/อัปเดต | `/var/backups/vmportal/` |

## ใช้งานครั้งแรก

1. เปิด URL ที่ตัวติดตั้งแสดง ถ้าเลือก self-signed browser จะเตือน ให้ตรวจ fingerprint หรือเปลี่ยนเป็นใบรับรององค์กรก่อนใช้งานจริง (รันตัวติดตั้งซ้ำเพื่อเปลี่ยน)
2. อ่านรหัสติดตั้งบนเครื่อง Portal:

   ```bash
   sudo cat /etc/vmportal/bootstrap-token
   ```

3. กรอกรหัสที่หน้า Setup พร้อม Username/Password ของ Admin (อย่างน้อย 12 ตัวอักษร) รหัสนี้สร้าง Admin ได้ครั้งเดียว Admin คนนี้เป็น **ผู้ดูแลหลัก**
4. Login แล้วไปที่ **ตั้งค่า → Proxmox**: กรอก API Endpoint, Token ID/Secret, CA PEM แล้วเลือก Node, Storage, Pool และเครือข่าย
5. กด **บันทึกและตรวจสอบ** (ตรวจแบบอ่านอย่างเดียว ไม่ Clone VM) เมื่อผ่านแล้วกด **เปิดใช้งาน**
6. ไปที่ **ตั้งค่า → Template**: กด **+ เพิ่ม Template** ตั้งชื่อที่ผู้ใช้เห็น (เช่น Ubuntu 24.04) เลือก VMID ระบบดึง Boot disk และขนาด Disk ให้ → **ตรวจสอบ** → **เปิดให้ขอ** วิธีเตรียม Template บน Proxmox ดูในเว็บที่ คู่มือผู้ดูแลระบบ หัวข้อ 3–4
7. ทดลองขอ VM หนึ่งเครื่องและอนุมัติ ก่อนเปิดให้ผู้ใช้ทั่วไป

ถ้าต้องการลอง Workflow โดยไม่เชื่อม Proxmox ให้เลือก Mock ก่อนเริ่มใช้ DB นั้น การเปลี่ยน Cluster/Mode เมื่อมี VM records แล้วจะถูกบล็อก ควรแยก DB สำหรับ Mock และ Production

## Secrets และ Security

- API Token Secret รับจาก Admin ผ่าน HTTPS เท่านั้น เก็บใน PostgreSQL แบบ Fernet authenticated encryption ไม่ส่งค่ากลับใน Response/Audit Log
- Master Key `ENCRYPTION_KEY` อยู่ใน `/etc/vmportal/portal.env` (root:กลุ่มของบัญชีที่ติดตั้ง, 0640) ต้องสำรองพร้อม Database การสร้าง Master Key ใหม่จะทำให้ถอด Secret เดิมไม่ได้
- CA ของ Proxmox เก็บใน DB ระบบตรวจ CA และ Hostname เสมอ ไม่มีตัวเลือกข้าม TLS verification
- บันทึกการเชื่อมต่อใหม่จะพักการสั่งงานและทำให้ทุก Template ต้องตรวจสอบใหม่
- Infrastructure identity (Cluster/Node/Pool/Storage) ถูกล็อกเมื่อมี VM แล้ว

## จัดการ Service

```bash
sudo systemctl status vmportal-api vmportal-worker vmportal-beat vmportal-redis
sudo systemctl restart vmportal-api vmportal-worker vmportal-beat
sudo journalctl -u vmportal-api -u vmportal-worker -f
```

## อัปเดตหรือเปลี่ยนค่า

รันตัวติดตั้งซ้ำจาก repository ที่อัปเดตแล้ว เลือก **Change settings only** เพื่อเปลี่ยน URL path, port, hostname, certificate หรือ DB หรือ **Update the application** เพื่อติดตั้งรุ่นใหม่ ตัวติดตั้งแสดงผลกระทบของทุกค่าที่เปลี่ยนก่อนลงมือ สำรอง DB ให้อัตโนมัติ และคืนค่าเดิมถ้าล้มเหลว

```bash
cd ~/service-vmportal
git pull
sudo bash setup-server.sh
```

## Health / Backup

```bash
curl -k https://127.0.0.1:<port><url-path>/api/health
```

สำรอง PostgreSQL (ตัวติดตั้งทำให้ทุกครั้งที่รัน ที่ `/var/backups/vmportal/`), ไฟล์ `/etc/vmportal/portal.env` (มี Master Key) และ TLS key ใน `/etc/vmportal/tls/`

## บัญชีผู้ใช้

ใช้ **Username + Password** เท่านั้น เช่น `admin` หรือ `user01` ไม่ต้องมีอีเมลจริง ไม่มีระบบส่งอีเมล/ยืนยันอีเมล/Password Reset ผ่านอีเมลในเวอร์ชันนี้ ฟีเจอร์อีเมลเลื่อนไปพัฒนาภายหลัง

Username ใช้ 3–32 ตัวอักษร เริ่มด้วย a–z หรือ 0–9 ตามด้วย a–z, 0–9, `_`, `.`, `-` ระบบ trim ช่องว่างหัวท้ายและแปลงเป็นตัวพิมพ์เล็กเพื่อป้องกันบัญชีซ้ำ

Migration `0003` เปลี่ยน Login identifier เป็น Username โดยรักษา user ID, Password Hash, Role, Approval และ Ownership เดิม หากมีบัญชีจากเวอร์ชันก่อนจะใช้ส่วนหน้าของอีเมลเป็น Username และเติม ID เมื่อชนกัน การ rollback schema ไม่สามารถกู้ Email address เดิมได้ ต้องใช้ Database backup หากต้องการข้อมูลเดิม

## รหัสสำหรับเข้า VM

ในหน้า Requests เลือก **วิธีเข้า VM → Password** แล้วตั้งและยืนยันรหัส 12–128 ตัวอักษร ชื่อผู้ใช้ภายใน VM ค่าเริ่มต้นเป็น `ubuntu` และเลือกชื่ออื่นได้ในช่อง VM username รหัสนี้เป็นคนละ credential กับบัญชี Portal ไม่ดึงรหัส Portal มาใช้โดยอัตโนมัติ ตัวเลือก SSH Public Key ยังใช้งานได้

Portal เข้ารหัสรหัส VM ด้วย Master Key ก่อนบันทึก รับค่าแบบ write-only และไม่แสดง Password/Ciphertext ใน API หรือ Audit เมื่อ Worker ยืนยัน Configure สำเร็จจะลบสำเนาที่เก็บใน Portal; การ Reject คำขอก็ลบสำเนาเช่นกัน ถ้า Provision ล้มเหลวก่อน Configure จะคง Ciphertext ไว้สำหรับตรวจสอบ ไม่มีการ Clone ซ้ำหรือลบ VM อัตโนมัติ

Password mode ส่ง `ciuser=<VM username ที่เลือก>`, `cipassword=<รหัสที่ตั้ง>` และล้าง `sshkeys` ใน config ของ VM ใหม่ ส่วน SSH Key mode ส่ง `sshkeys` และล้าง `cipassword` Template และ VM อื่นไม่ถูกแก้ไขโดยคำขอนี้

**Password สำหรับ Console กับการอนุญาต SSH Password Authentication เป็นคนละส่วน:** Proxmox ตั้งรหัสผ่าน Cloud-Init ได้ผ่าน `cipassword` แต่รหัสจะใช้กับ SSH ได้เมื่อ Cloud-Init/sshd ของ Template อนุญาตด้วย ไม่ได้ยืนยันว่า Template 9000 เปิดใช้งานไว้แล้ว

การเปิด SSH Password Login แบบต่อ VM ใช้ vendor snippet ที่ Admin เตรียมไว้ครั้งเดียว ดู [ขั้นตอนติดตั้งและสิทธิ์ที่ต้องใช้](SSH-PASSWORD-SETUP.md) Root SSH Login ถูกปิดในนโยบายนี้ ระบบไม่แก้ Template จริงอัตโนมัติ

Template ที่ใช้ custom Cloud-Init **user-data** จะถูกบล็อกใน Password mode เพราะ custom user-data อาจแทนที่รหัสที่ส่งผ่าน API ต้องให้ Admin ตรวจ Template ก่อน

อ้างอิง: [Proxmox Cloud-Init options](https://github.com/proxmox/pve-docs/blob/master/generated/qm-cloud-init-opts.adoc), [Proxmox Cloud-Init generator](https://github.com/proxmox/qemu-server/blob/master/src/PVE/QemuServer/Cloudinit.pm), [Cloud-Init password/SSH configuration](https://docs.cloud-init.io/en/latest/reference/modules.html#set-passwords)

Template ตั้งได้หลายตัวที่หน้า ตั้งค่า → Template แต่ละตัวต้องตรวจสอบผ่านก่อนเปิดให้ขอ คำขอที่อนุมัติแล้วใช้ Template ตอนอนุมัติเสมอ แม้ Admin จะแก้ภายหลัง ดูคู่มือในเว็บหัวข้อ 4
