import { useRef, useState } from "react";
import { FormDialog } from "./FormDialog";
import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import type { User } from "./types";

type API = <T>(path: string, body?: unknown) => Promise<T>;
export function AdminRoleForm({api,user,onClose,onDone}:{api:API;user:User;onClose:()=>void;onDone:(user:User)=>void}) {
  const proofInput=useRef<HTMLInputElement>(null);
  const [name,setName]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  const promote=user.role!=="admin";
  const title=promote?`ยกระดับ ${user.username} เป็น Admin`:`ลดสิทธิ์ ${user.username} เป็นผู้ใช้`;
  return <FormDialog title={title} busy={busy} onClose={onClose}><section className="panel recovery-panel role-panel">
    <div className="section-head"><div className="help-heading"><h2>{title}</h2><HelpTip label="สิทธิ์ของ Admin ที่ยกระดับ">Admin ที่ยกระดับอนุมัติคำขอ จัดการ VM งานค้าง และตั้งค่าระบบได้ แต่ลบผู้ใช้ เปลี่ยนสิทธิ์ผู้อื่น และออกโค้ดกู้คืนให้ Admin คนอื่นไม่ได้ ทุกการตัดสินใจจะแสดงชื่อผู้ทำให้ผู้ใช้เห็น</HelpTip></div><button type="button" disabled={busy} onClick={onClose}>ปิด</button></div>
    {promote
      ?<ul className="role-scope"><li>อนุมัติ / ปฏิเสธบัญชีและคำขอ VM ได้</li><li>ทำต่อหรือปิดงานค้าง และตั้งค่าระบบได้</li><li><strong>ลบผู้ใช้ เปลี่ยนสิทธิ์ผู้อื่น และออกโค้ดกู้คืนให้ Admin ไม่ได้</strong></li></ul>
      :<p className="muted">บัญชีนี้จะกลับเป็นผู้ใช้ทั่วไปทันที และเข้าหน้าผู้ดูแลไม่ได้อีก ประวัติการตัดสินใจเดิมยังแสดงชื่อนี้ไว้</p>}
    <form className="sensitive-fields" data-form-type="other" autoComplete="off" onSubmit={async e=>{
      e.preventDefault();if(busy||!proofInput.current)return;
      const proof=proofInput.current.value;proofInput.current.value="";setBusy(true);setError("");
      try{onDone(await api<User>(`/admin/users/${user.id}/role`,{role:promote?"admin":"user",admin_password:proof,confirm_username:name}));}
      catch(e){setError(explainError(e));}finally{setBusy(false);}
    }}>
      <label>พิมพ์ชื่อผู้ใช้ {user.username} เพื่อยืนยัน<input value={name} onChange={e=>setName(e.target.value)} required autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={32}/></label>
      <label>รหัส Portal ของคุณ<input ref={proofInput} type="password" autoComplete="off" data-lpignore="true" data-1p-ignore="true" required maxLength={128}/></label>
      {error&&<p role="alert" className="error">{error}</p>}
      <button className={promote?"primary":"danger"} disabled={busy||name!==user.username}>{promote?"ยืนยันยกระดับเป็น Admin":"ยืนยันลดสิทธิ์"}</button>
    </form>
  </section></FormDialog>;
}
