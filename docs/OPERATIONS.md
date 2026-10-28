# Operations / Recovery

## Logs และ State

```bash
journalctl --user -u vmportal-api -f
journalctl --user -u vmportal-worker -f
journalctl --user -u vmportal-beat -f
```

Application logs เป็น JSON มี job_id/error_type หรือ method/path/status; Celery framework lifecycle logs อาจเป็นข้อความปกติ Audit log อยู่ PostgreSQL และแสดงให้ Admin เท่านั้น ไม่เก็บ Password, Token Secret หรือ SSH Key ใน Audit metadata

Job states: queued → running → succeeded หรือ needs_review; VM provisioning: queued → provisioning → ready หรือ needs_review งาน Power ไม่เปลี่ยน VM provisioning status ดู Job เพื่อทราบผลคำสั่ง

ปุ่ม **พักการทำงาน** ในหน้า Setup ปิดการเริ่มงานเขียนใหม่ทั้งหมด แต่ไม่ยกเลิกงานที่ Worker รับไปแล้ว หากต้องหยุดให้ pause Beat และรอ Worker จบด้วย graceful stop

## Job ค้าง / การกู้คืน

- queued: Beat จะส่งซ้ำอัตโนมัติทุก 10 วินาที ไม่ต้องสร้าง Job ใหม่ ตรวจ Redis/Beat/Execution gate
- running: อย่า reset เป็น queued เพราะอาจมี Clone หรือ Power คำสั่งที่สำเร็จแล้ว
- needs_review: ไม่มีการลบ VM, Clone ซ้ำ หรือคืน Quota อัตโนมัติ

ก่อนทำ Recovery ให้ Admin หยุด Beat และ **ยืนยันว่า Worker ที่ทำ Job นั้นหยุดแล้วจริง** แล้วตรวจ Job checkpoint/UPID, Proxmox Tasks และ VMID เทียบ hostname กับ Portal DB

หาก Worker ล่มและ Job ยัง running ให้บันทึกสถานะรอตรวจสอบ:

```bash
sudo /opt/vmportal/current/.venv/bin/python /opt/vmportal/current/scripts/portal_cli.py mark-interrupted JOB_ID
```

คำสั่งนี้เปลี่ยนเป็น needs_review พร้อม Audit เท่านั้น ไม่มี Proxmox mutation และไม่ Replay งาน การดำเนินการต่อ/การคืนทรัพยากรใน Phase 1 เป็น Manual DBA/Admin runbook หลังตรวจว่าทรัพยากรจริงเป็นของ request ที่ถูกต้อง เก็บหลักฐานและ Audit ก่อนเปลี่ยน DB ห้ามลบหรือแก้ VMID เพื่อหลีกเลี่ยง Quota

Retry ที่รองรับอัตโนมัติ: ส่ง queued outbox ใหม่เมื่อ broker มีปัญหา, ลอง VMID ถัดไปเมื่อ preflight ยืนยัน occupied. การ Timeout หลังส่ง Clone อาจสร้าง VM สำเร็จแล้ว จึงต้อง review เสมอ ไม่ใช้ generic autoretry สำหรับคำสั่งเขียน Proxmox

## Proxmox ACL — ตรวจ Least Privilege

ยังไม่ได้ตรวจ ACL ของ Token จริง รายการนี้เป็นจุดตรวจสำหรับผู้ดูแล ไม่ใช่ข้อยืนยันว่าต้องเพิ่มสิทธิ์ทั้งหมด ต้องตรวจ error จาก PVE 9 API/ACL จริงและระบุเฉพาะรายการที่ขาด ห้ามมอบ Administrator อัตโนมัติ

| Operation / API | Privilege และ Path ที่ต้องตรวจ |
| --- | --- |
| Full clone template 9000 | VM.Clone ที่ `/vms/9000` |
| Read template config | VM.Audit ที่ `/vms/9000` (อาจยังไม่มีจากสิทธิ์ที่แจ้ง) |
| Allocate into pool | VM.Allocate ที่ `/pool/Portal-Service`; `pool=Portal-Service` ส่งทุก Clone |
| Target disk storage | Datastore.AllocateSpace ที่ `/storage/local-lvm` |
| CPU/RAM/Network/Disk/Cloud-Init | VM.Config.CPU, Memory, Network, Disk, Cloudinit และ Options ตาม field ที่ใช้ บน VM ใน Pool |
| Power start/stop/shutdown | VM.PowerMgmt บน VM ใน `/pool/Portal-Service` (ยังไม่ได้ระบุว่ามี) |
| Read VM state/config | VM.Audit บน VM ใน Pool |
| Node status | Sys.Audit ที่ `/nodes/Node3` |
| Task status / cluster nextid | ตรวจ permission ของ endpoint สำหรับ Token ตาม PVE API viewer; อย่าเพิ่มสิทธิ์กว้างเพียงเพราะ preflight ล้มเหลว |

