"""Public error text: no submitted values, validator context or provider response bodies."""

FIELD_LABELS = {
    "request_reason": "เหตุผลที่ขอสร้าง VM",
    "username": "ชื่อผู้ใช้",
    "mode": "โหมดเชื่อมต่อ",
    "auth_method": "วิธีเข้าใช้งาน VM",
    "action": "คำสั่ง VM",
    "approve": "การอนุมัติ",
    "enabled": "การเปิดระบบ",
    "vm_id": "หมายเลข VM",
    "user_id": "หมายเลขผู้ใช้",
    "job_id": "หมายเลขงาน",
    "request_id": "หมายเลขคำขอ",
    "password": "รหัสผ่าน",
    "confirm_password": "ยืนยันรหัสผ่าน",
    "first_name": "ชื่อ",
    "last_name": "นามสกุล",
    "hostname": "ชื่อ VM",
    "cpu": "CPU",
    "ram": "RAM",
    "disk": "ขนาด Disk",
    "ssh_key": "SSH Public Key",
    "guest_username": "ชื่อผู้ใช้ใน VM",
    "vm_password": "รหัสผ่าน VM",
    "reason": "เหตุผล",
    "token_id": "API Token ID",
    "token_secret": "API Token Secret",
    "ca_pem": "CA Certificate",
    "url": "API Endpoint",
    "bridge": "Network Bridge",
    "network_bridges": "เครือข่ายของ VM",
    "bridge_allowlist": "Bridge allowlist",
    "node": "Node",
    "pool": "Resource Pool",
    "storage": "Storage",
    "template": "Template VMID",
    "vmid": "Template VMID",
    "min_disk_gb": "Disk ขั้นต่ำ",
    "name": "ชื่อ Template",
    "description": "คำอธิบาย",
    "template_id": "Template",
    "template_disk_gb": "ขนาด Disk ของ Template",
    "disk_device": "Boot disk device",
    "token_minutes": "ระยะเวลา Session",
    "confirm_vm_ids": "รายการ VM ยืนยัน",
    "confirm_username": "ชื่อบัญชียืนยันลบ",
    "confirm_hostname": "ชื่อ VM ยืนยัน",
    "code": "โค้ดกู้คืน",
    "current_password": "รหัสผ่านปัจจุบัน",
    "new_password": "รหัสผ่านใหม่",
    "admin_password": "รหัสผ่าน Admin",
    "quota_vms": "โควตา VM",
    "quota_cpu": "โควตา CPU",
    "quota_ram": "โควตา RAM",
    "quota_disk": "โควตา Disk",
}
MESSAGES = {
    "Cluster audit permission required to confirm missing VM": "ยังยืนยันว่า VM หายไม่ได้ สิทธิ์อ่านสถานะ Cluster ไม่เพียงพอ กรุณาให้ผู้ดูแลตรวจสอบ",
    "Proxmox task still active; absence cannot be confirmed": "งานเดิมใน Proxmox ยังไม่จบหรือยังตรวจสอบไม่ได้ จึงยังสรุปว่า VM หายไม่ได้",
    "Clone outcome is uncertain; absence cannot be confirmed": "งานสร้าง VM เดิมยังมีผลไม่แน่นอน กรุณาให้ผู้ดูแลตรวจ Task ก่อนปิดรายการ",
    "VM confirmed missing from Proxmox": "ไม่พบ VM ใน Proxmox หลังตรวจสอบแล้ว กรุณาให้ Admin ยืนยันรายการ โควตายังไม่ถูกคืน",
    "VM moved to another Proxmox node": "พบว่า VM ย้ายไป Node อื่น กรุณาให้ผู้ดูแลตรวจสอบ ยังไม่ได้ส่งคำสั่ง",
    "VM identity changed; command blocked": "ข้อมูล VM ไม่ตรงกับเครื่องเดิม ระบบระงับคำสั่ง กรุณาติดต่อผู้ดูแล",
    "VM is locked; command blocked": "VM กำลังถูกล็อกหรือมีงานใน Proxmox กรุณารอให้เสร็จแล้วลองใหม่",
    "VM presence cannot be verified: permission": "สิทธิ์ตรวจสอบ VM ไม่เพียงพอ ยังยืนยันไม่ได้ว่าเครื่องหาย กรุณาติดต่อผู้ดูแล",
    "VM presence could not be verified": "ยังตรวจสอบ VM ไม่สำเร็จ อาจเป็นการเชื่อมต่อหรือระบบ Proxmox ขัดข้อง กรุณาลองใหม่ภายหลัง",
    "A confirmed missing VM is required": "ต้องเป็นรายการ VM ที่ตรวจยืนยันว่าหายก่อน",
    "VM exists again; external deletion was not confirmed": "ตรวจพบ VM อีกครั้ง จึงไม่ปิดรายการหรือคืนโควตา กรุณาตรวจสถานะล่าสุด",
    "VM presence changed; external deletion was not confirmed": "สถานะ VM เปลี่ยนระหว่างตรวจสอบ จึงไม่ปิดรายการหรือคืนโควตา",
    "A meaningful VM request reason is required": "กรุณาระบุเหตุผลที่ขอสร้าง VM เป็นข้อความ ไม่ใช้สัญลักษณ์หรืออักขระควบคุมอย่างเดียว",
    "Quota defaults schema missing; run migrations": "ระบบโควตาเริ่มต้นยังไม่พร้อม กรุณาให้ผู้ดูแลตรวจการอัปเดตฐานข้อมูล",
    "Registration password requires uppercase, lowercase, digit and special character": "รหัสผ่านสมัครสมาชิกต้องมีตัวพิมพ์ใหญ่ A–Z พิมพ์เล็ก a–z ตัวเลข 0–9 และอักขระพิเศษ เช่น !@#$% และไม่มีอักขระควบคุม",
    "System and root guest usernames are not allowed": "ไม่อนุญาตให้ใช้ root หรือบัญชีระบบเป็นชื่อผู้ใช้ใน VM",
    "SSH password login requires password authentication": "กรุณาเลือกการเข้าใช้งานแบบรหัสผ่านก่อนเปิด SSH Password",
    "SSH key mode requires a public key and no VM password": "โหมด SSH Key ต้องระบุ Public Key และไม่ส่งรหัสผ่าน VM",
    "Password mode does not accept an SSH key": "โหมดรหัสผ่านไม่รับ SSH Key กรุณาเลือกวิธีเข้าใช้งานเพียงแบบเดียว",
    "VM password must be 12-128 characters without control characters": "รหัสผ่าน VM ต้องยาว 12–128 ตัว ไม่เป็นช่องว่างล้วนและไม่มีอักขระควบคุม",
    "Password requires 12-128 characters without control characters": "รหัสผ่านต้องยาว 12–128 ตัว ไม่เป็นช่องว่างล้วนและไม่มีอักขระควบคุม",
    "Reason is required": "กรุณาระบุเหตุผล ไม่ใช้ช่องว่างอย่างเดียว",
    "Endpoint must be an HTTPS origin without credentials or path": "API Endpoint ต้องเป็น https://ชื่อหรือIP:พอร์ต ไม่ใส่บัญชี รหัสผ่าน หรือ path ต่อท้าย",
    "Wait for running jobs before changing configuration": "มีงานกำลังทำงาน กรุณารอให้เสร็จก่อนแก้การเชื่อมต่อ",
    "Wait for pending provisioning jobs before changing template": "มีงานสร้าง VM ค้างอยู่ กรุณารอให้เสร็จก่อนเปลี่ยน Template",
    "Create the initial administrator first": "กรุณาสร้างผู้ดูแลระบบคนแรกก่อนเปิดรับสมัครสมาชิก",
    "A console session is already active; close it or wait for expiry": "มี Console เปิดอยู่แล้ว กรุณาปิดหน้าต่างเดิมหรือรอ Session หมดอายุ",
    "Clone task proof not found; admin review required": "ไม่พบหลักฐาน Task Clone ของงานนี้ ให้ผู้ดูแลตรวจสอบก่อนทำต่อ",
    "This job cannot be resumed safely; close it and notify the user": "งานนี้ทำต่ออย่างปลอดภัยไม่ได้ กรุณาปิดงานและแจ้งเหตุผลให้ผู้ใช้",
    "VM disk is larger than requested; admin review required": "Disk ของ VM ใหญ่กว่าที่ขอไว้ ระบบจึงไม่ทำต่ออัตโนมัติ กรุณาตรวจใน Proxmox",
    "Only a job awaiting review can be closed": "ปิดได้เฉพาะงานที่รอผู้ดูแลตรวจสอบ กรุณาโหลดข้อมูลล่าสุด",
    "Job changed; reload and try again": "สถานะงานเปลี่ยนระหว่างตรวจสอบ กรุณาโหลดข้อมูลล่าสุดแล้วลองใหม่",
    "Cannot read VM disk size; admin review required": "อ่านขนาด Disk ของ VM ไม่ได้ กรุณาตรวจใน Proxmox",
    "Existing clone is locked or is a template": "เครื่องเดิมติดล็อกหรือเป็น Template จึงยังทำต่อไม่ได้",
    "Start VM before opening console": "VM ยังไม่ทำงาน กรุณาเปิดเครื่องจากเมนูจัดการก่อน แล้วเปิด Console ใหม่",
    "Invalid credentials": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง กรุณาตรวจแล้วลองใหม่",
    "Account not approved": "บัญชียังไม่ได้รับอนุมัติหรือถูกระงับ กรุณาติดต่อผู้ดูแลระบบ",
    "Session invalid; sign in again": "การเข้าสู่ระบบไม่สามารถใช้งานได้แล้ว กรุณาเข้าสู่ระบบอีกครั้ง",
    "Session expired; sign in again": "Session หมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง",
    "Primary administrator required": "คำสั่งนี้สงวนไว้สำหรับผู้ดูแลหลัก Admin ทั่วไปดูข้อมูลและอนุมัติคำขอได้เท่านั้น",
    "Top administrator required": "คำสั่งนี้สงวนไว้สำหรับผู้ดูแลสูงสุด",
    "The top administrator keeps primary rights": "เปลี่ยนสิทธิ์ของผู้ดูแลสูงสุดหรือของตนเองไม่ได้",
    "Only an approved admin can hold primary rights": "มอบสิทธิ์ผู้ดูแลหลักได้เฉพาะ Admin ที่อนุมัติแล้ว ยกระดับบัญชีเป็น Admin ก่อน",
    "Only an approved account can change role": "เปลี่ยนสิทธิ์ได้เฉพาะบัญชีที่อนุมัติแล้ว",
    "Account already has this role": "บัญชีนี้มีสิทธิ์ระดับนี้อยู่แล้ว กรุณาโหลดข้อมูลล่าสุด",
    "Admin required": "คำสั่งนี้ต้องใช้สิทธิ์ผู้ดูแลระบบ",
    "Username unavailable": "ชื่อผู้ใช้นี้ไม่พร้อมใช้งาน กรุณาเลือกชื่ออื่น",
    "Password confirmation does not match": "รหัสผ่านและช่องยืนยันรหัสผ่านไม่ตรงกัน",
    "Invalid personal name": "ชื่อและนามสกุลต้องเป็นตัวอักษร ไม่ใส่ตัวเลขหรืออักขระพิเศษ",
    "Too many attempts": "ทำรายการถี่เกินไป กรุณารอ 1 นาทีแล้วลองใหม่",
    "Authentication temporarily unavailable": "ระบบเข้าสู่ระบบไม่พร้อมชั่วคราว กรุณาลองใหม่ภายหลัง",
    "Disk smaller than template": "ขนาด Disk ต้องไม่น้อยกว่าขนาด Template ที่ผู้ดูแลกำหนด",
    "Choose a template": "กรุณาเลือก Template ที่ต้องการ",
    "Template is not available": "Template นี้ยังไม่เปิดให้ขอ หรือถูกปิด/แก้ไขแล้วรอตรวจสอบใหม่ กรุณาเลือก Template อื่นหรือติดต่อผู้ดูแล",
    "Template not found": "ไม่พบ Template นี้",
    "Template name already exists": "มีชื่อ Template นี้แล้ว กรุณาใช้ชื่ออื่น",
    "Template name required": "กรุณาตั้งชื่อ Template",
    "Verify the template before enabling it": "ต้องตรวจสอบ Template ให้ผ่านก่อนเปิดให้ผู้ใช้ขอ",
    "Template has pending requests; decide them before deleting": "Template นี้มีคำขอรออนุมัติอยู่ กรุณาอนุมัติหรือปฏิเสธคำขอเหล่านั้นก่อนลบ",
    "Template check failed; check the connection and VMID": "ตรวจสอบ Template ไม่สำเร็จ กรุณาตรวจการเชื่อมต่อและ VMID",
    "Too many pending requests": "มีคำขอค้างรออนุมัติมากเกินไป กรุณารอให้ผู้ดูแลพิจารณาก่อน",
    "Hostname already exists; choose a different hostname": "ชื่อ VM นี้ถูกใช้งานแล้ว กรุณาเลือกชื่อใหม่",
    "Request already decided": "รายการนี้ถูกพิจารณาแล้ว กรุณาโหลดข้อมูลล่าสุด",
    "Account already decided": "บัญชีนี้ถูกพิจารณาแล้ว กรุณาโหลดข้อมูลล่าสุด",
    "Owner not approved": "เจ้าของ VM ยังไม่ได้รับอนุมัติหรือถูกระงับ",
    "VM is not ready": "VM ยังไม่พร้อมรับคำสั่ง กรุณาตรวจสถานะและงานที่ค้างอยู่",
    "An operation is already active": "VM นี้มีคำสั่งกำลังทำงาน กรุณารอให้เสร็จก่อน",
    "VM hostname confirmation does not match": "ชื่อ VM ที่พิมพ์ยืนยันไม่ตรง กรุณาตรวจชื่อเครื่อง",
    "Username confirmation does not match": "ชื่อบัญชีที่พิมพ์ยืนยันไม่ตรง กรุณาตรวจชื่อผู้ใช้",
    "Account VM list changed; reload deletion preview": "รายการ VM ของบัญชีเปลี่ยนไป กรุณาปิดหน้าต่างแล้วเปิดตรวจรายการลบใหม่",
    "Account deletion already requested": "บัญชีนี้ถูกลบหรืออยู่ระหว่างลบแล้ว กรุณาตรวจสถานะล่าสุด",
    "Account deletion is in progress": "บัญชีเจ้าของกำลังถูกลบ จึงไม่สามารถสั่งงาน VM เพิ่มได้",
    "Account has active VM jobs; wait for completion": "บัญชีนี้มีงาน VM ค้างอยู่ กรุณารอให้งานเสร็จก่อนลบผู้ใช้",
    "Account has VMs requiring review; reconcile before deletion": "บัญชีนี้มี VM ที่ต้องตรวจสอบ กรุณาแก้สถานะในหน้ากิจกรรมก่อนลบผู้ใช้",
    "An approved deletion already exists; reconcile before account deletion": "มีงานลบ VM ที่อนุมัติแล้ว กรุณาตรวจให้งานเสร็จก่อนลบผู้ใช้",
    "VM must be stopped before approved deletion; no force stop performed": "กรุณาปิด VM ให้มีสถานะปิดเครื่องก่อนลบ ระบบจะไม่บังคับปิดเครื่องให้อัตโนมัติ",
    "Complete system setup first": "กรุณาตั้งค่าการเชื่อมต่อระบบให้ครบก่อนทำรายการ",
    "Verify connection and enable the system in Setup first": "กรุณาตรวจการเชื่อมต่อและเปิดใช้งานระบบที่หน้าตั้งค่า",
    "Current password is incorrect": "รหัสผ่านปัจจุบันไม่ถูกต้อง",
    "Administrator password is incorrect": "รหัสผ่าน Admin ไม่ถูกต้อง",
    "New password must differ from current password": "รหัสผ่านใหม่ต้องต่างจากรหัสผ่านเดิม",
    "Recovery code is invalid, expired or already used": "โค้ดกู้คืนไม่ถูกต้อง หมดอายุ หรือถูกใช้แล้ว กรุณาขอโค้ดใหม่จากผู้ดูแล",
    "Quota cannot be below current reservations": "โควตาใหม่ต้องไม่น้อยกว่าทรัพยากรที่จองใช้อยู่",
    "Deletion already requested": "VM นี้มีคำขอลบอยู่แล้ว กรุณาตรวจรายการเดิม",
    "A password reset is already pending": "VM นี้มีคำขอรีเซ็ตรหัสผ่านค้างอยู่แล้ว",
    "Only a pending reset can be cancelled": "ยกเลิกได้เฉพาะคำขอที่ยังรออนุมัติ",
    "Console is available only for real VMs": "Console ใช้ได้กับ VM จริงเท่านั้น",
    "Bridge must belong to the allowlist": "Network Bridge ต้องอยู่ในรายการที่อนุญาต",
    "A valid trusted CA PEM is required": "CA Certificate ไม่ถูกต้อง กรุณาใช้ไฟล์ใบรับรองแบบ PEM",
    "CA PEM required": "กรุณาระบุ CA Certificate ก่อนเชื่อมต่อจริง",
    "Invalid token secret": "รูปแบบ Token Secret ไม่ถูกต้อง กรุณาตรวจค่าจาก Proxmox",
    "Wait for pending provisioning jobs before changing network": "กรุณารอให้งานสร้าง VM ที่ค้างอยู่เสร็จก่อนเปลี่ยนเครือข่าย",
    "Custom Cloud-Init network overrides DHCP; review template": "Template ใช้ไฟล์ Cloud-Init network เอง ซึ่งทับค่า DHCP กรุณาตรวจ Template ก่อนใช้งานหลายขา",
    "Template network devices exceed configured interfaces": "จำนวนการ์ดเครือข่ายใน Template เกินที่ตั้งค่าไว้ กรุณาตรวจ Template และจำนวนขาที่เลือก",
    "Enter token secret for this connection": "กรุณากรอก Token Secret ใหม่สำหรับการเชื่อมต่อนี้",
    "Token secret required for real connection": "กรุณาระบุ Token Secret ก่อนเชื่อมต่อจริง",
    "Unsupported SSH public key": "ชนิด SSH Key ไม่รองรับ กรุณาใช้ ed25519, RSA หรือ ECDSA ที่รองรับ",
    "Invalid SSH public key": "SSH Public Key ไม่ถูกต้อง กรุณาคัดลอก Public Key ให้ครบหนึ่งบรรทัด",
    "Guest Agent is unavailable; check agent=1, running service and VM.GuestAgent.Audit": "QEMU Guest Agent ใน VM ไม่ตอบสนอง จึงรีเซ็ตรหัสและอ่าน IP ไม่ได้ ให้ติดตั้งและเปิด qemu-guest-agent ภายใน VM (sudo apt install -y qemu-guest-agent แล้ว sudo systemctl enable --now qemu-guest-agent)",
    "Guest Agent does not enable guest-set-user-password": "QEMU Guest Agent ใน VM ปิดคำสั่งตั้งรหัสผ่านไว้ กรุณาตรวจการตั้งค่า qemu-guest-agent ภายใน VM",
    "VM must be running for Guest Agent password reset": "ต้องเปิด VM ก่อนจึงจะรีเซ็ตรหัสได้",
    "Only accounts below your level can be managed": "จัดการได้เฉพาะบัญชีที่มีระดับต่ำกว่าคุณ (ผู้ใช้ < Admin < ผู้ดูแลหลัก < ผู้ดูแลสูงสุด)",
}


