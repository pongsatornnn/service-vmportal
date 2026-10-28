import { Highlight, type Step } from "./RequestCard";
import type { Job, VM } from "./types";

export type RequestKind="provision"|"delete"|"reset_password";
const finished=["succeeded","rejected","cancelled","deleted","failed"];
export function describeRequest(status:string,kind:RequestKind,vm?:VM,job?:Job) {
  const action=kind==="provision"?"สร้าง VM":kind==="delete"?"ลบ VM":"รีเซ็ตรหัส VM";
  let state=status,label="",message="";
  if(job?.state==="failed") {
    state="failed";label=`${action}ไม่สำเร็จ`;
    message=kind==="provision"?"ผู้ดูแลตรวจสอบแล้วว่าทำต่อไม่ได้ ระบบคืนสิทธิ์ใช้ทรัพยากรแล้ว (หากมีเครื่องค้างอยู่ ระบบจะลบให้) ส่งคำขอใหม่ได้ตามคำแนะนำด้านล่าง":kind==="delete"?"ผู้ดูแลตรวจสอบแล้วว่าลบไม่ได้ VM ยังใช้งานได้ตามเดิม":"ผู้ดูแลตรวจสอบแล้วว่าเปลี่ยนรหัสผ่านไม่ได้ รหัสผ่านเดิมยังใช้ได้ ส่งคำขอใหม่ได้ตามคำแนะนำด้านล่าง";
  }
  else if(status==="pending") {label="รอ Admin พิจารณา";message="ส่งคำขอแล้ว กำลังรอการอนุมัติ";}
  else if(status==="rejected") {label="Admin ปฏิเสธคำขอ";message="คำขอนี้ไม่ได้รับอนุมัติ";}
  else if(status==="cancelled") {label="ยกเลิกคำขอแล้ว";message="คำขอนี้ถูกยกเลิกแล้ว";}
  else if(status==="deleted") {state="deleted";label="ปิดคำขอแล้ว · VM ถูกลบ";message="VM ถูกลบแล้ว และคืนสิทธิ์ใช้ทรัพยากรแล้ว";}
  else if(["succeeded","completed"].includes(status)||(kind==="provision"&&status==="approved"&&(vm?.status==="ready"||job?.state==="succeeded"||(vm?.status==="missing"&&vm.presence_previous_status==="ready")))) {
    state="succeeded";label=`${action} สำเร็จ`;
    message=kind==="provision"?(vm?.status==="ready"?"VM พร้อมใช้งาน เปิดดูได้ที่หน้าเครื่องเสมือน":"คำขอสร้าง VM สำเร็จแล้ว ตรวจสถานะปัจจุบันได้ที่หน้าเครื่องเสมือน"):kind==="delete"?"ลบ VM เรียบร้อยแล้ว":"เปลี่ยนรหัสผ่านใน VM เรียบร้อยแล้ว";
  } else if(status==="needs_review"||(status==="approved"&&job?.state==="needs_review")) {
    state="needs_review";label="ยังไม่สำเร็จ · รอ Admin ตรวจสอบ";message="ระบบยังยืนยันผลสำเร็จไม่ได้ กรุณารอผู้ดูแลตรวจสอบและอย่าส่งคำขอซ้ำ";
  } else if(status==="approved"&&!job&&(!vm||["needs_review","missing"].includes(vm.status))) {
    label="Admin อนุมัติแล้ว";message="กำลังรอข้อมูลผลดำเนินการ หากสถานะไม่อัปเดตกรุณาติดต่อผู้ดูแล";
  } else if(status==="approved") {
    state=job?.state==="running"||(kind==="provision"&&vm?.status==="provisioning")?"running":"queued";
    label=state==="running"?`กำลัง${action}`:`อนุมัติแล้ว · รอ${action}`;
    message="Admin อนุมัติแล้ว ระบบกำลังดำเนินงานตามคำขอ";
  } else {label="กำลังตรวจสอบสถานะคำขอ";message="กรุณารอข้อมูลอัปเดตหรือติดต่อผู้ดูแล";}
  return {state,label,message,done:finished.includes(state)};
}
const finishLabels:Record<string,string>={succeeded:"เสร็จ",failed:"ปิดงาน",needs_review:"หยุดรอตรวจสอบ",cancelled:"ยกเลิกงาน"};
export function requestSteps(status:string,createdAt?:string,decidedAt?:string|null,job?:Job):Step[] {
  const decision=status==="rejected"?"ไม่อนุมัติ":status==="cancelled"?"ยกเลิก":"อนุมัติ";
  return [["ส่งคำขอ",createdAt],[decision,decidedAt],[finishLabels[job?.state??""]??"เสร็จ",job&&finishLabels[job.state]?job.finished_at:undefined]];
}

// What happened and who decided; the badge with describeRequest().label sits in the card head.
export function RequestOutcome({status,kind,vm,job,reason,decidedBy}:{status:string;kind:RequestKind;vm?:VM;job?:Job;reason?:string|null;decidedBy?:string|null}) {
  const comment=reason?.trim();
  const showComment=comment&&!["Admin confirmed hostname","Admin confirmed account cascade"].includes(comment);
  const {state,message}=describeRequest(status,kind,vm,job);
  // Who made the decision, so the owner knows which administrator to contact.
  const actor=job?.state==="failed"?job.reviewed_by_name:decidedBy;
  const verb=job?.state==="failed"?"ปิดงาน":status==="rejected"?"ปฏิเสธ":status==="cancelled"?"ยกเลิก":"อนุมัติ";
  return <>
    <p className={`outcome-message tone-${state}`}>{message}</p>
    {actor&&status!=="pending"&&<p className="decided-by">{verb}โดย Admin <strong>{actor}</strong></p>}
    {state==="failed"?<Highlight tone="danger" title="ข้อความจาก Admin">{job?.user_message?.trim()||"กรุณาติดต่อผู้ดูแลระบบ"}</Highlight>
      :status==="rejected"?<Highlight tone="danger" title="เหตุผลที่ไม่อนุมัติ">{comment||"คำขอเดิมนี้ไม่ได้บันทึกเหตุผลไว้ กรุณาติดต่อผู้ดูแล"}</Highlight>
      :showComment?<Highlight title="ความเห็นจาก Admin">{comment}</Highlight>:null}
  </>;
}
