import { thaiTime } from "./time";
import { FormDialog } from "./FormDialog";
import { PasswordChecklist, passwordValid } from "./RegistrationPolicy";
import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import { FormEvent, useEffect, useId, useRef, useState } from "react";

type API = <T>(path: string, body?: unknown) => Promise<T>;
function fields(form: HTMLFormElement) {
  const data = new FormData(form);
  if(!passwordValid(String(data.get("new_password")??""),12))throw new Error("กรุณาตั้งรหัสผ่านให้ครบตาม checklist ทุกข้อ");
  if (data.get("new_password") !== data.get("confirm_password")) throw new Error("รหัสผ่านใหม่ไม่ตรงกัน");
  return data;
}
export function NewPasswordFields({guest=false,passwordName="new_password",confirmationName="confirm_password",passwordLabel="รหัสผ่านใหม่",confirmationLabel="ยืนยันรหัสผ่านใหม่"}:{guest?:boolean;passwordName?:string;confirmationName?:string;passwordLabel?:string;confirmationLabel?:string}) {
  const [password,setPassword]=useState(""),[confirmation,setConfirmation]=useState("");
  const rulesId=useId(),passwordInput=useRef<HTMLInputElement>(null);
  useEffect(()=>{
    const form=passwordInput.current?.form;
    const clear=()=>{setPassword("");setConfirmation("");};
    form?.addEventListener("reset",clear);
    return ()=>form?.removeEventListener("reset",clear);
  },[]);
  return <><label>{passwordLabel}<input ref={passwordInput} value={password} name={passwordName} type="password" minLength={12} maxLength={128} aria-describedby={rulesId} onChange={e=>setPassword(e.target.value)} autoComplete={guest?"off":"new-password"} data-lpignore={guest?"true":undefined} data-1p-ignore={guest?"true":undefined} required /></label>
    <label>{confirmationLabel}<input value={confirmation} name={confirmationName} type="password" minLength={12} maxLength={128} aria-describedby={rulesId} onChange={e=>setConfirmation(e.target.value)} autoComplete={guest?"off":"new-password"} data-lpignore={guest?"true":undefined} data-1p-ignore={guest?"true":undefined} required /></label>
    <div id={rulesId}><PasswordChecklist value={password} minLength={12}/></div></>;
}
export function PasswordForm({ api, recovery = false, onDone }: {api: API; recovery?: boolean; onDone: () => void}) {
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; setError(""); setBusy(true);
    try {
      const data = fields(form);
      await api(recovery ? "/auth/recover-password" : "/auth/change-password", {
        new_password: data.get("new_password"),
        ...(recovery ? {code: data.get("code")} : {current_password: data.get("current_password")}),
      });
      form.reset(); onDone();
    } catch (e) { setError(explainError(e)); } finally { setBusy(false); }
  }
  return <section className={`panel password-panel ${recovery ? "auth" : ""}`}><div className="help-heading"><h2>{recovery ? "กู้คืนรหัส Portal" : "เปลี่ยนรหัส Portal"}</h2><HelpTip label="เกี่ยวกับรหัสผ่าน Portal">{recovery?"ใช้โค้ดจาก Admin ภายใน 15 นาที หลังบันทึกต้อง Login ใหม่ทุกอุปกรณ์":"หลังบันทึกต้อง Login ใหม่ทุกอุปกรณ์"}</HelpTip></div>

    <form onSubmit={submit}>
      {recovery ? <label>โค้ดกู้คืน<input name="code" autoComplete="off" minLength={32} maxLength={128} required /></label> : <label>รหัส Portal ปัจจุบัน<input name="current_password" type="password" autoComplete="current-password" required maxLength={128} /></label>}
      <NewPasswordFields />{error && <p role="alert" className="error">{error}</p>}
      <button className="primary" disabled={busy}>บันทึกรหัส Portal ใหม่</button>
    </form>
  </section>;
}
export function IssueRecoveryForm({ api, user, onClose }: {api: API; user: {id: number; username: string}; onClose: () => void}) {
  const proofInput=useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<{code: string; expires_at: string} | null>(null), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  return <FormDialog title={`กู้คืนบัญชี ${user.username}`} busy={busy} onClose={onClose}><section className="panel recovery-panel"><div className="section-head"><div className="help-heading"><h2>กู้คืนบัญชี {user.username}</h2><HelpTip label="เกี่ยวกับการออกโค้ดกู้คืน">ยืนยันตัวตนเจ้าของบัญชีก่อนออกโค้ด และส่งโค้ดให้เจ้าของผ่านช่องทางส่วนตัว</HelpTip></div><button type="button" disabled={busy} onClick={onClose}>ปิด</button></div>

    {result ? <><p>แสดงโค้ดครั้งนี้เท่านั้น · หมดอายุ {thaiTime(result.expires_at)}</p><code className="recovery-code">{result.code}</code></> : <div className="sensitive-fields" data-form-type="other"><label>รหัส Portal ของ Admin<input ref={proofInput} type="password" autoComplete="off" data-lpignore="true" data-1p-ignore="true" required maxLength={128}/></label><button type="button" disabled={busy} onClick={async()=>{if(busy||!proofInput.current?.reportValidity())return;const proof=proofInput.current.value;proofInput.current.value='';setBusy(true);setError('');try{setResult(await api<{code:string;expires_at:string}>(`/admin/users/${user.id}/recovery-code`,{admin_password:proof}));}catch(e){setError(explainError(e));}finally{setBusy(false);}}}>ออกโค้ดกู้คืน 15 นาที</button></div>}
    {error && <p role="alert" className="error">{error}</p>}
  </section></FormDialog>;
}
export function VMPasswordForm({ api, vm, onDone, onClose }: {api: API; vm: {id: number; hostname: string}; onDone: () => void; onClose: () => void}) {
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  return <FormDialog title={`ขอรีเซ็ตรหัส VM: ${vm.hostname}`} busy={busy} onClose={onClose}><section className="panel"><div className="section-head"><div className="help-heading"><h2>ขอรีเซ็ตรหัส VM: {vm.hostname}</h2><HelpTip label="เกี่ยวกับการรีเซ็ตรหัส VM">รีเซ็ตบัญชี Guest เดิม · ต้องให้ Admin อนุมัติ</HelpTip></div><button type="button" disabled={busy} onClick={onClose}>ยกเลิก</button></div>

    <form autoComplete="off" data-form-type="other" onSubmit={async e => {
      e.preventDefault(); const form = e.currentTarget; setBusy(true); setError("");
      try { const data = fields(form); await api(`/vms/${vm.id}/password-resets`, {new_password: data.get("new_password"), reason: data.get("reason")}); form.reset(); onDone(); }
      catch (error) { setError(explainError(error)); } finally { setBusy(false); }
    }}><NewPasswordFields guest/><label>เหตุผล<textarea name="reason" required minLength={3} maxLength={1000} /></label>
      {error && <p role="alert" className="error">{error}</p>}<button className="primary" disabled={busy}>ส่งคำขอรีเซ็ตรหัส VM</button>
    </form></section></FormDialog>;
}