QUOTA_NAMES = {
    "vms": ("จำนวน VM ", " เครื่อง"),
    "cpu": ("vCPU ", " vCPU"),
    "ram": ("RAM ", " MiB"),
    "disk": ("Disk ", " GiB"),
}


def public_message(detail, status=400):
    text = detail if isinstance(detail, str) else ""
    if text in MESSAGES:
        return MESSAGES[text]
    if text.startswith("Quota exceeded:"):
        name, _, left = text.removeprefix("Quota exceeded:").partition("; remaining ")
        label, unit = QUOTA_NAMES.get(name.strip(), ("ทรัพยากร", ""))
        if left.isdigit():
            return (
                f"{label}เกินโควตา: เหลือให้ขอได้อีก {left}{unit} "
                "(นับรวมคำขอที่รออนุมัติ) กรุณาลดค่าที่ขอหรือขอผู้ดูแลเพิ่มโควตา"
            )
        return f"{label}เกินโควตาที่ได้รับ กรุณาลดทรัพยากรหรือขอผู้ดูแลเพิ่มโควตา"
    if text.startswith("Password reset requires VM.GuestAgent.Unrestricted at "):
        return (
            "Token ของ Portal ยังไม่มีสิทธิ์ VM.GuestAgent.Unrestricted ที่ "
            + text.split(" at ", 1)[1].split(";", 1)[0]
            + " จึงรีเซ็ตรหัส VM ไม่ได้ กรุณาให้ผู้ดูแลหลักเพิ่มสิทธิ์ใน Proxmox"
        )
    if text.startswith("Cannot read node health;"):
        return (
            "อ่านสุขภาพ Proxmox ไม่สำเร็จ กรุณาตรวจการเชื่อมต่อและสิทธิ์ Sys.Audit บน "
            + text.split(" at ", 1)[-1].split(";", 1)[0]
        )
    if status == 404:
        return "ไม่พบรายการที่ร้องขอ หรือคุณไม่มีสิทธิ์เข้าถึง"
    if status >= 500:
        return (
            "ระบบหรือการเชื่อมต่อขัดข้อง กรุณาลองใหม่ภายหลัง หากยังไม่สำเร็จให้แจ้งผู้ดูแลพร้อมเลขอ้างอิง"
        )
    if status == 403:
        return "คุณไม่มีสิทธิ์ทำรายการนี้ กรุณาติดต่อผู้ดูแลระบบ"
    if status == 401:
        return "กรุณาเข้าสู่ระบบใหม่เพื่อทำรายการต่อ"
    if status == 409:
        return (
            "ยังทำรายการนี้ไม่ได้ กรุณาตรวจสถานะ VM และงานในหน้ากิจกรรม หรือติดต่อผู้ดูแลพร้อมเลขอ้างอิง"
        )
    return "ข้อมูลหรือเงื่อนไขไม่ถูกต้อง กรุณาตรวจช่องที่กรอก หากยังไม่สำเร็จให้แจ้งผู้ดูแลพร้อมเลขอ้างอิง"