Token ที่เปิด privilege separation ต้องตรวจทั้ง ACL ของ User `vmportal@pve` และ ACL ของ Token ID จริง สิทธิ์ที่มีผลเป็นผลร่วมของทั้งสอง ฝั่ง Backend ไม่แก้ ACL

หากมี HTTP 403 ให้รายงาน `{method, endpoint, operation, required privilege, ACL path}` ตาม Error ใน Proxmox API/Task log โดยไม่เปิดเผย Secret ถ้า PVE ใช้ SDN/VNet ให้ตรวจสิทธิ์ network ตามทรัพยากรจริง ไม่ถือว่า Bridge VLAN48 เป็น SDN โดยอัตโนมัติ

## Template Acceptance

Admin ตรวจ Template 9000 แบบ Read-only ว่าเป็น Ubuntu Cloud-Init จริง, Boot Disk เป็น device ตาม `DISK_DEVICE`, Disk จริงไม่เกิน `TEMPLATE_DISK_GB`, มีการ์ดไม่เกินจำนวนขาที่เลือกใน Setup และไม่มี NIC อื่นเชื่อม Network นอกที่กำหนด, DHCP VLAN48 พร้อมใช้งาน, Template ไม่มี Secret และไม่ต้องใช้ Password ร่วมกัน

Worker กำหนด CPU/RAM, ciuser=ubuntu, SSH Public Key, DHCP และ bridge ฝั่ง Backend ก่อน Start; user hostname ถูกเติม request ID ป้องกันชื่อซ้ำ SSH Key ตรวจรูปแบบด้วย cryptography ไม่ยอมรับ arbitrary configuration

## Backups / Secrets

สำรอง PostgreSQL สม่ำเสมอ (รวม audit/jobs/allocator), ENV และ CA/Portal key ในที่จำกัดสิทธิ์ เก็บ Redis AOF เพื่อคิวและ limiter แต่ PostgreSQL Jobs เป็นแหล่งข้อมูลหลัก ไม่พึ่ง Redis result backend

หมุน JWT_SECRET ทำให้ Token เดิมใช้ไม่ได้; หมุน API Token Secret ในหน้า Setup แล้วตรวจ Read-only และเปิดใช้งานใหม่ API Token ไม่ถูกส่งไป Browser และไม่มี Frontend ENV ที่เปิดเผย Secret

## ข้อจำกัดที่ต้องทราบ

- ไม่มี Automatic Reconciliation, Delete VM, Quota Reclaim, Password Reset หรือ Refresh Token ใน Phase 1
- Power state/IP แบบสดและการจัดการ Migration ระหว่าง Node ไม่อยู่ใน Phase 1
- Audit table ใช้ credential ของแอป จึงยังไม่เป็น tamper-proof against a compromised DB administrator; ใช้ DB backup/central LAN logs หากต้องการ retention เพิ่ม
- Production acceptance ต้องทดสอบกับ Node3 และ Token จริงหลัง TLS ผ่านก่อนเปิด execution

การตั้งค่าและตำแหน่ง Service/Secrets ปัจจุบันดู [SETUP.md](SETUP.md) Master Key ต้องสำรองคู่ DB; การหมุน Key ต้อง re-encrypt ข้อมูลด้วย Key เดิมก่อน ไม่เปลี่ยนเป็นค่าใหม่ตรง ๆ

## ประวัติอายุ 7 วัน

Celery Beat เรียก `portal.purge_history` ทุกชั่วโมง ล้าง Activity ที่สำเร็จ, คำขอที่ปิดแล้ว, VM ที่ลบแล้ว และผู้ใช้ที่ลบแล้ว เมื่อครบ 7 วันนับจากจบ/ลบสำเร็จ (`retention_since`) รวมถึง Audit Log อายุเกิน 7 วันนับจากเหตุการณ์ งาน queued/running/needs_review และข้อมูลที่ยังอ้างอิงงานเหล่านี้จะไม่ถูกล้าง แต่ละรอบจำกัด 500 รายการต่อตารางและ 100 บัญชี จึงอาจใช้หลายรอบหากสะสมมาก

