import { Toast } from "./Toast";
import { HelpTip } from "./HelpTip";
import { explainError } from "./errors";
import { FormEvent, useEffect, useState } from "react";
import { wholeNumber } from "./wholeNumber";

type API = <T>(path: string, body?: unknown) => Promise<T>;
export function SessionSettings({api}: {api: API}) {
  const [minutes, setMinutes] = useState(30), [saved, setSaved] = useState<number | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  useEffect(() => { let active = true; api<{token_minutes: number}>("/admin/session-policy").then(r => { if(active){setMinutes(r.token_minutes);setSaved(r.token_minutes);} }).catch(e => {if(active)setError(explainError(e));}); return () => {active=false;}; }, []);
  async function save(e: FormEvent) {
    e.preventDefault();setBusy(true);setError("");setNotice("");
    try { const r = await api<{token_minutes: number}>("/admin/session-policy", {token_minutes: minutes});setSaved(r.token_minutes);setNotice("บันทึกแล้ว มีผลกับการ Login ครั้งถัดไปของทุกบัญชี"); }
    catch(e){setError(explainError(e));}finally{setBusy(false);}
  }
  return <section className="panel session-settings"><div className="help-heading"><h2>อายุการเข้าสู่ระบบ</h2><HelpTip label="เกี่ยวกับอายุ Session">5–1440 นาที · มีผลกับ Login ครั้งถัดไป Session ที่เปิดอยู่ยังใช้เวลาเดิม</HelpTip></div>

    {error && <p role="alert" className="alert error">{error}</p>}<Toast message={notice} onClose={()=>setNotice("")}/>
    <form onSubmit={save}><label>อายุ Session (นาที)<input name="token_minutes" {...wholeNumber} min={5} max={1440} value={minutes} required onChange={e => setMinutes(Number(e.target.value))} /></label>
      <div className="preset-options">{[15,30,60,240,480].map(n => <button type="button" key={n} className={minutes===n?"selected":""} onClick={() => setMinutes(n)}>{n<60?`${n} นาที`:`${n/60} ชั่วโมง`}</button>)}</div>

      <button className="primary" disabled={busy || saved===null || saved===minutes}>บันทึกอายุ Session</button>
    </form>
  </section>;
}
