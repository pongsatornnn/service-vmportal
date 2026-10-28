import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import { useEffect, useRef, useState } from 'react';
import type { User, VM } from './types';
import { statusLabel } from './labels';
type API=<T>(path:string,body?:unknown)=>Promise<T>;
export function DeleteUserDialog({user,api,onClose,onDone}:{user:User;api:API;onClose:()=>void;onDone:()=>void}){
 const dialog=useRef<HTMLDialogElement>(null),[preview,setPreview]=useState<{user:User;vms:VM[]}|null>(null),[error,setError]=useState(''),[name,setName]=useState(''),[busy,setBusy]=useState(false);
 const reasonInput=useRef<HTMLTextAreaElement>(null),proofInput=useRef<HTMLInputElement>(null);
 useEffect(()=>{const previous=document.activeElement as HTMLElement|null;dialog.current?.showModal();let active=true;api<{user:User;vms:VM[]}>(`/admin/users/${user.id}/deletion-preview`).then(r=>{if(active)setPreview(r);}).catch(e=>{if(active)setError(explainError(e));});return()=>{active=false;dialog.current?.close();if(previous?.isConnected)previous.focus();};},[user.id]);
 return <dialog ref={dialog} className="confirmation-dialog account-delete-dialog" aria-labelledby="delete-user-title" onCancel={e=>{e.preventDefault();if(!busy)onClose();}}>
  <div className="help-heading"><h2 id="delete-user-title">ลบผู้ใช้และ VM ของบัญชี</h2><HelpTip label="เกี่ยวกับการลบผู้ใช้">เมื่อรับงาน ระบบจะยกเลิก Login และคำขอค้างของบัญชีทันที บัญชีจะแสดงว่าลบแล้วเมื่อ VM ลบสำเร็จทั้งหมด ประวัติ Audit ยังคงอยู่</HelpTip></div><p><strong>{user.username}</strong> · {user.first_name} {user.last_name}</p>
  {error&&<p className="alert error" role="alert">{error}</p>}
  {!preview?<p>กำลังอ่านรายการ VM…</p>:<><p className="alert warning">VM ทั้ง {preview.vms.length} เครื่องด้านล่างจะถูกลบถาวร ต้องปิด VM ทุกเครื่องและรอให้งานเดิมเสร็จก่อนยืนยัน</p>
   <ul className="deletion-vms">{preview.vms.map(v=><li key={v.id}>{v.hostname} · VMID {v.vmid??'ยังไม่จัดสรร'} · {statusLabel(v.status)}</li>)}</ul>
   {!preview.vms.length&&<p>บัญชีนี้ไม่มี VM ที่ต้องลบ</p>}

   <div className="sensitive-fields" data-form-type="other">
    <label>พิมพ์ชื่อบัญชี {user.username} เพื่อยืนยัน<input autoFocus value={name} onChange={e=>setName(e.target.value)} required maxLength={32} autoComplete="off" data-lpignore="true" data-1p-ignore="true" disabled={busy}/></label>
    <label>เหตุผลที่ลบ<textarea ref={reasonInput} autoComplete="off" data-lpignore="true" data-1p-ignore="true" required maxLength={1000} disabled={busy}/></label>
    <label>รหัสผ่าน Admin ของคุณ<input ref={proofInput} type="password" required maxLength={128} autoComplete="off" data-lpignore="true" data-1p-ignore="true" disabled={busy}/></label>
    <div className="dialog-actions"><button type="button" disabled={busy} onClick={onClose}>ยกเลิก</button><button type="button" className="danger-solid" disabled={busy||name!==user.username} onClick={async ()=>{if(busy||name!==user.username)return;if(!reasonInput.current?.reportValidity()||!proofInput.current?.reportValidity())return;const proof=proofInput.current.value;proofInput.current.value='';setBusy(true);setError('');try{await api(`/admin/users/${user.id}/deletion`,{confirm_username:name,confirm_vm_ids:preview.vms.map(v=>v.id),reason:reasonInput.current.value,admin_password:proof});onDone();}catch(e){setError(explainError(e));}finally{setBusy(false);}}}>{busy?'กำลังรับคำขอ…':'ยืนยันลบผู้ใช้และ VM'}</button></div>
   </div></>}
  {!preview&&<button type="button" onClick={onClose}>ปิด</button>}
 </dialog>;
}