Migration 0012 เริ่มนับระยะผ่อนผัน 7 วันให้รายการปิดเก่าที่ไม่มีเวลาจบจริง ระบบล้างเฉพาะฐานข้อมูล Portal ไม่ส่งคำสั่งไป Proxmox เมื่อบัญชีลบสำเร็จ (`deleted`) Username เดิมสามารถสมัครใหม่ได้ทันทีโดยใช้ ID ใหม่ บัญชีที่ยังลบไม่เสร็จ (`deleting`) ยังสงวนชื่อไว้ ประวัติเดิมเชื่อมด้วย ID เก่า ประวัติอาจคงอยู่เกิน 7 วันถ้ามีรายการอื่นอ้างอิงอยู่ การเก็บไฟล์ Backup แยกจากนโยบายนี้และยังไม่ได้เปลี่ยน

## VM ถูกลบหรือเปลี่ยนจาก Proxmox ภายนอก Portal

ตรวจเมื่อผู้ใช้กดคำสั่ง, ขอลบ/รีเซ็ตรหัส, เปิด Console หรือกดอัปเดต IP/ตรวจสถานะเท่านั้น Worker ตรวจซ้ำก่อนส่งคำสั่งของงานที่ผู้ใช้ร้องขอ ไม่มี timer สำหรับตรวจ VM หาย GET รายการ VM และการอ่าน runtime ตามปกติไม่เปลี่ยนสถานะเป็น missing

- อ่าน config ตาม VMID/Node และตรวจชื่อ/template/lock ก่อนส่งคำสั่ง หากพบ VM ใน Node อื่นจะระงับคำสั่ง ให้ Admin ตรวจการย้าย ไม่ย้ายตามเอง
- ไม่ใช้รายการ `/cluster/resources` ที่ว่างเป็นหลักฐานว่าลบ เพราะผลถูกกรองด้วย VM.Audit ตรวจ `/cluster/nextid?vmid=...` ให้ตอบเลขเดิมแบบ integer ว่าว่างจริงสองครั้ง ร่วมกับสถานะ Cluster ทั้งสองรอบ (quorum, Node ทุกตัว online, สมาชิกไม่เปลี่ยน) และอ่าน Node ที่ตั้งค่าได้ พร้อมตรวจ Template ที่รู้จักว่ายังอ่านได้และ VMID ของ Template ยังถูกใช้งาน เพื่อป้องกันการสรุปจาก index ว่าง/ไม่ครบระหว่างเริ่มระบบ ทุกคำสั่งเป็น GET มีงบเวลาตรวจประมาณ15วินาที
- ถ้า403/timeout/responseผิดรูป/Nodeoffline/noquorum/ชื่อไม่ตรง/VMIDยังใช้/Taskเดิมยังไม่จบ/Cloneผลไม่แน่นอน จะไม่สรุปว่าลบ และไม่คืนโควตา
- หากยืนยันไม่พบ ให้ VM เป็น `missing` จำ workflow เดิมใน `presence_previous_status` ปิดคำสั่งและซ่อน IP/metrics เก่าจากหน้าปกติ แต่ยังจองโควตาอยู่ ผู้ใช้กดตรวจสถานะอีกครั้งได้ หากพบเครื่องเดิมตาม VMID/ชื่อ/Node และไม่มี lock จะคืน workflow เดิม ไม่เปลี่ยน needs_review เป็น ready โดยพลการ
- Admin พิมพ์ Hostname เพื่อยืนยันการลบจากภายนอก ระบบตรวจใหม่และตรวจซ้ำใต้ DB lock ก่อนปิดรายการ/คืนโควตา ไม่มีคำสั่ง DELETE ไป Proxmox ปิดคำขอลบที่ค้าง ยกเลิก reset/งาน review ที่ไม่ต้องทำต่อ ล้าง credential และเก็บ Audit ตาม retention

