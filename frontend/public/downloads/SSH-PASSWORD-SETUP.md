# ให้ผู้ใช้เลือก VM Username/Password และเปิด SSH Password Login

หน้า Requests รองรับ VM Username (ค่าเริ่มต้น `ubuntu`), Password และตัวเลือก **เปิด SSH Password Login สำหรับ VM นี้** แยกจากบัญชี Portal ยังต้องผ่าน Admin อนุมัติ VM ทุกครั้ง

ระบบส่ง Username/Password ผ่าน `ciuser`/`cipassword` และใช้ **vendor snippet** ที่ Admin ติดตั้งไว้สำหรับ `ssh_pwauth: true`, `disable_root: true` และ `PermitRootLogin no` โดยผูก `cicustom=vendor=...` เฉพาะ VM ใหม่ ไม่แก้ Template ไม่เปลี่ยน SSH ของ Proxmox หรือ VM เดิม

## สิ่งที่ทำเสร็จใน Portal

- รับ Username 3–32 ตัวอักษร (`a-z` ขึ้นต้น ตามด้วย `a-z`, `0-9`, `_`, `-`), แปลงเป็นตัวพิมพ์เล็ก และไม่อนุญาต root/บัญชีระบบ
- Password 12–128 ตัวอักษร เก็บแบบเข้ารหัสและไม่แสดงย้อนหลัง
- คำขอ SSH Password ถูกบล็อกก่อนบันทึก/อนุมัติใน real mode ถ้า Admin ยังไม่กำหนด snippet
- ตรวจ Template, สถานะ Storage ที่รองรับ snippets ก่อน Clone
- Configure VM ใหม่ด้วย ciuser/cipassword/cicustom แล้วอ่าน config ยืนยัน Username และ Vendor Reference ก่อน Start
- เมื่อ Configure สำเร็จลบสำเนา Password ของ Portal ตามเดิม; Error จะหยุดที่ needs_review ไม่มีการลบ VM
- คำขอเดิม migrate เป็น guest user `ubuntu` และไม่ร้องขอเปิด SSH Password เพิ่ม ไม่มีการแก้ VM เดิมย้อนหลัง

## ขั้นตอน Admin ครั้งเดียวบน Proxmox Node3

ไฟล์ที่เตรียมไว้:

- [Installer สำหรับ Proxmox](../scripts/install-proxmox-ssh-policy.sh)
- [นโยบาย Cloud-Init ที่ไม่มีรหัสผ่านหรือ Secret](../infra/cloud-init/portal-ssh-password.yaml)

ดาวน์โหลดได้จากหน้า Admin Setup หรือ URL `/downloads/install-proxmox-ssh-policy.sh` และ `/downloads/portal-ssh-password.yaml` ของ Portal

1. อ่าน Script ก่อน แล้วคัดลอกไป Node3 ตัวอย่างคำสั่งนี้ให้ Admin รันเองบน Portal Server (จะถาม SSH credentials ของ Proxmox ตามปกติ ไม่ใส่รหัสลงในคำสั่ง):

   ```bash
   scp install-proxmox-ssh-policy.sh root@<proxmox-host>:/root/
   ```

2. เปิด **Proxmox → Node3 → Shell** แล้วรัน:

   ```bash
   bash /root/install-proxmox-ssh-policy.sh
   ```

   Script สร้าง Directory Storage `portal-snippets` รองรับเฉพาะ `snippets` ที่ `/var/lib/vz/portal-snippets` และวางไฟล์นโยบายใน subdirectory `snippets/` โดยจำกัด Storage ให้อยู่ Node ที่รัน Script หากพบ Storage/ไฟล์เดิมที่ต่างจากที่กำหนดจะหยุดให้ตรวจเอง ไม่มีการทับไฟล์ต่างเนื้อหา ไม่มีการสร้าง VM/แก้ Template/แก้ ACL

3. ผู้ดูแลตรวจสิทธิ์ของ Service User และ API Token (ถ้า privilege separation เปิด ทั้งสองฝั่งต้องมีสิทธิ์ที่มีผล):

   | ใช้ทำอะไร | Privilege / Path |
   | --- | --- |
   | ใช้/ตรวจ snippet | `Datastore.AllocateSpace` ที่ `/storage/portal-snippets` |
   | ตั้ง ciuser/cipassword/cicustom | `VM.Config.Cloudinit` บน VM ใน `/pool/Portal-Service` |
   | อ่าน config ยืนยันก่อน Start | `VM.Audit` บน VM ใน `/pool/Portal-Service` |

   ใช้ Role เฉพาะสิทธิ์ที่ขาด ไม่เพิ่ม Administrator ไม่จำเป็นต้องให้สิทธิ์ Storage อื่น เช่น `local` เพื่อฟีเจอร์นี้ การตรวจเบื้องต้นพบว่า Token ปัจจุบันเรียกอ่าน `/nodes/Node3/storage/local/content` ได้ HTTP 403 จึงแยก Storage เฉพาะสำหรับ snippet แทนการขอสิทธิ์กว้างบน local

