import { useState } from "react";
import { FormDialog } from "./FormDialog";
import type { Dashboard } from "./types";

export function SystemStatus({setup,admin,canSetup,onSetup}:{setup:Dashboard["setup"];admin:boolean;canSetup:boolean;onSetup:()=>void}) {
  const [open,setOpen]=useState(false);
  const ready=!!(setup?.configured&&setup.connection_verified&&setup.enabled);
  const label=!setup?"กำลังตรวจสอบสถานะ":ready?"ระบบพร้อม":"ระบบยังไม่พร้อม";
  const detail=!setup?"กำลังรอข้อมูลสถานะจากระบบ":!setup.configured?"ยังไม่ได้ตั้งค่าการเชื่อมต่อ Proxmox":!setup.connection_verified?"ต้องตรวจการเชื่อมต่อให้ผ่านก่อนเปิดใช้งาน":!setup.enabled?"ระบบพักรับคำขอและคำสั่ง VM":"ระบบพร้อมรับคำขอและคำสั่ง VM ตามการตั้งค่าล่าสุด";
  if(!admin)return <span className={`system-status-button system-status-indicator ${!setup?"unknown":ready?"available":"unavailable"}`} role="status" aria-label={`สถานะระบบ: ${label}`}><span className="system-status-dot" aria-hidden="true"/>{label}</span>;
  return <>
    <button type="button" className={`system-status-button ${!setup?"unknown":ready?"available":"unavailable"}`} aria-label={`สถานะระบบ: ${label}`} aria-haspopup="dialog" aria-expanded={open} onClick={()=>setOpen(true)}><span className="system-status-dot" aria-hidden="true"/>{label}</button>
    {open&&<FormDialog title="สถานะระบบ" onClose={()=>setOpen(false)}><section className="panel"><div className="section-head"><h2>สถานะระบบ</h2><button type="button" onClick={()=>setOpen(false)}>ปิด</button></div>
      <p>{detail}</p>
      {setup&&<dl className="system-status-list">
        <div><dt>การตั้งค่า</dt><dd>{setup.configured?"ตั้งค่าแล้ว":"ยังไม่ได้ตั้งค่า"}</dd></div>
        <div><dt>ตรวจการเชื่อมต่อ</dt><dd>{setup.connection_verified?"ผ่านแล้ว":"ยังไม่ผ่าน"}</dd></div>
        <div><dt>รับคำขอและคำสั่ง VM</dt><dd>{setup.enabled?"เปิดใช้งาน":"พักใช้งาน"}</dd></div>
      </dl>}
      {!ready&&<p className="muted">{canSetup?"ตั้งค่า ตรวจการเชื่อมต่อ และเปิดใช้งานในหน้า Setup":"กรุณารอผู้ดูแลหลักตรวจสอบและเปิดใช้งานระบบ"}</p>}
      {canSetup&&<button type="button" className="primary" onClick={()=>{setOpen(false);onSetup();}}>ไปหน้า Setup</button>}
    </section></FormDialog>}
  </>;
}
