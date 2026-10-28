const statuses: Record<string,string> = {missing:"ไม่พบ VM ใน Proxmox",deleting:"กำลังลบบัญชีและ VM",pending:"รออนุมัติ",approved:"อนุมัติแล้ว",rejected:"ไม่อนุมัติ",queued:"รอดำเนินการ",running:"กำลังทำงาน",provisioning:"กำลังเตรียม",ready:"พร้อมใช้งาน",succeeded:"สำเร็จ",needs_review:"ต้องตรวจสอบ",deleted:"ลบแล้ว",completed:"เสร็จแล้ว",cancelled:"ยกเลิกแล้ว",failed:"ไม่สำเร็จ"};
const operations: Record<string,string> = {provision:"สร้าง VM",start:"เปิดเครื่อง",shutdown:"ปิดเครื่อง",stop:"บังคับปิดเครื่อง",reboot:"Restart",delete:"ลบ VM",reset_password:"รีเซ็ตรหัส VM"};
export const statusLabel=(value:string)=>statuses[value]??value;
export const operationLabel=(value:string)=>operations[value]??value;