การอ่าน `/cluster/status` (ทางเลือกสำหรับการยืนยันโดย Portal) ต้องมี **Sys.Audit บน /** ให้ทั้ง Service User และ API Token เมื่อใช้ Privilege Separation ใช้ Custom Role เฉพาะสิทธิ์อ่านนี้ ไม่ต้องให้ Administrator ระบบไม่เพิ่ม ACL เอง Token ที่มีแค่ Sys.Audit บน Node ยังใช้คำสั่งกับ VM ที่อ่าน config ได้ตามปกติ แต่จะยืนยัน absence แบบ Cluster ไม่ครบ ให้แจ้งสิทธิ์ไม่พอแทนการเดาว่าลบแล้ว

อ้างอิงพฤติกรรม inventory/VMID/Cluster status: [Proxmox API implementation](https://github.com/proxmox/pve-manager/blob/master/PVE/API2/Cluster.pm) การตรวจพิสูจน์ว่าไม่อยู่ใน Cluster ที่ Portal เชื่อมต่อ ณ เวลานั้น ไม่ได้ติดตามเครื่องที่ย้ายออกไป Cluster อื่น

Admin ที่ตรวจใน Proxmox แล้วสามารถยืนยันการลบจากภายนอกพร้อมพิมพ์ชื่อ VM ได้ แม้ Portal ขาด Sys.Audit บน `/` โดยบันทึกแหล่งการยืนยันเป็น admin_proxmox_review ไม่คืนโควตาอัตโนมัติ และยังปฏิเสธเมื่อพบ VM, ย้าย Node, ติดล็อก, การเชื่อมต่อผิดพลาด หรือมีงานทำอยู่

### VM หลายขา (DHCP)

ติ๊ก Bridge ใน **เครือข่ายของ VM** เพื่อนับจำนวนขาอัตโนมัติ หรือเปิด **กำหนดแต่ละขาเอง** เพื่อเพิ่ม/ลบแถว 1–32 ขา Backend เก็บลำดับใน network_bridges และกำหนด net0..netN เป็น virtio / ipconfig0..ipconfigN เป็น ip=dhcp ทุก Bridge ต้องอยู่ใน allowlist ข้อมูลเดิมที่มี bridge/secondary_bridge ยังอ่านได้ โดยแปลงเป็นรายการ 1–2 ขาเมื่อใช้งาน ไม่ต้องทำ migration ฐานข้อมูล

Template ใช้ net0 ใบเดียวได้ ระบบเพิ่มขาอื่นหลัง Full Clone หรือใช้ Template ที่มี NIC ไม่เกินจำนวนที่เลือกได้ แต่จะปฏิเสธ NIC นอกจำนวนและ custom Cloud-Init network ที่ทับ DHCP การเปลี่ยนรายการหรือเรียงเครือข่ายใหม่ใช้กับ VM ใหม่เท่านั้น ต้องรองาน provision ที่ค้างอยู่เสร็จก่อนบันทึก หลังบันทึกต้องตรวจ Read-only และเปิดระบบตามเดิม การแก้เครือข่ายไม่แก้ VM เดิม ส่วน Cluster/Node/Pool/Storage/Boot device ยังอยู่ภายใต้ข้อจำกัด infrastructure identity เดิม

### Clone สำเร็จแต่ Portal ขึ้นต้องตรวจสอบ

VM ปรากฏใน Proxmox ไม่ได้หมายความว่าขั้นตอนตั้งค่า ขยาย Disk และเปิดเครื่องสำเร็จแล้ว หากงาน provision ค้างที่ clone_accepted, configure_sending หรือ resume_after_clone ให้ Admin เปิดกิจกรรม กด **ตรวจและทำต่อจาก Clone เดิม (Admin)** และพิมพ์ hostname ระบบตรวจ Task Clone เดิมจาก job/audit ว่าเสร็จ OK ตรวจชื่อ/VMID เครื่องปิดและไม่ติดล็อก พร้อม Cloud-Init/Boot disk/credential แล้วค่อยจัดคิวทำต่อ Worker ตรวจซ้ำก่อน configure และไม่ Clone อีกครั้ง ไม่ใช้ปุ่มนี้กับ resize/start ที่ผลยังไม่ชัด หรือเมื่อไม่มีหลักฐาน Task

คำสั่งเขียนยังไม่ลองซ้ำเมื่อผลตอบกลับกำกวม ยกเว้น PUT config ที่ ConnectTimeout ก่อนเริ่มส่ง HTTP จะลองเชื่อมต่อใหม่อีกหนึ่งครั้ง ส่วน ReadTimeout, WriteTimeout และข้อผิดพลาดหลังส่งคำสั่งยังพักให้ตรวจสอบ ไม่ส่ง Clone ซ้ำอัตโนมัติ