4. กลับหน้า **Portal → Setup** กรอก **SSH password vendor snippet**:

   ```text
   portal-snippets:snippets/portal-ssh-password.yaml
   ```

5. กด **บันทึก → ตรวจ Read-only/TLS → เปิดใช้งาน** ผลตรวจจะรวมสถานะ/การเข้าถึง Storage ที่รองรับ snippets การบันทึก Setup จะพัก Execution และล้างผลตรวจเดิมตามปกติ

จากนั้น User เลือก Username/Password และติ๊กเปิด SSH Password Login ได้ เมื่อ Admin อนุมัติ Worker จึงสร้าง VM จริง หากยังไม่ได้เตรียม snippet ผู้ใช้ยังขอ Password สำหรับ Console ตาม Template policy ได้โดยปิดตัวเลือก SSH Password Login

## ตัวอย่างผลที่ต้องการ

```text
VM username: developer01
Authentication: Password
SSH Password Login: เปิด
```

หลัง VM บูตและ Cloud-Init เสร็จ:

```bash
ssh developer01@<VM-IP>
```

ใช้ Password ที่ตั้งในคำขอ ไม่ใช้ Password ของ Portal

## ขอบเขตการตรวจและ Acceptance

Read-only Setup ตรวจได้ว่า Storage อ่านได้ เปิดใช้งานและรองรับ snippets ส่วนก่อน Start จะตรวจ `ciuser` และ `cicustom` ที่ผูกไว้ แล้วสั่ง regenerate Cloud-Init ของ VM ใหม่เพื่อให้ Proxmox อ่านไฟล์จริงก่อน Start **Proxmox dump API รองรับ user/network/meta ไม่รองรับการอ่าน vendor file ผ่าน endpoint นี้** จึงไม่อ้างว่าตรวจเนื้อหา vendor หรือ Guest SSH จริงจาก API ได้ Admin ต้องติดตั้งไฟล์ที่เตรียมไว้และไม่เปลี่ยนเนื้อหาเองภายหลัง

เมื่อพร้อม ให้ Admin อนุญาตการทดสอบ VM จริงหนึ่งเครื่อง ตรวจ Cloud-Init, DHCP/IP, login ด้วย Username/Password ที่เลือก และยืนยันว่า Root SSH ถูกปิด Template ที่มี custom user/vendor/meta/network config ซึ่งขัดกับนโยบายนี้จะถูกบล็อกก่อน Clone เพื่อไม่ทับการตั้งค่าเดิมโดยไม่ตั้งใจ

Template ที่ harden sshd ด้วย Match/AllowUsers หรือ config ที่ override ก่อน Include อาจต้องปรับ policy ภายใน Guest ให้สอดคล้อง การทดสอบอัตโนมัติใช้ Mock ไม่ใช่หลักฐานว่า Guest SSH ของ Template 9000 ผ่าน acceptance แล้ว

## อ้างอิง Primary Sources

- [Proxmox Cloud-Init และ vendor snippets](https://github.com/proxmox/pve-docs/blob/master/qm-cloud-init.adoc)
- [Storage content permissions](https://github.com/proxmox/pve-storage/blob/master/src/PVE/API2/Storage/Content.pm)
- [Snippet access requires Datastore.AllocateSpace](https://github.com/proxmox/pve-storage/blob/master/src/PVE/Storage.pm)
- [Cloud-Init dump API types และ VM.Audit](https://github.com/proxmox/qemu-server/blob/master/src/PVE/API2/Qemu.pm)
- [Cloud-Init vendor-data merge](https://docs.cloud-init.io/en/latest/explanation/vendordata.html)

Storage listing บางเวอร์ชันกรองไฟล์ snippets จนต้องใช้ Datastore.Allocate จึงไม่ขอสิทธิ์นี้เพื่อ list ไฟล์ ระบบใช้ Storage status และการ regenerate Cloud-Init ของ VM ใหม่เพื่อตรวจว่ามีไฟล์ที่อ่านได้ก่อน Start แทน หากไฟล์หายหรืออ่านไม่ได้หลัง Clone จะหยุดที่ needs_review และไม่ Start/ลบ VM อัตโนมัติ