def validation_message(error):
    loc = error.get("loc", ())
    field = next(
        (v for v in reversed(loc) if isinstance(v, str) and v in FIELD_LABELS), None
    )
    label = FIELD_LABELS.get(field, "ข้อมูล")
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    if kind == "missing":
        return f"กรุณากรอก{label}"
    if kind == "extra_forbidden":
        return "มีข้อมูลที่ระบบไม่อนุญาต กรุณาใช้ฟอร์มของระบบและลองใหม่"
    if kind == "json_invalid":
        return "รูปแบบข้อมูลที่ส่งไม่ถูกต้อง กรุณาโหลดหน้าใหม่แล้วลองอีกครั้ง"
    if kind == "string_pattern_mismatch" and field == "token_id":
        return (
            "API Token ID ต้องมีรูปแบบ user@realm!token-name เช่น vmportal@pve!portal-api"
        )
    if kind == "string_pattern_mismatch" and field == "disk_device":
        return "Boot disk device ต้องเป็นชื่อ Disk เช่น scsi0, sata0 หรือ virtio0"
    if kind == "string_pattern_mismatch" and field in {
        "node",
        "pool",
        "storage",
        "bridge",
    }:
        return (
            f"{label}ใช้ได้เฉพาะตัวอักษรอังกฤษ ตัวเลข จุด ขีดกลาง หรือขีดล่าง ความยาวไม่เกิน 63 ตัว"
        )
    if kind == "literal_error":
        return f"{label}ไม่ใช่ตัวเลือกที่ระบบรองรับ กรุณาเลือกจากรายการในฟอร์ม"
    if kind == "bool_type":
        return f"{label}ต้องเป็นค่าเปิดหรือปิดที่ถูกต้อง"
    if kind == "string_pattern_mismatch" and field == "username":
        return "ชื่อผู้ใช้ต้องเริ่มด้วย a-z หรือ 0-9 และใช้ได้เฉพาะ a-z, 0-9, จุด, ขีดกลาง และขีดล่าง"
    if kind == "string_pattern_mismatch" and field == "hostname":
        return "ชื่อ VM ต้องเริ่มด้วย a-z และใช้เฉพาะ a-z, 0-9 หรือขีดกลาง ความยาวไม่เกิน 40 ตัว"
    if kind == "string_pattern_mismatch" and field == "guest_username":
        return "ชื่อผู้ใช้ใน VM ต้องเริ่มด้วย a-z และใช้เฉพาะ a-z, 0-9, ขีดกลางหรือขีดล่าง"
    limits = {
        "string_too_short": ("min_length", "ต้องมีอย่างน้อย", "ตัวอักษร"),
        "string_too_long": ("max_length", "ต้องไม่เกิน", "ตัวอักษร"),
        "greater_than_equal": ("ge", "ต้องไม่น้อยกว่า", ""),
        "less_than_equal": ("le", "ต้องไม่เกิน", ""),
    }
    if kind in limits:
        key, rule, unit = limits[kind]
        limit = ctx.get(key)
        if isinstance(limit, (int, float)):
            return f"{label}{rule} {limit} {unit}".strip()
    if kind in {"int_type", "int_parsing"}:
        return f"{label}ต้องเป็นจำนวนเต็ม"
    if kind == "value_error":
        message = str(ctx.get("error", ""))
        if message in MESSAGES:
            return MESSAGES[message]
    return f"{label}มีรูปแบบหรือค่าไม่ถูกต้อง กรุณาตรวจตามเงื่อนไขของช่องนี้"
