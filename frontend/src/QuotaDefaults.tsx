import { Toast } from "./Toast";
import { FormDialog } from "./FormDialog";
import { FormEvent, useEffect, useState } from 'react';
import { HelpTip } from './HelpTip';
import { explainError } from './errors';
type Values={quota_vms:number;quota_cpu:number;quota_ram:number;quota_disk:number};
type API=<T>(path:string,body?:unknown)=>Promise<T>;
const fields=[['quota_vms','จำนวน VM',1000],['quota_cpu','vCPU รวม',10000],['quota_ram','RAM รวม (MiB)',100000000],['quota_disk','Disk รวม (GiB)',10000000]] as const;
export function QuotaDefaultsForm({api,onClose,changed}:{api:API;onClose:()=>void;changed:()=>Promise<void>}){
 const [values,setValues]=useState<Values|null>(null),[apply,setApply]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 useEffect(()=>{let active=true;api<Values>('/admin/quota-defaults').then(r=>{if(active)setValues(r);}).catch(e=>{if(active)setError(explainError(e));});return()=>{active=false;};},[]);
 async function save(e:FormEvent<HTMLFormElement>){e.preventDefault();if(busy||!values)return;setBusy(true);setError('');setNotice('');try{const r=await api<Values&{updated_count:number;skipped_count:number}>('/admin/quota-defaults',{...Object.fromEntries(fields.map(([key])=>[key,values[key]])),apply_to_existing:apply});setValues(r);setNotice(apply?`บันทึกแล้ว ปรับผู้ใช้เดิม ${r.updated_count} บัญชี ข้าม ${r.skipped_count} บัญชีที่ใช้ทรัพยากรเกินค่าใหม่`:'บันทึกแล้ว มีผลกับสมาชิกใหม่ ผู้ใช้เดิมคงสิทธิ์ใช้ทรัพยากรเดิม');await changed();}catch(e){setError(explainError(e));}finally{setBusy(false);}}
 return <FormDialog title={"สิทธิ์ใช้ทรัพยากรเริ่มต้น"} busy={busy} onClose={onClose}><section className="panel quota-defaults"><div className="section-head"><div className="help-heading"><h3>สิทธิ์ใช้ทรัพยากรเริ่มต้น</h3><HelpTip label="เกี่ยวกับสิทธิ์ใช้ทรัพยากรเริ่มต้น">ค่าใหม่นี้ใช้กับสมาชิกที่สมัครหลังบันทึก หากเลือกปรับผู้ใช้เดิม จะปรับเฉพาะบัญชี User ที่ยังไม่เคยกำหนดสิทธิ์ใช้ทรัพยากรเอง และข้ามบัญชีที่ใช้ทรัพยากรเกินค่าใหม่ บัญชีที่กำหนดเองและ Admin จะไม่ถูกทับ</HelpTip></div><button type="button" disabled={busy} onClick={onClose}>ปิด</button></div>
 {error&&<p className="alert error" role="alert">{error}</p>}<Toast message={notice} onClose={()=>setNotice('')}/>
 {values?<form onSubmit={save}><div className="fields">{fields.map(([key,label,max])=><label key={key}>{label}<input name={`default_${key}`} type="number" min={0} max={max} step={1} required disabled={busy} value={values[key]} onChange={e=>setValues({...values,[key]:e.target.value===''?'':Number(e.target.value)} as Values)}/></label>)}</div><label className="checkbox-label"><input type="checkbox" checked={apply} disabled={busy} onChange={e=>setApply(e.target.checked)}/>ปรับผู้ใช้เดิมที่ยังใช้ค่าเริ่มต้นด้วย</label><button className="primary" disabled={busy}>{busy?'กำลังบันทึก…':'บันทึกสิทธิ์ใช้ทรัพยากรเริ่มต้น'}</button></form>:!error&&<p role="status">กำลังอ่านค่าเริ่มต้น…</p>}
 </section></FormDialog>;
}
